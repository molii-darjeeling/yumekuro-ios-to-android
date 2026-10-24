from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
from pathlib import Path
import hashlib, sqlite3, sys, warnings
import UnityPy
sys.path.insert(0,str(ROOT))
from inspect_octo_index import fields
UnityPy.config.FALLBACK_UNITY_VERSION='2021.3.54f1'
warnings.filterwarnings('ignore',category=UserWarning)

class SourceAssets:
    def __init__(self, allow_cache_variants=False):
        self.allow_cache_variants=allow_cache_variants
        self.variant_metadata={}
        self.records={}
        for n,w,v in fields((ROOT/'resource-analysis/ios-octo-index.bin').read_bytes()):
            if n==2:
                r={a:c for a,b,c in fields(v) if a in (1,3,4,10)}
                self.records[r[3].decode()]=r
        self.db=sqlite3.connect(f'file:{(ROOT/"resource-analysis/archive-index.sqlite3").as_posix()}?mode=ro',uri=True)
        self.files={k:(ROOT/'exports/yumekuro-archives'/f'{k}.tar').open('rb') for k in ['app','data']}
    def read(self,name):
        r=self.records.get(name)
        if not r:return None
        enc=('A'+str(r[1])).encode().hex()
        for kind,member in [('data',f'./Library/octo/v1/11/{enc[-1]}/{enc}/{r[10].decode()}'),('app',f'./ProductName.app/Data/Octo/{enc[-1]}/{enc}')]:
            row=self.db.execute('SELECT offset,size FROM members WHERE kind=? AND name=?',(kind,member)).fetchone()
            if row:
                f=self.files[kind];f.seek(row[0]);b=f.read(row[1])
                if len(b)==r[4] and hashlib.md5(b).hexdigest()==r[10].decode():return b
                if not self.allow_cache_variants or kind=='data':
                    raise ValueError('Canonical original resource hash mismatch: '+name)
        if self.allow_cache_variants:
            prefix=f'./Library/octo/v1/11/{enc[-1]}/{enc}/'
            candidates=[]
            for member,offset,size in self.db.execute("SELECT name,offset,size FROM members WHERE kind='data' AND type='0' AND name>=? AND name<?",(prefix,prefix+'\uffff')):
                digest=member.rsplit('/',1)[-1]
                if len(digest)!=32 or any(c not in '0123456789abcdef' for c in digest):continue
                stream=self.files['data'];stream.seek(offset);payload=stream.read(size)
                if len(payload)!=size or hashlib.md5(payload).hexdigest()!=digest:continue
                plain=payload
                if plain[:1]==b'\x1f':plain=b'U'+bytes(x^255 for x in plain[1:48])+plain[48:]
                if not plain.startswith(b'UnityFS\x00'):continue
                env=UnityPy.load(plain)
                bundles=[o.read_typetree() for o in env.objects if o.type.name=='AssetBundle']
                if len(bundles)!=1 or bundles[0].get('m_Name')!=name:continue
                candidates.append((payload,{'kind':'verified_older_cached_bundle',
                    'actual_source_md5':digest,'current_index_md5':r[10].decode(),
                    'internal_bundle_name':name,'internal_dependencies':bundles[0]['m_Dependencies'],
                    'source_member':member}))
            distinct={meta['actual_source_md5']:(payload,meta) for payload,meta in candidates}
            if len(distinct)==1:
                payload,meta=next(iter(distinct.values()));self.variant_metadata[name]=meta
                return payload
            if len(distinct)>1:raise ValueError('Multiple valid cached versions require explicit selection: '+name)
        return None
    def dependencies_for(self,name,current,allowed_names):
        variant=self.variant_metadata.get(name)
        if not variant:return current
        deps=variant['internal_dependencies']
        if any(n not in allowed_names for n in deps):
            raise ValueError('Older bundle dependency is not in the Android catalog: '+name)
        return deps
    def load(self,name):
        b=self.read(name)
        if b is None:return None
        if b[:1]==b'\x1f':b=b'U'+bytes(x^255 for x in b[1:48])+b[48:]
        return UnityPy.load(b)
    def close(self):
        self.db.close()
        for f in self.files.values():f.close()
