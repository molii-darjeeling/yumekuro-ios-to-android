from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Build a verified local Android snapshot, streaming payloads to the phone.

Original TARs are read-only. No intermediate payload copies are made on PC.
Only byte-identical Android reconstructions enter this snapshot.
"""
from pathlib import Path
import collections, csv, hashlib, io, json, sqlite3, subprocess, sys, tarfile, time

sys.path.insert(0, str(ROOT))
from inspect_octo_index import fields

ADB = adb_args()
PKG = PACKAGE
ANALYSIS = ROOT / 'resource-analysis'
BUILD = ROOT / 'native-offline/build'

def records(platform):
    result = {}
    for number, wire, value in fields((ANALYSIS / f'{platform}-octo-index.bin').read_bytes()):
        if number != 2:
            continue
        fs = list(fields(value))
        d = {n: v for n, w, v in fs}
        result[d[3].decode()] = dict(id=d[1], size=d[4], md5=d[10].decode(),
                                    dependencies=[v for n, w, v in fs if n == 8])
    return result

def main():
    ios, android = records('ios'), records('android')
    by_id = {v['id']: k for k, v in android.items()}
    db = sqlite3.connect(f'file:{(ANALYSIS / "archive-index.sqlite3").as_posix()}?mode=ro', uri=True)
    archives = {kind: (ROOT / 'exports/yumekuro-archives' / f'{kind}.tar').open('rb') for kind in ('app', 'data')}
    transport_log = (BUILD / 'snapshot-transport.log').open('wb')
    proc = subprocess.Popen(ADB + [ 'exec-in', 'run-as', PKG,
                             'tar', '-xf', '-', '-C', 'files'], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=transport_log)
    stats, manifest, started, total = collections.Counter(), [], time.monotonic(), 0
    existing = json.loads((BUILD / 'phone-payload-hashes.json').read_text()) if (BUILD / 'phone-payload-hashes.json').exists() else {}
    report = (BUILD / 'local-snapshot-verification.tsv').open('w', encoding='utf-8-sig', newline='')
    writer = csv.writer(report, delimiter='\t')
    writer.writerow(['logical_name', 'ios_id', 'android_id', 'result', 'conversion', 'source_member'])

    def add(archive, path, payload):
        entry = tarfile.TarInfo(path)
        entry.size = len(payload)
        entry.mode = 0o600
        archive.addfile(entry, io.BytesIO(payload))

    def checkpoint(archive, complete):
        snapshot = dict(format=1, platform='Android', complete=complete,
                        source='verified iPad archive conversion', files=manifest,
                        statistics=dict(stats), bytes=total)
        data = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode()
        add(archive, 'offline/local-snapshot.json', data)
        (BUILD / 'local-snapshot.json').write_bytes(data)

    def convert(payload, target):
        if hashlib.md5(payload).hexdigest() == target['md5']:
            return payload, 'unchanged'
        offsets = [174, 206, 158, 157]
        offsets += [i for i in range(48, min(1024, len(payload))) if payload[i] == 9 and i not in offsets]
        for pos in offsets:
            if pos >= len(payload) or payload[pos] != 9:
                continue
            candidate = payload[:pos] + b'\x0d' + payload[pos+1:]
            if hashlib.md5(candidate).hexdigest() == target['md5']:
                return candidate, f'BuildTarget@{pos}:9->13'
        return None, ''

    try:
        with tarfile.open(fileobj=proc.stdin, mode='w|', format=tarfile.USTAR_FORMAT) as output:
            # Shared metadata first, then the remaining collection. No source is invented.
            ordered = sorted(android, key=lambda n: (0 if n.startswith(('masterdata/', 'standalone/', 'shaders/')) else 1, n))
            for step, name in enumerate(ordered, 1):
                target, source = android[name], ios.get(name)
                if not source:
                    stats['no_ios_record'] += 1
                    continue
                enc = ('A' + str(source['id'])).encode().hex()
                located = None
                for kind, member in [('data', f'./Library/octo/v1/11/{enc[-1]}/{enc}/{source["md5"]}'),
                                     ('app', f'./ProductName.app/Data/Octo/{enc[-1]}/{enc}')]:
                    row = db.execute('SELECT offset,size FROM members WHERE kind=? AND name=?', (kind, member)).fetchone()
                    if row:
                        located = kind, member, row
                        break
                if not located:
                    stats['source_not_located'] += 1
                    continue
                kind, member, (offset, size) = located
                if size != target['size']:
                    stats['different_size'] += 1
                    writer.writerow([name, source['id'], target['id'], 'different_size', '', kind+':'+member])
                    continue
                archive = archives[kind]
                archive.seek(offset)
                payload = archive.read(size)
                assert len(payload) == source['size'] and hashlib.md5(payload).hexdigest() == source['md5'], name
                converted, conversion = convert(payload, target)
                if converted is None:
                    stats['no_exact_android_match'] += 1
                    writer.writerow([name, source['id'], target['id'], 'no_exact_android_match', '', kind+':'+member])
                    continue
                # PAD loads plain UnityFS; Octo's reversible envelope belongs to its own loader.
                if converted[:1] == b'\x1f' and bytes(x ^ 255 for x in converted[1:7]) == b'nityFS':
                    converted = b'U' + bytes(x ^ 255 for x in converted[1:48]) + converted[48:]
                assert converted.startswith(b'UnityFS\x00'), name
                relative = f'offline/payload/{target["id"]}'
                digest = hashlib.sha256(converted).hexdigest()
                if existing.get(str(target['id'])) != digest:
                    add(output, relative, converted)
                else:
                    stats['resumed_verified'] += 1
                deps = [by_id[i] for i in target['dependencies']]
                manifest.append([name, target['id'], len(converted), digest, deps])
                total += len(converted)
                stats['verified'] += 1
                writer.writerow([name, source['id'], target['id'], 'exact_android_md5', conversion, kind+':'+member])
                if stats['verified'] % 2000 == 0 or name == 'standalone/builtinassetlist':
                    checkpoint(output, False)
                    report.flush()
                    print(json.dumps(dict(checked=step, counts=stats, mib=round(total/1048576, 1), seconds=round(time.monotonic()-started)), ensure_ascii=False), flush=True)
            checkpoint(output, True)
        proc.stdin.close()
        code = proc.wait()
        print(json.dumps(dict(exit=code, counts=stats, bytes=total, seconds=round(time.monotonic()-started))), flush=True)
        if code:
            raise SystemExit(code)
    finally:
        report.close()
        transport_log.close()
        db.close()
        for f in archives.values():
            f.close()

if __name__ == '__main__':
    main()
