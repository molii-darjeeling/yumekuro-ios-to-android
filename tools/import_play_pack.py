from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Import an original Play pack whose paths match its Octo logical prefix.

Only exact original Android-index MD5 matches are admitted. Source APKs and
archives are read-only. Payloads stream directly into the native local app.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile

sys.path.insert(0, str(ROOT))
from inspect_octo_index import fields
import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.54f1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack')
    parser.add_argument('--version', type=int, default=551)
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--select', action='append', default=[])
    parser.add_argument('--selection-file', type=Path)
    parser.add_argument('--prefix', default='')
    parser.add_argument('--logical-root', default='')
    args = parser.parse_args()
    if args.selection_file:
        chosen = json.loads(args.selection_file.read_text(encoding='utf-8'))
        if not isinstance(chosen, list) or any(not isinstance(name, str) for name in chosen):
            raise ValueError('Selection file must contain logical resource names')
        args.select.extend(chosen)
    build = WORK / 'build'
    logical_root = args.logical_root or args.pack
    records = {}
    all_ids = {}
    for number, wire, value in fields((ROOT / 'resource-analysis/android-octo-index.bin').read_bytes()):
        if number == 2:
            fs = list(fields(value))
            d = {k: v for k, w, v in fs}
            name = d[3].decode()
            all_ids[d[1]] = name
            if name.startswith(logical_root + '/'):
                records[name] = (d, [v for k, w, v in fs if k == 8])
    rows, payloads, proof = [], [], []
    if args.remote and not (args.select or args.prefix):
        raise ValueError('Remote imports require explicit logical resource selection')
    remote = None
    if args.remote:
        from remote_play_zip import RemotePlayZip
        remote = RemotePlayZip(args.pack)
    with zipfile.ZipFile(remote or (build / f'play-{args.pack}-{args.version}.apk')) as z:
        entries = set(z.namelist())
        selected_names = [name for name in sorted(records)
                          if not (args.select or args.prefix)
                          or name in args.select or (args.prefix and name.startswith(args.prefix))]
        if remote:
            wanted_entries = [z.getinfo('assets/assetpack/' + name.split('/', 1)[1])
                              for name in selected_names
                              if 'assets/assetpack/' + name.split('/', 1)[1] in entries]
            print(f'Prefetching {len(wanted_entries)} selected entries, '
                  f'{sum(x.file_size for x in wanted_entries)} content bytes.', flush=True)
            remote.prefetch_entries(sorted(wanted_entries, key=lambda entry: entry.header_offset))
        for name in selected_names:
            d, dependencies = records[name]
            entry = 'assets/assetpack/' + name.split('/', 1)[1]
            if entry not in entries:
                continue
            data = z.read(entry)
            expected_md5 = d[10].decode()
            hash_form = 'plain UnityFS'
            actual_md5 = hashlib.md5(data).hexdigest()
            if actual_md5 != expected_md5 and data.startswith(b'UnityFS\0'):
                # Octo indexes may hash the legacy 48-byte transport envelope;
                # Play packs contain the same payload without that envelope.
                wrapped = b'\x1f' + bytes(x ^ 255 for x in data[1:48]) + data[48:]
                actual_md5 = hashlib.md5(wrapped).hexdigest()
                hash_form = 'Octo 48-byte transport envelope'
            if len(data) != d[4] or actual_md5 != expected_md5:
                raise ValueError('Original Android MD5 mismatch: ' + name)
            row = [name, d[1], len(data), hashlib.sha256(data).hexdigest(),
                   [all_ids[i] for i in dependencies]]
            item = {'name': name, 'id': d[1], 'bytes': len(data),
                    'md5': expected_md5, 'hash_form': hash_form,
                    'validation': 'original Android index MD5 match'}
            if args.pack == 'shaders':
                env = UnityPy.load(data)
                platforms = set()
                shader_count = 0
                for obj in env.objects:
                    if obj.type.name == 'Shader':
                        shader_count += 1
                        platforms.update(int(x) for x in obj.read().platforms)
                if not shader_count or 14 in platforms:
                    raise ValueError('Android shader platform validation failed')
                item.update(shader_count=shader_count, gpu_platforms=sorted(platforms))
            rows.append(row)
            payloads.append((f'offline/payload/{d[1]}', data))
            proof.append(item)
    if remote:
        print(f'Range transfer: {remote.transferred} bytes of {remote.size}-byte asset APK.')
        remote.close()
    if not rows:
        raise ValueError('No matching original resources in the pack')
    meta_path = build / 'play-assets-supplement.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {
        'format': 1, 'kind': 'original_google_play_asset_packs', 'version': args.version, 'files': []}
    merged = {row[0]: row for row in meta['files']}
    merged.update({row[0]: row for row in rows})
    meta['files'] = sorted(merged.values(), key=lambda row: row[0])
    encoded = json.dumps(meta, ensure_ascii=False, separators=(',', ':')).encode()
    meta_path.write_bytes(encoded)
    proof_path = build / f'original-android-{args.pack}-verification.json'
    old_proof = json.loads(proof_path.read_text()) if proof_path.exists() else []
    proof_rows = {row['name']: row for row in old_proof}
    proof_rows.update({row['name']: row for row in proof})
    proof_path.write_text(json.dumps(list(proof_rows.values()), ensure_ascii=False, indent=2), encoding='utf-8')
    adb = adb_args()
    process = subprocess.Popen(adb + ['exec-in', 'run-as', PACKAGE,
                                    'tar', '-xf', '-', '-C', 'files'], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdin, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
        for path, data in payloads + [('offline/play-assets-supplement.json', encoded)]:
            entry = tarfile.TarInfo(path)
            entry.size, entry.mode = len(data), 0o600
            tar.addfile(entry, io.BytesIO(data))
    process.stdin.close()
    if process.wait() != 0:
        raise ValueError('Phone transfer failed')
    checks = ''.join(f'{row[3]}  payload/{row[1]}\n' for row in rows).encode()
    checked = subprocess.run(adb + ['shell', '-T', 'run-as', PACKAGE,
                                   'sh', '-c', "'cd files/offline && sha256sum -c -'"],
                             input=checks, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = checked.stdout.decode('utf-8', 'replace').splitlines()
    if checked.returncode or len(output) != len(rows) or any(not x.endswith(': OK') for x in output):
        raise ValueError('Phone SHA-256 verification failed')
    print(f'Imported and verified {len(rows)} original Android resources from {args.pack}.')
    if args.pack == 'shaders':
        for item in proof:
            print(json.dumps(item))


if __name__ == '__main__':
    main()
