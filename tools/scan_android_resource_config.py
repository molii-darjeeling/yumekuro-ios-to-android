from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
from collections import Counter
from pathlib import Path
import re
import struct
import zipfile
import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.54f1'
root = ROOT
def main():
    out = root / 'resource-analysis'
    candidates = set()
    names = Counter()
    with zipfile.ZipFile(root / 'android-original/base.apk') as archive:
        entries = [item for item in archive.infolist() if re.fullmatch(r'assets/bin/Data/[0-9a-f]{32}', item.filename)]
        print('Scanning serialized resource files:', len(entries), flush=True)
        for item in entries:
            payload = archive.read(item)
            for length in (10, 16, 32):
                pattern = re.escape(struct.pack('<i', length)) + rb'([ -~]{' + str(length).encode() + rb'})'
                candidates.update(match.group(1) for match in re.finditer(pattern, payload))
            try:
                env = UnityPy.load(payload)
                for obj in env.objects:
                    if obj.type.name != 'MonoBehaviour':
                        continue
                    raw = obj.get_raw_data()
                    if len(raw) < 32:
                        continue
                    size = struct.unpack_from('<i', raw, 28)[0]
                    if not 0 <= size <= 200 or size + 32 > len(raw):
                        continue
                    name = raw[32:32+size].decode('utf-8', errors='replace')
                    names[name] += 1
                    if re.search(r'octo|environment|config|setting', name, re.I):
                        target = out / ('config-' + item.filename.rsplit('/', 1)[-1] + '-' + str(obj.path_id) + '.bin')
                        target.write_bytes(raw)
                        print('Config object:', repr(name), 'bytes', len(raw), flush=True)
            except Exception as error:
                print('Resource scan issue:', item.filename, type(error).__name__, flush=True)
    (out / 'serialized-string-candidates.bin').write_bytes(b'\n'.join(sorted(candidates)))
    print('Additional constant candidates:', len(candidates), 'MonoBehaviour names:', names.most_common(35), flush=True)

if __name__ == '__main__':
    main()
