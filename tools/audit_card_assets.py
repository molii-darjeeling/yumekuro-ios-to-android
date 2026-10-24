from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Inventory card art and story CG against the original Android dependency graph."""
from pathlib import Path
from collections import Counter
import json
import sys

sys.path[:0] = [str(ROOT), str(ROOT / 'offline-player')]
from source_assets import SourceAssets
from inspect_octo_index import fields


def main():
    local = {}
    for filename in ['local-snapshot.json', 'metadata-supplement.json', 'audio-supplement.json',
                     'cuesheet-supplement.json', 'visual-supplement.json', 'play-assets-supplement.json']:
        local.update({r[0]: r for r in json.loads((WORK / 'build' / filename).read_text())['files']})
    records, names = {}, {}
    for number, _, value in fields((ROOT / 'resource-analysis/android-octo-index.bin').read_bytes()):
        if number != 2:
            continue
        fs = list(fields(value))
        d = {k: v for k, _, v in fs}
        name = d[3].decode()
        records[name] = (d, [v for k, _, v in fs if k == 8])
        names[d[1]] = name
    roots = [n for n in records if n.startswith((
        'unit/meister/cardimage/', 'unit/meister/livecardimage/',
        'unit/fairy/cardimage/', 'unit/fairy/livecardimage/',
        'gallery/albumthumbnail/')) or (n.startswith('story/background/') and '_stl' in n)]
    source = SourceAssets()
    seen, report, candidates = set(), [], []

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        raw = None if name in local else source.read(name)
        row = {'name': name, 'androidId': records[name][0][1], 'root': name in root_set,
               'local': name in local, 'sourcePresentIfMissing': raw is not None,
               'sourceBytesIfMissing': len(raw) if raw is not None else 0}
        report.append(row)
        if raw is not None:
            candidates.append(name)
        deps = local[name][4] if name in local else [names[i] for i in records[name][1]]
        for dep in deps:
            visit(dep)

    root_set = set(roots)
    for name in roots:
        visit(name)
    source.close()
    build = WORK / 'build'
    (build / 'card-cg-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (build / 'card-cg-recovery-selection.json').write_text(json.dumps(sorted(candidates)), encoding='utf8')
    counts = Counter()
    for row in report:
        group = '/'.join(row['name'].split('/')[:-1])
        state = 'local' if row['local'] else 'recoverable' if row['sourcePresentIfMissing'] else 'absent_in_export'
        counts[(group, state)] += 1
    for (group, state), count in sorted(counts.items()):
        print(group, state, count)
    print('Recoverable source bytes:', sum(r['sourceBytesIfMissing'] for r in report))


if __name__ == '__main__':
    main()
