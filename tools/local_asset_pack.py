"""Export/import a version-verified offline Android asset supplement, without Google login.

No save, account, authentication response, or APK is included. Export is restricted
to already verified original Android Play entries. Import rechecks the Android
index MD5, declared size, dependencies, ZIP CRC, and SHA before device writes.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile
from project import ROOT, BUILD, PACKAGE, adb_args, require_profile
from inspect_octo_index import fields

MAX_ENTRY = 64 * 1024**2
MAX_PACK = 512 * 1024**2


def records():
    by_name, by_id = {}, {}
    for number, _, raw in fields((ROOT/'resource-analysis/android-octo-index.bin').read_bytes()):
        if number != 2:
            continue
        fs=list(fields(raw));d={n:v for n,_,v in fs}
        name=d[3].decode();by_id[d[1]]=name
        by_name[name]={'id':d[1],'size':d[4],'md5':d[10].decode(),'dep_ids':[v for n,_,v in fs if n==8]}
    for row in by_name.values():
        row['deps']=[by_id[i] for i in row.pop('dep_ids')]
    return by_name


def check_row(row, data, catalog):
    if not isinstance(row,list) or len(row)!=5 or row[0] not in catalog:
        raise ValueError('Pack entry is not an indexed game resource')
    expected=catalog[row[0]]
    if type(row[1]) is not int or row[1]!=expected['id'] or row[2]!=expected['size'] or row[4]!=expected['deps']:
        raise ValueError('Pack ID, size, or dependency mapping differs from original Android index')
    if not 0<len(data)<=MAX_ENTRY or len(data)!=row[2] or hashlib.sha256(data).hexdigest()!=row[3]:
        raise ValueError('Pack payload size or SHA-256 mismatch')
    candidates=[data]
    if data.startswith(b'UnityFS\x00'):
        candidates.append(b'\x1f'+bytes(x^255 for x in data[1:48])+data[48:])
    if not data.startswith(b'UnityFS\x00') or not any(hashlib.md5(b).hexdigest()==expected['md5'] for b in candidates):
        raise ValueError('Pack payload does not match the authentic Android index MD5')


def validate_manifest(meta, profile):
    if not isinstance(meta,dict) or meta.get('format')!=1 or meta.get('package')!='com.gcrest.yumekuro':
        raise ValueError('Unrecognized local pack')
    if meta.get('version_code')!=profile['version_code'] or meta.get('abi')!=profile['abi']:
        raise ValueError('Local pack version/ABI mismatch')
    if meta.get('native_sha256')!=profile['sha256']['resource-analysis/libil2cpp.so']:
        raise ValueError('Local pack native profile mismatch')
    rows=meta.get('files')
    if not isinstance(rows,list) or not rows or len(rows)>20000:
        raise ValueError('Invalid local pack row count')
    ids=set();names=set()
    for row in rows:
        if not isinstance(row,list) or len(row)!=5 or not isinstance(row[0],str) or type(row[1]) is not int:
            raise ValueError('Malformed local pack row')
        if row[1]<=0 or row[1] in ids or row[0] in names:
            raise ValueError('Duplicate/invalid resource identity')
        ids.add(row[1]);names.add(row[0])
    return rows


def export_pack(output):
    profile=require_profile();catalog=records();adb=adb_args()
    rows=json.loads((BUILD/'play-assets-supplement.json').read_text())['files']
    if not rows:
        raise ValueError('No verified original Android supplement exists to export')
    if sum(row[2] for row in rows)>MAX_PACK:
        raise ValueError('Supplement exceeds the bounded export budget; partition it first')
    if output.exists():
        raise ValueError('Choose a new output file; existing packs are never overwritten')
    partial=output.with_suffix(output.suffix+'.partial')
    if partial.exists():
        raise ValueError('Inspect the existing incomplete export first')
    output.parent.mkdir(parents=True,exist_ok=True)
    meta={'format':1,'package':'com.gcrest.yumekuro','version_code':profile['version_code'],
          'abi':profile['abi'],'native_sha256':profile['sha256']['resource-analysis/libil2cpp.so'],
          'kind':'original_android_asset_supplement','files':rows}
    validate_manifest(meta,profile)
    with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_STORED) as archive:
        for row in rows:
            data=subprocess.run(adb+['exec-out','run-as',PACKAGE,'cat','files/offline/payload/'+str(row[1])],capture_output=True,check=True).stdout
            check_row(row,data,catalog)
            archive.writestr('payload/'+str(row[1]),data)
        archive.writestr('manifest.json',json.dumps(meta,separators=(',',':')))
    partial.rename(output)
    print('Exported authentic Android supplement:',len(rows),'resources. No user save or credentials included.')


def import_pack(path,confirmed):
    if not confirmed:
        raise ValueError('Inspect the pack and wait for transfer authorization, then use --confirmed')
    profile=require_profile();catalog=records();adb=adb_args()
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        if len({x.filename for x in entries})!=len(entries) or sum(x.file_size for x in entries)>MAX_PACK+8*1024**2:
            raise ValueError('Duplicate entries or excessive uncompressed pack size')
        if archive.getinfo('manifest.json').file_size>8*1024**2:
            raise ValueError('Pack manifest is too large')
        meta=json.loads(archive.read('manifest.json'));rows=validate_manifest(meta,profile)
        allowed={'manifest.json'}|{'payload/'+str(r[1]) for r in rows}
        if {x.filename for x in entries}!=allowed:
            raise ValueError('Local pack contains extra files or missing payloads')
        for row in rows:
            entry=archive.getinfo('payload/'+str(row[1]))
            if entry.file_size>MAX_ENTRY:
                raise ValueError('Oversized payload')
            check_row(row,archive.read(entry),catalog)
        local=BUILD/'play-assets-supplement.json'
        previous=json.loads(local.read_text()) if local.exists() else {'format':1,'files':[]}
        merged={r[0]:r for r in previous['files']};merged.update({r[0]:r for r in rows})
        previous['files']=sorted(merged.values(),key=lambda r:r[0])
        encoded=json.dumps(previous,separators=(',',':')).encode()
        process=subprocess.Popen(adb+['exec-in','run-as',PACKAGE,'tar','-xf','-','-C','files'],stdin=subprocess.PIPE)
        with tarfile.open(fileobj=process.stdin,mode='w|',format=tarfile.USTAR_FORMAT) as output:
            for row in rows:
                data=archive.read('payload/'+str(row[1]));entry=tarfile.TarInfo('offline/payload/'+str(row[1]))
                entry.size=len(data);entry.mode=0o600;output.addfile(entry,io.BytesIO(data))
            entry=tarfile.TarInfo('offline/play-assets-supplement.json');entry.size=len(encoded);entry.mode=0o600
            output.addfile(entry,io.BytesIO(encoded))
        process.stdin.close()
        if process.wait():
            raise ValueError('Pack transfer failed')
    checks=''.join(f'{r[3]}  payload/{r[1]}\n' for r in rows).encode()
    result=subprocess.run(adb+['shell','-T','run-as',PACKAGE,'sh','-c',"'cd files/offline && sha256sum -c -'"],input=checks,capture_output=True,check=True)
    lines=result.stdout.decode().splitlines()
    if len(lines)!=len(rows) or any(not line.endswith(': OK') for line in lines):
        raise ValueError('Phone pack SHA verification failed')
    local.write_bytes(encoded)
    print('Imported and phone-verified local supplement:',len(rows),'resources. No Google login used. Restart manually after the completed batch.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['export','import'])
    parser.add_argument('path',type=Path)
    parser.add_argument('--confirmed',action='store_true')
    args=parser.parse_args()
    export_pack(args.path) if args.action=='export' else import_pack(args.path,args.confirmed)


if __name__=='__main__':
    main()
