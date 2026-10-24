"""Plan original cue descriptors and their missing clips; never writes a device."""
import argparse
import json
from project import ROOT, BUILD
from source_assets import SourceAssets
from inspect_octo_index import fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-verified-cache-variants', action='store_true')
    args = parser.parse_args()
    known = {}
    for filename in ['local-snapshot.json', 'metadata-supplement.json',
                     'audio-supplement.json', 'cuesheet-supplement.json',
                     'visual-supplement.json', 'play-assets-supplement.json']:
        path = BUILD / filename
        if path.exists():
            known.update({r[0]: r for r in json.loads(path.read_text())['files']})
    records, names = {}, {}
    for number, _, value in fields((ROOT/'resource-analysis/android-octo-index.bin').read_bytes()):
        if number != 2:
            continue
        fs = list(fields(value)); d = {k:v for k,_,v in fs}
        name = d[3].decode(); names[d[1]] = name
        if name.startswith(('sound/cuesheet/', 'sound/cuesheetoptional/')) and name not in known:
            records[name] = [v for k,_,v in fs if k == 8]
    source = SourceAssets(allow_cache_variants=args.allow_verified_cache_variants)
    complete, recoverable, needed_audio, blocked = [], [], set(), []
    presence = {}
    try:
        for name, ids in sorted(records.items()):
            if source.read(name) is None:
                continue
            deps = source.dependencies_for(name, [names[i] for i in ids], set(names.values()))
            absent = [n for n in deps if n not in known]
            if not absent:
                complete.append(name)
                continue
            for dependency in absent:
                if dependency not in presence:
                    presence[dependency] = source.read(dependency) is not None
            if all(presence[n] for n in absent) and all(n.startswith('sound/audioclips/') for n in absent):
                recoverable.append(name); needed_audio.update(absent)
            else:
                blocked.append({'name':name, 'missing':absent})
    finally:
        source.close()
    BUILD.mkdir(parents=True, exist_ok=True)
    for filename, values in [('portable-cuesheet-selection.json', complete),
                             ('remaining-cuesheet-selection.json', recoverable),
                             ('remaining-story-audio-selection.json', sorted(needed_audio)),
                             ('blocked-cuesheets-private.json', blocked)]:
        (BUILD/filename).write_text(json.dumps(values, indent=2), encoding='utf8')
    print('Complete descriptors:', len(complete), '; recoverable after clips:', len(recoverable),
          '; missing clips to prepare in bounded batches:', len(needed_audio), '; blocked:', len(blocked))


if __name__ == '__main__':
    main()
