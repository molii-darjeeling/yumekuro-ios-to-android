"""Build a separately signed, local-only native client from the user's own APKs.
No installation is performed here. The exact supported input profile is required.
"""
from pathlib import Path
import json,struct,subprocess,zipfile
import lief
from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, require_profile
R=WORK; W=BUILD
OLD='com.gcrest.yumekuro'; NEW=PACKAGE
JAVA=Path(CONFIG.get('java','java'))
BT=Path(CONFIG.get('build_tools',''))
SIGN=ROOT/'offline-player/build'
def run(args,stdout=None):
    p=subprocess.run([str(a) for a in args],stdout=stdout or subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace')[-1500:])
    return p.stdout

def readlen8(b,p):
    n=b[p];return (((n&127)<<8)|b[p+1],p+2) if n&128 else (n,p+1)
def readlen16(b,p):
    n=struct.unpack_from('<H',b,p)[0];return (((n&32767)<<16)|struct.unpack_from('<H',b,p+2)[0],p+4) if n&32768 else (n,p+2)
def len8(n):return bytes([(n>>8)|128,n&255]) if n>=128 else bytes([n])
def len16(n):return struct.pack('<HH',(n>>16)|32768,n&65535) if n>=32768 else struct.pack('<H',n)

def manifest(raw,base):
    pool=None;chunks=[];p=8
    while p<len(raw):
        typ,hs,size=struct.unpack_from('<HHI',raw,p);c=bytearray(raw[p:p+size]);chunks.append((typ,c));p+=size
        if typ==1:
            count,styles,flags,start,styleStart=struct.unpack_from('<5I',c,8);ss=[]
            for i in range(count):
                pos=start+struct.unpack_from('<I',c,hs+i*4)[0]
                if flags&256:
                    _,pos=readlen8(c,pos);n,pos=readlen8(c,pos);ss.append(bytes(c[pos:pos+n]).decode('utf-8'))
                else:n,pos=readlen16(c,pos);ss.append(bytes(c[pos:pos+n*2]).decode('utf-16le'))
            pool=(hs,styles,flags,bytes(c[hs+count*4:hs+count*4+styles*4]),bytes(c[styleStart:]) if styleStart else b'')
    assert pool is not None
    ss=[s.replace(OLD,NEW) for s in ss];label=len(ss);ss.append('Yumekuro Local')
    result=[];skip=0
    for typ,c in chunks:
        if typ==1:
            hs,styles,flags,styleOffsets,styleData=pool;flags&=~1;offsets=[];data=bytearray()
            for s in ss:
                offsets.append(len(data));u=s.encode('utf-16le')
                if flags&256:
                    b=s.encode('utf-8');data+=len8(len(u)//2)+len8(len(b))+b+b'\0'
                else:data+=len16(len(u)//2)+u+b'\0\0'
            while len(data)%4:data+=b'\0'
            start=hs+len(ss)*4+styles*4;styStart=start+len(data) if styles else 0
            c=bytearray(struct.pack('<HHI5I',1,hs,start+len(data)+len(styleData),len(ss),styles,flags,start,styStart))
            c+=b''.join(struct.pack('<I',n) for n in offsets)+styleOffsets+data+styleData
        elif typ==0x102:
            name=ss[struct.unpack_from('<I',c,20)[0]];a=16+struct.unpack_from('<H',c,24)[0];cnt=struct.unpack_from('<H',c,28)[0];stride=struct.unpack_from('<H',c,26)[0]
            if skip:skip+=1;continue
            attrs=[]
            for i in range(cnt):
                pos=a+i*stride;ni,rawValue=struct.unpack_from('<II',c,pos+4);dataType=c[pos+15];value=struct.unpack_from('<I',c,pos+16)[0]
                attrs.append((ss[ni],pos,ss[value] if dataType==3 else value))
            if name=='uses-permission' and any(n=='name' and v=='android.permission.INTERNET' for n,pos,v in attrs):skip=1;continue
            if name=='application' and base:
                for n,pos,v in attrs:
                    if n=='label':struct.pack_into('<I',c,pos+8,label);c[pos+15]=3;struct.pack_into('<I',c,pos+16,label)
                    elif n in ('debuggable','extractNativeLibs'):c[pos+15]=18;struct.pack_into('<I',c,pos+16,0xffffffff)
        elif typ==0x103 and skip:skip-=1;continue
        elif skip:continue
        result.append(c)
    data=b''.join(result)
    return struct.pack('<HHI',3,8,8+len(data))+data


def main():
    require_profile()
    W.mkdir(parents=True,exist_ok=True)
    gadget=W/'libofflinegadget.so'
    if not gadget.is_file():
        raise ValueError('Place the verified official Android arm64 Frida Gadget at native-offline/build/libofflinegadget.so first')
    cfg=json.dumps({'interaction':{'type':'script','path':f'/sdcard/Android/data/{NEW}/files/offline/bootstrap.js'},'runtime':'qjs','teardown':'minimal'}).encode()
    with zipfile.ZipFile(ROOT/'android-original/split_config.arm64_v8a.apk') as z:(W/'libmain-original.so').write_bytes(z.read('lib/arm64-v8a/libmain.so'))
    elf=lief.ELF.parse(str(W/'libmain-original.so'));elf.add_library('libofflinegadget.so');elf.write(str(W/'libmain-local.so'))
    for filename,isbase in [('base.apk',True),('split_config.arm64_v8a.apk',False)]:
        out=W/('unsigned-'+filename)
        with zipfile.ZipFile(ROOT/'android-original'/filename) as src,zipfile.ZipFile(out,'w') as dest:
            for entry in src.infolist():
                if entry.filename.startswith('META-INF/'):continue
                b=src.read(entry.filename)
                if entry.filename=='AndroidManifest.xml':b=manifest(b,isbase)
                if entry.filename=='lib/arm64-v8a/libmain.so':b=(W/'libmain-local.so').read_bytes()
                if entry.filename=='resources.arsc':
                    # Keep original numeric resource IDs, update the fixed-width package name.
                    old=OLD.encode('utf-16le')+b'\0\0';new=NEW.encode('utf-16le')+b'\0\0';at=b.find(old)
                    if at>=0 and b[at:at+256].startswith(old):b=b[:at]+new+b'\0'*(256-len(new))+b[at+256:]
                dest.writestr(entry,b)
            if not isbase:
                dest.writestr('lib/arm64-v8a/libofflinegadget.so',gadget.read_bytes(),compress_type=zipfile.ZIP_STORED)
                dest.writestr('lib/arm64-v8a/libofflinegadget.config.so',cfg,compress_type=zipfile.ZIP_STORED)
        aligned=W/('aligned-'+filename);signed=R/('local-'+filename)
        run([BT/'zipalign.exe','-f','4',out,aligned])
        run([JAVA,'-jar',BT/'lib/apksigner.jar','sign','--ks',SIGN/'offline-player-private.p12','--ks-key-alias','offline-player','--ks-pass','file:'+str(SIGN/'signing-password-private.txt'),'--out',signed,aligned])
        run([JAVA,'-jar',BT/'lib/apksigner.jar','verify',signed])
        print('NATIVE_APK_READY',signed.name,signed.stat().st_size,flush=True)

if __name__ == '__main__':
    main()
