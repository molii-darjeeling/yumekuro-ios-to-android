"""Export original encrypted Production files, or import them into the separate local app."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
from project import ROOT, PACKAGE, adb_args


def extract():
    target = ROOT / 'android-import/source-save'
    manifest = []
    with tarfile.open(ROOT/'exports/yumekuro-archives/data.tar', 'r:') as archive:
        for item in archive:
            name = item.name.removeprefix('./')
            if not item.isfile() or not name.startswith('Documents/Production/'):
                continue
            relative = name.removeprefix('Documents/')
            if not re.fullmatch(r'[A-Za-z0-9_./+-]+', relative) or '..' in PurePosixPath(relative).parts:
                raise ValueError('Unexpected encoded save filename')
            data = archive.extractfile(item).read()
            if len(data) != item.size:
                raise ValueError('Truncated source save')
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != data:
                raise ValueError('Existing extracted save differs; do not overwrite it')
            path.write_bytes(data)
            manifest.append([relative,len(data),hashlib.sha256(data).hexdigest()])
    if not manifest:
        raise ValueError('No Production files found; locate the actual save directory before proceeding')
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('Extracted and source-verified encrypted save files:',len(manifest))


def transfer(confirmed):
    if not confirmed:
        raise ValueError('Wait for the user to approve stopping the local app and importing their save, then use --confirmed')
    adb = adb_args()
    target = ROOT / 'android-import/source-save'
    manifest = json.loads((target/'manifest.json').read_text())
    for relative, size, digest in manifest:
        data = (target/relative).read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Extracted save changed since verification')
    run = lambda args, **kw: subprocess.run(adb+args,capture_output=True,check=True,**kw)
    run(['shell','am','force-stop','--user','0',PACKAGE])
    remote = '/sdcard/Android/data/'+PACKAGE+'/files'
    # mkdir only affects the separate local app; original app and iOS stay intact.
    run(['shell','mkdir','-p',remote])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    exists = subprocess.run(adb+['shell','test','-d',remote+'/Production'],capture_output=True).returncode == 0
    if exists:
        old = run(['exec-out','tar','-cf','-','-C',remote,'Production']).stdout
        with tarfile.open(fileobj=io.BytesIO(old),mode='r:') as backup:
            if not list(backup):
                raise ValueError('Existing save backup is empty')
        private = ROOT/'private'
        private.mkdir(parents=True,exist_ok=True)
        (private/('android-save-before-'+stamp+'.tar')).write_bytes(old)
        run(['shell','mv',remote+'/Production',remote+'/Production.before-'+stamp])
    process = subprocess.Popen(adb+['exec-in','tar','-xf','-','-C',remote],stdin=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdin,mode='w|',format=tarfile.USTAR_FORMAT) as output:
        for relative, size, _ in manifest:
            entry = tarfile.TarInfo(relative);entry.size=size;entry.mode=0o600
            with (target/relative).open('rb') as source:
                output.addfile(entry,source)
    process.stdin.close()
    if process.wait():
        raise ValueError('Transfer failed; previous save remains in the timestamped backup directory')
    for relative, size, digest in manifest:
        returned = run(['exec-out','cat',remote+'/'+relative]).stdout
        if len(returned) != size or hashlib.sha256(returned).hexdigest() != digest:
            raise ValueError('Phone save round-trip verification failed')
    print('Every imported encrypted save matches the user\'s original export; no JSON progress was fabricated.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['extract','import'])
    parser.add_argument('--confirmed',action='store_true')
    args=parser.parse_args()
    extract() if args.action=='extract' else transfer(args.confirmed)


if __name__=='__main__':
    main()
