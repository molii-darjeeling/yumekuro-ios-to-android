from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Final source/cached-variant/raw-media inventory and optional complete phone SHA audit.

Writes private reports only; never enters UI, restarts an app, or changes progress.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse
import json
import subprocess
import sys

sys.path[:0]=[str(ROOT),str(ROOT/'offline-player')]
from source_assets import SourceAssets
from inspect_octo_index import fields


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone-verify',action='store_true')
    args=parser.parse_args()
    local={}
    for f in ['local-snapshot.json','metadata-supplement.json','audio-supplement.json',
              'cuesheet-supplement.json','visual-supplement.json','raw-supplement.json','play-assets-supplement.json']:
        path=WORK/'build'/f
        if path.exists():local.update({r[0]:r for r in json.loads(path.read_text())['files']})
    catalogs={}
    for platform in ['ios','android']:
        records={}
        for n,_,v in fields((ROOT/'resource-analysis'/f'{platform}-octo-index.bin').read_bytes()):
            if n not in (2,4):continue
            fs=list(fields(v));d={k:x for k,_,x in fs};name=d[3].decode()
            records[name]={'id':d[1],'md5':d[10].decode(),'bytes':d[4],
                           'kind':'A' if n==2 else 'R','dependencyIds':[x for k,_,x in fs if k==8]}
        byid={r['id']:n for n,r in records.items() if r['kind']=='A'}
        for r in records.values():r['deps']=[byid[i] for i in r['dependencyIds']]
        catalogs[platform]=records
    source=SourceAssets()
    members={(k,n):(o,z) for k,n,o,z in source.db.execute("SELECT kind,name,offset,size FROM members WHERE type='0'")}
    variants=defaultdict(list)
    for (kind,path),(offset,size) in members.items():
        if kind!='data' or not path.startswith('./Library/octo/v1/11/'):continue
        parts=path.split('/');leaf=parts[-1]
        if len(leaf)!=32 or any(c not in '0123456789abcdef' for c in leaf):continue
        try:identity=bytes.fromhex(parts[-2]).decode('ascii')
        except (ValueError,UnicodeError):continue
        variants[identity].append({'member':path,'bytes':size,'md5':leaf})
    available={}
    for name,r in catalogs['ios'].items():
        identity=r['kind']+str(r['id']);enc=identity.encode().hex();suffix=Path(name).suffix if r['kind']=='R' else ''
        for kind,path in [('data',f'./Library/octo/v1/11/{enc[-1]}/{enc}/{r["md5"]}{suffix}'),
                          ('app',f'./ProductName.app/Data/Octo/{enc[-1]}/{enc}')]:
            if (kind,path) in members and members[(kind,path)][1]==r['bytes']:
                available[name]={'source':'canonical_inventory','bytes':r['bytes']};break
        if name not in available and r['kind']=='A' and identity in variants:
            available[name]={'source':'older_cached_candidate','bytes':sum(x['bytes'] for x in variants[identity])}
    def required(n):
        return n.startswith(('unit/meister/cardimage/','unit/meister/livecardimage/',
            'unit/fairy/cardimage/','unit/fairy/livecardimage/','gallery/albumthumbnail/',
            'story/scripts/','story/background/','story/effect/','actor/atlas/',
            'guildspine/','fairysd/','background/','sound/audioclips/','sound/cuesheet/','sound/cuesheetoptional/')) or n.startswith('spine/chr_') or (
            n.startswith('guildhouse/guildhouse/') and not n.endswith('_seek')) or catalogs['ios'][n]['kind']=='R'
    cache={}
    def missing(n,stack=None):
        if n in cache:return cache[n]
        stack=set() if stack is None else stack
        if n in stack:return frozenset()
        stack=stack|{n}
        result=set() if n in local else {n}
        deps=local[n][4] if n in local else catalogs['android'].get(n,{}).get('deps',[])
        for d in deps:result.update(missing(d,stack))
        cache[n]=frozenset(result);return cache[n]
    groups=defaultdict(Counter);gaps=[];source_only=[];recover=set()
    for n,origin in available.items():
        if not required(n):continue
        if catalogs['ios'][n]['kind']=='R':group='raw_media'
        elif n.startswith('sound/audioclips/'):group='/'.join(n.split('/')[:3])
        else:group='/'.join(n.split('/')[:3] if n.startswith('unit/') else n.split('/')[:-1])
        groups[group]['sourceAvailable']+=1
        if n not in catalogs['android']:
            groups[group]['noAndroidIndexMapping']+=1;source_only.append(n);continue
        absent=missing(n)
        if not absent:groups[group]['completeClosure']+=1
        else:
            groups[group]['incompleteClosure']+=1
            item={'name':n,'source':origin['source'],'rootLocal':n in local,'missing':sorted(absent)}
            if '/livecardimage/' in n:
                still=n.replace('/livecardimage/','/cardimage/').replace('_livecard_','_card_')
                item['fullStaticFallbackAvailable']=still in local and not missing(still)
            gaps.append(item)
            recover.update(d for d in absent if d in available and catalogs['ios'].get(d,{}).get('kind')=='A')
    source.close()
    report={'evidence':'catalog/archive inventory; older candidates require internal-name validation on conversion',
            'localFiles':len(local),'localBytes':sum(r[2] for r in local.values()),
            'groups':dict(groups),'gaps':gaps,'iOSOnlyNames':source_only,
            'recoverableOrCandidateNames':sorted(recover),'phoneSHA':None}
    build=WORK/'build'
    (build/'final-visible-recovery-selection.json').write_text(json.dumps(sorted(recover),indent=2),encoding='utf8')
    if args.phone_verify:
        adb=adb_args()
        checks=''.join(f'{r[3]}  payload/{r[5]["file"] if len(r)>5 and r[5].get("kind")=="raw" else r[1]}\n' for r in local.values()).encode()
        checked=subprocess.run(adb+['shell','-T','run-as',PACKAGE,'sh','-c',"'cd files/offline && sha256sum -c -'"],input=checks,capture_output=True)
        lines=checked.stdout.decode('utf8','replace').splitlines()
        failed=[line for line in lines if not line.endswith(': OK')]
        report['phoneSHA']={'requested':len(local),'returned':len(lines),'failures':failed,
                            'exitCode':checked.returncode,'stderr':checked.stderr.decode('utf8','replace')}
        if checked.returncode or failed or len(lines)!=len(local):
            (build/'final-audit-private.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            raise ValueError('Final phone hash audit failed; inspect the private report before declaring readiness')
    (build/'final-audit-private.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    for group,count in sorted(groups.items()):print(group,json.dumps(count))
    print('Local bytes',report['localBytes'],'remaining visible gaps',len(gaps),'source-only names',source_only)
    if report['phoneSHA']:print('Full phone SHA checks passed:',len(local))


if __name__=='__main__':main()
