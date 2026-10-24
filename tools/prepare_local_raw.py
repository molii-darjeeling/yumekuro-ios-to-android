from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Stream original Octo raw media; require exact original Android size and MD5.

Raw resources are top-level index field 4 and use R IDs, not AssetBundle A IDs.
No movie, audio stream, codec, or container bytes are modified.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import subprocess
import sys

sys.path.insert(0,str(ROOT))
from inspect_octo_index import fields


def main():
    records={}
    for platform in ['ios','android']:
        current={}
        for n,_,v in fields((ROOT/'resource-analysis'/f'{platform}-octo-index.bin').read_bytes()):
            if n==4:
                d={k:x for k,_,x in fields(v)};current[d[3].decode()]=d
        records[platform]=current
    db=sqlite3.connect('file:'+(ROOT/'resource-analysis/archive-index.sqlite3').as_posix()+'?mode=ro',uri=True)
    streams={k:(ROOT/'exports/yumekuro-archives'/f'{k}.tar').open('rb') for k in ['app','data']}
    adb=adb_args()
    rows=[];skipped=[]
    # Resume only exact phone hashes; use sync PUSH for binary payload transport.
    existing=subprocess.run(adb+['shell','-T','run-as',PACKAGE,'sh','-c',"'sha256sum files/offline/payload/R* 2>/dev/null'"],capture_output=True)
    hashes={}
    for line in existing.stdout.decode('utf8','replace').splitlines():
        parts=line.split()
        if len(parts)==2 and len(parts[0])==64:hashes[Path(parts[1]).name]=parts[0]
    try:
        for name,target in records['android'].items():
            source=records['ios'].get(name)
            if source is None:
                skipped.append({'name':name,'reason':'no_ios_record'});continue
            ext=Path(name).suffix
            if ext not in ('.mp4','.mov','.mp3','.caf','.wav'):
                raise ValueError('Unreviewed raw media extension')
            enc=('R'+str(source[1])).encode().hex();located=None
            for kind,member in [('data',f'./Library/octo/v1/11/{enc[-1]}/{enc}/{source[10].decode()}{ext}'),
                                ('app',f'./ProductName.app/Data/Octo/{enc[-1]}/{enc}')]:
                hit=db.execute('SELECT offset,size FROM members WHERE kind=? AND name=?',(kind,member)).fetchone()
                if hit:located=(kind,hit);break
            if not located:
                skipped.append({'name':name,'reason':'absent_from_source'});continue
            kind,(offset,size)=located;streams[kind].seek(offset);data=streams[kind].read(size)
            if len(data)!=source[4] or hashlib.md5(data).hexdigest()!=source[10].decode():
                raise ValueError('Original raw media hash mismatch: '+name)
            if len(data)!=target[4] or hashlib.md5(data).hexdigest()!=target[10].decode():
                skipped.append({'name':name,'reason':'not_exact_android_media'});continue
            filename='R'+str(target[1])+ext
            row=[name,target[1],len(data),hashlib.sha256(data).hexdigest(),[],{'kind':'raw','file':filename}]
            rows.append(row)
            if hashes.get(filename)!=row[3]:
                # Windows adb shell stdin treated byte 0x1A as EOF in a
                # deterministic binary probe. Use the sync PUSH protocol,
                # then a device-local copy; neither transports media over
                # shell stdin. Keep at most one bounded temporary PC file.
                temporary=WORK/'build/raw-transfer.tmp'
                temporary.write_bytes(data)
                external='/data/local/tmp/yumekuro-raw-transfer.tmp'
                subprocess.run(adb+['push',str(temporary),external],capture_output=True,check=True)
                subprocess.run(adb+['shell','run-as',PACKAGE,'cp',external,'files/offline/payload/'+filename],capture_output=True,check=True)
                temporary.unlink()
            if len(rows)%25==0:print('Prepared exact Android raw media:',len(rows),flush=True)
        encoded=json.dumps({'format':1,'kind':'original_android_raw_media_md5_verified','files':rows},separators=(',',':')).encode()
        subprocess.run(adb+['shell','-T','run-as',PACKAGE,'sh','-c',"'cat > files/offline/raw-supplement.json'"],input=encoded,capture_output=True,check=True)
        checks=''.join(f'{r[3]}  payload/{r[5]["file"]}\n' for r in rows).encode()
        result=subprocess.run(adb+['shell','-T','run-as',PACKAGE,'sh','-c',"'cd files/offline && sha256sum -c -'"],input=checks,capture_output=True,check=True)
        lines=result.stdout.decode().splitlines()
        if len(lines)!=len(rows) or any(not line.endswith(': OK') for line in lines):raise ValueError('Raw resource phone SHA mismatch')
        (WORK/'build/raw-supplement.json').write_bytes(encoded)
        (WORK/'build/raw-resource-skipped.json').write_text(json.dumps(skipped,indent=2),encoding='utf8')
        print('Imported and phone-verified exact Android raw media:',len(rows),'bytes',sum(r[2] for r in rows),'skipped',len(skipped),flush=True)
    finally:
        db.close()
        for stream in streams.values():stream.close()


if __name__=='__main__':main()
