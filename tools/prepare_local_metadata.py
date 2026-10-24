from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Adapt source master tables whose contents differ from the Android release.

These are explicitly NOT official Android MD5 matches. No image, audio or
shader is accepted through this path: only verified MonoBehaviour table data.
"""
from pathlib import Path
import csv, hashlib, io, json, subprocess, sys, tarfile
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'offline-player'))
from source_assets import SourceAssets
from inspect_octo_index import fields
import UnityPy
from UnityPy.enums import BuildTarget

def main():
    build=ROOT/'native-offline/build'
    source=SourceAssets()
    android={}
    for n,w,v in fields((ROOT/'resource-analysis/android-octo-index.bin').read_bytes()):
     if n==2:
      fs=list(fields(v));d={k:t for k,q,t in fs}
      android[d[3].decode()]=(d[1],[t for k,q,t in fs if k==8])
    id_to_name={v[0]:k for k,v in android.items()}
    failed=[]
    for row in csv.DictReader((build/'local-snapshot-verification.tsv').open(encoding='utf-8-sig'),delimiter='\t'):
     if row['logical_name'].startswith('masterdata/') and row['result']!='exact_android_md5':failed.append(row['logical_name'])
    payloads=[];rows=[]
    for name in failed:
     env=source.load(name)
     if env is None:raise RuntimeError('Source master table missing: '+name)
     types={o.type.name for o in env.objects}
     assert types <= {'AssetBundle','MonoBehaviour','MonoScript'}, (name,types)
     before={o.path_id:o.read_typetree() for o in env.objects if o.type.name=='MonoBehaviour'}
     assert before,name
     for f in env.file.files.values():
      if hasattr(f,'_m_target_platform'):
       f._m_target_platform=13;f.target_platform=BuildTarget.Android
     data=env.file.save(packer='lz4')
     test=UnityPy.load(data)
     assert all(f.target_platform==BuildTarget.Android for f in test.file.files.values() if hasattr(f,'target_platform'))
     after={o.path_id:o.read_typetree() for o in test.objects if o.type.name=='MonoBehaviour'}
     assert before==after,name
     aid,deps=android[name]
     payloads.append((f'offline/payload/{aid}',data))
     rows.append([name,aid,len(data),hashlib.sha256(data).hexdigest(),[id_to_name[i] for i in deps]])
     print(name,'verified_table_roundtrip',len(data),flush=True)
    source.close()
    meta=dict(format=1,kind='adapted_iOS_master_tables',validation='identical typed table data before/after Android platform serialization',files=rows)
    encoded=json.dumps(meta,ensure_ascii=False,separators=(',',':')).encode()
    (build/'metadata-supplement.json').write_bytes(encoded)
    proc=subprocess.Popen(adb_args()+['exec-in','run-as',PACKAGE,'tar','-xf','-','-C','files'],stdin=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdin,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
     for path,data in payloads+[('offline/metadata-supplement.json',encoded)]:
      item=tarfile.TarInfo(path);item.size=len(data);item.mode=0o600;tar.addfile(item,io.BytesIO(data))
    proc.stdin.close();code=proc.wait();print('METADATA_IMPORT',code,'tables',len(rows),flush=True)
    if code:raise SystemExit(code)
    checks=''.join(f'{r[3]}  payload/{r[1]}\n' for r in rows).encode()
    if rows:
        checked=subprocess.run(adb_args()+['shell','-T','run-as',PACKAGE,'sh','-c',"'cd files/offline && sha256sum -c -'"],input=checks,capture_output=True,check=True)
        lines=checked.stdout.decode().splitlines()
        if len(lines)!=len(rows) or any(not line.endswith(': OK') for line in lines):
            raise ValueError('Metadata phone SHA verification failed')
    print('Metadata phone hashes verified:',len(rows))

if __name__ == '__main__':
    main()
