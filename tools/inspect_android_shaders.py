from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Inventory real Android shader programs embedded in the preserved APK."""
from pathlib import Path
import collections,json,re,zipfile,warnings
import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION='2021.3.54f1'
warnings.filterwarnings('ignore',category=UserWarning)
def main():
    rows=[];types=collections.Counter()
    with zipfile.ZipFile(ROOT/'android-original/base.apk') as z:
     groups=collections.defaultdict(list)
     for i in z.infolist():
      path=i.filename
      if not path.startswith('assets/bin/Data/'):continue
      m=re.match(r'(.*\.assets)\.split(\d+)$',path)
      if m:groups[m[1]].append((int(m[2]),path))
      elif path.endswith('.assets') or re.fullmatch(r'assets/bin/Data/[0-9a-f]{32}',path):groups[path].append((0,path))
     print('ANDROID_SERIALIZED_FILES',len(groups),flush=True)
     for path,parts in groups.items():
      payload=b''.join(z.read(n) for _,n in sorted(parts))
      try:
       env=UnityPy.load(payload)
       for o in env.objects:
        types[o.type.name]+=1
        if o.type.name=='Shader':
         data=o.read_typetree();name=data.get('m_ParsedForm',{}).get('m_Name') or data.get('m_Name')
         rows.append(dict(name=name,path=path,path_id=o.path_id,platforms=data.get('platforms')))
      except Exception as e:print('ANDROID_READ_ERROR',path,type(e).__name__,str(e)[:80],flush=True)
    (ROOT/'native-offline/build/android-shader-inventory.json').write_text(json.dumps(dict(shaders=rows,types=types),ensure_ascii=False),encoding='utf-8')
    print('ANDROID_SHADERS',len(rows),flush=True)
    for row in rows:print(json.dumps(row,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    main()
