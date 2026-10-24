"""Small, explicit workflow commands. No automatic installation, reset, or jailbreak."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import tarfile
import zipfile
from project import REPO, ROOT, WORK, BUILD, CONFIG, ADB, PACKAGE, adb_args, require_profile, sha256_file


def init():
    for path in [ROOT/'exports/yumekuro-archives', ROOT/'resource-analysis', ROOT/'android-original',
                 ROOT/'private', ROOT/'offline-player/build', BUILD]:
        path.mkdir(parents=True, exist_ok=True)
    for name in ['metadata', 'audio', 'cuesheet', 'visual', 'raw', 'play-assets']:
        path = BUILD / (name + '-supplement.json')
        if not path.exists():
            path.write_text(json.dumps({'format': 1, 'files': []}), encoding='utf8')
    note = ROOT / 'SESSION.md'
    if not note.exists():
        note.write_text('# Private migration session\n\nStage: intake\nNext human checkpoint: device details and workspace choice\n\nRecord source hashes, checks, blockers, and the next action here. Never store passwords.\n', encoding='utf8')
    print('Private workspace initialized:', ROOT)


def doctor():
    print('Workspace:', ROOT)
    anchor = ROOT if ROOT.exists() else ROOT.parent
    while not anchor.exists():
        anchor = anchor.parent
    print('Free GiB:', round(shutil.disk_usage(anchor).free / 1024**3, 2))
    for name in ['UnityPy', 'lief', 'cryptography', 'paramiko', 'httpx']:
        print(name, 'available' if importlib.util.find_spec(name) else 'not installed')
    executable = shutil.which(ADB)
    if not executable:
        print('ADB unavailable; stop at the installation checkpoint')
        return
    result = subprocess.run([executable, '-P', str(CONFIG.get('adb_port', 5037)), 'devices', '-l'], capture_output=True, text=True)
    print(result.stdout.strip())
    print('Device output is local-only. Do not publish serials.')


def index():
    database = ROOT / 'resource-analysis/archive-index.sqlite3'
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS members(kind TEXT,name TEXT,offset INTEGER,size INTEGER,type TEXT,PRIMARY KEY(kind,name))')
        for kind in ['app', 'data']:
            if db.execute('SELECT count(*) FROM members WHERE kind=?', (kind,)).fetchone()[0]:
                print(kind, 'already indexed; source archive must remain unchanged')
                continue
            archive = ROOT / 'exports/yumekuro-archives' / (kind + '.tar')
            with tarfile.open(archive, 'r:') as source:
                for item in source:
                    if PurePosixPath(item.name).is_absolute() or '..' in PurePosixPath(item.name).parts:
                        raise ValueError('Unsafe source archive path')
                    db.execute('INSERT INTO members VALUES(?,?,?,?,?)', (kind,item.name,item.offset_data,item.size,item.type.decode('ascii')))
            db.commit()
            print(kind, 'indexed')


def extract_inputs():
    output = ROOT / 'android-original'
    targets = {'assets/Octo/l': output/'android-l',
               'assets/Octo/octocacheevai': output/'android-octocacheevai',
               'assets/bin/Data/Managed/Metadata/global-metadata.dat': output/'android-global-metadata.dat',
               'lib/arm64-v8a/libil2cpp.so': ROOT/'resource-analysis/libil2cpp.so'}
    for name in ['base.apk', 'split_config.arm64_v8a.apk']:
        with zipfile.ZipFile(output/name) as archive:
            for member, path in targets.items():
                if member in archive.namelist():
                    data = archive.read(member)
                    if path.exists() and path.read_bytes() != data:
                        raise ValueError('Input extraction would overwrite different data')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
    require_profile()
    print('APK inputs extracted and exact supported profile verified')


def decrypt_ios_index():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from source_assets import fields
    analysis = ROOT / 'resource-analysis'
    key = (analysis/'octo-resource-crypto.bin').read_bytes()
    if len(key) != 32:
        raise ValueError('Expected locally derived resource-index key/IV')
    with sqlite3.connect(analysis/'archive-index.sqlite3') as db:
        row = db.execute("SELECT offset,size FROM members WHERE kind='app' AND name='./ProductName.app/Data/Octo/octocacheevai'").fetchone()
    if not row:
        raise ValueError('Discover this build\'s actual iOS index path; do not guess it')
    with (ROOT/'exports/yumekuro-archives/app.tar').open('rb') as stream:
        stream.seek(row[0]); data = stream.read(row[1])
    if data[:1] != b'\x01' or (len(data)-1) % 16:
        raise ValueError('Unrecognized encrypted index envelope')
    decrypt = Cipher(algorithms.AES(key[:16]), modes.CBC(key[16:])).decryptor()
    clear = decrypt.update(data[1:]) + decrypt.finalize()
    pad = clear[-1]
    if not 1 <= pad <= 16 or clear[-pad:] != bytes([pad])*pad:
        raise ValueError('Index padding mismatch')
    clear = clear[:-pad]
    if hashlib.md5(clear[16:]).digest() != clear[:16]:
        raise ValueError('iOS resource index payload checksum mismatch')
    (analysis/'ios-octo-index.bin').write_bytes(clear[16:])
    print('iOS index decrypted and internal MD5 verified')


def bootstrap():
    require_profile()
    content = '\n'.join((REPO/'runtime'/name).read_text(encoding='utf8') for name in ['local-provider.js','bootstrap-runtime.js'])
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD/'bootstrap.js').write_text(content.replace('com.yumekuro.local', PACKAGE), encoding='utf8')
    print('Generated version-checked runtime script. Syntax-check it before deployment.')


def plan(prefix, allow_cache_variants=False):
    from source_assets import SourceAssets
    from inspect_octo_index import fields
    local = {}
    for name in ['local-snapshot.json','metadata-supplement.json','audio-supplement.json','cuesheet-supplement.json','visual-supplement.json','play-assets-supplement.json']:
        path = BUILD/name
        if path.exists():
            local.update({r[0]:r for r in json.loads(path.read_text())['files']})
    source = SourceAssets(allow_cache_variants=allow_cache_variants)
    selected, missing = [], 0
    for number, _, value in fields((ROOT/'resource-analysis/android-octo-index.bin').read_bytes()):
        if number != 2:
            continue
        d = {n:v for n,_,v in fields(value)}
        name = d[3].decode()
        if name.startswith(prefix) and name not in local:
            if source.read(name) is not None:
                selected.append(name)
            else:
                missing += 1
    source.close()
    target = BUILD/'selection.json'
    target.write_text(json.dumps(selected, indent=2), encoding='utf8')
    print('Recoverable selections:', len(selected), '; absent from export:', missing, '; written:', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init','doctor','index','extract-inputs','decrypt-ios-index','bootstrap','plan'])
    parser.add_argument('--prefix', default='')
    parser.add_argument('--allow-verified-cache-variants', action='store_true')
    args = parser.parse_args()
    if args.action == 'plan':
        if not args.prefix:
            raise ValueError('Choose a resource family; do not blindly batch all types')
        plan(args.prefix, args.allow_verified_cache_variants)
    else:
        globals()[args.action.replace('-','_')]()


if __name__ == '__main__':
    main()
