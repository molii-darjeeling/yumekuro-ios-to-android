from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
from collections import Counter
from pathlib import Path
import re
import struct

root = ROOT / 'resource-analysis'

def varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
        shift += 7
        if shift > 64:
            raise ValueError('Invalid protobuf varint')

def fields(data):
    offset = 0
    while offset < len(data):
        tag, offset = varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire == 2:
            size, offset = varint(data, offset)
            value = data[offset:offset + size]
            offset += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = data[offset:offset + size]
            offset += size
        else:
            raise ValueError('Unsupported protobuf wire type')
        yield number, wire, value

if __name__ == '__main__':
    counts = Counter()
    samples = {}
    for number, wire, value in fields((root / 'android-octo-index.bin').read_bytes()):
        counts[number, wire] += 1
        samples.setdefault(number, value)
    print('Top-level fields:', counts)
    for number, value in samples.items():
        if isinstance(value, int):
            print('FIELD', number, value)
        elif len(value) < 400:
            print('FIELD', number, repr(value))
            if number in (2, 3):
                print(' ITEM FIELDS', [(n, w, repr(v) if isinstance(v, bytes) else v) for n, w, v in fields(value)])
        else:
            print('FIELD', number, 'bytes', len(value), 'prefix', repr(value[:100]))
    for path in root.glob('config-*.bin'):
        urls = re.findall(rb'https?://[ -~]+', path.read_bytes())
        for url in urls:
            print('CONFIG URL', path.name, url.decode('ascii'))
