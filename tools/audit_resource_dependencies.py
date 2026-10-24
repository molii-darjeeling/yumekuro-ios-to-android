from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Read-only dependency closure report using the real Android index."""
from pathlib import Path
from collections import Counter
import argparse
import json
import sys

sys.path[:0] = [str(ROOT), str(ROOT / 'offline-player')]
from source_assets import SourceAssets
from inspect_octo_index import fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-file', type=Path, required=True)
    args = parser.parse_args()
    roots = json.loads(args.selection_file.read_text())
    local = {}
    for filename in ['local-snapshot.json', 'metadata-supplement.json', 'audio-supplement.json',
                     'cuesheet-supplement.json', 'visual-supplement.json', 'play-assets-supplement.json']:
        local.update({r[0]: r for r in json.loads((WORK / 'build' / filename).read_text())['files']})
    records, names = {}, {}
    for number, _, value in fields((ROOT / 'resource-analysis/android-octo-index.bin').read_bytes()):
        if number == 2:
            fs = list(fields(value))
            d = {k: v for k, _, v in fs}
            name = d[3].decode()
            records[name] = [v for k, _, v in fs if k == 8]
            names[d[1]] = name
    source = SourceAssets()
    seen, missing = set(), []
    def visit(name):
        if name in seen:
            return
        seen.add(name)
        if name not in local:
            raw = source.read(name)
            missing.append({'name': name, 'sourcePresent': raw is not None,
                            'sourceBytes': len(raw) if raw is not None else 0})
        deps = local[name][4] if name in local else [names[i] for i in records[name]]
        for dependency in deps:
            visit(dependency)
    for root in roots:
        visit(root)
    source.close()
    report = {'roots': roots, 'closureSize': len(seen), 'missing': missing}
    (WORK / 'build' / 'dependency-closure-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (WORK / 'build' / 'dependency-recovery-selection.json').write_text(json.dumps([r['name'] for r in missing if r['sourcePresent']]), encoding='utf-8')
    print('Closure resources:', len(seen), 'missing:', len(missing))
    print('Missing by category:', dict(Counter(r['name'].split('/')[0] for r in missing)))
    for row in missing[:35]:
        print(json.dumps(row))


if __name__ == '__main__':
    main()
