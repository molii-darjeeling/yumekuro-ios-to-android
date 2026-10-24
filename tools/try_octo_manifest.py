from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Test embedded game constants against its own encrypted resource index."""
import hashlib
from pathlib import Path
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

root = ROOT
def main():
    metadata = (root / 'android-original/android-global-metadata.dat').read_bytes()
    _, _, table, table_size, literals, _, _, _ = struct.unpack_from('<8I', metadata)
    values = set()
    candidate_path = root / 'resource-analysis/serialized-string-candidates.bin'
    if candidate_path.exists():
        values.update(candidate_path.read_bytes().splitlines())
    for position in range(table, table + table_size, 8):
        size, offset = struct.unpack_from('<2I', metadata, position)
        if size in (10, 16, 32):
            value = metadata[literals + offset:literals + offset + size]
            if all(32 <= byte < 127 for byte in value):
                values.add(value)
    keys = set()
    ivs = set()
    for value in values:
        if len(value) == 16:
            keys.add(hashlib.md5(value).digest())
            keys.add(value)
            ivs.add(value)
        if len(value) == 10:
            ivs.add(hashlib.md5(value).digest())
        if len(value) == 32:
            try:
                decoded = bytes.fromhex(value.decode('ascii'))
                if len(decoded) == 16:
                    keys.add(decoded)
                    ivs.add(decoded)
            except ValueError:
                pass
    raw = (root / 'android-original/android-octocacheevai').read_bytes()
    assert raw[0] == 1 and (len(raw) - 1) % 16 == 0
    encrypted = raw[1:]
    print('Testing embedded index constants:', len(keys), 'keys,', len(ivs), 'IVs.', flush=True)
    padding_candidates = 0
    for key in keys:
        decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        last = decryptor.update(encrypted[-16:]) + decryptor.finalize()
        last = bytes(a ^ b for a, b in zip(last, encrypted[-32:-16]))
        padding = last[-1]
        if not 1 <= padding <= 16 or last[-padding:] != bytes([padding]) * padding:
            continue
        padding_candidates += 1
        decryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).decryptor()
        plain = decryptor.update(encrypted) + decryptor.finalize()
        body = plain[16:-padding]
        expected = hashlib.md5(body).digest()
        iv = bytes(a ^ b for a, b in zip(plain[:16], expected))
        if iv in ivs:
            (root / 'resource-analysis/android-octo-index.bin').write_bytes(body)
            # These are game resource constants, retained locally for resource migration only.
            (root / 'resource-analysis/octo-resource-crypto.bin').write_bytes(key + iv)
            print('Verified encrypted resource index: AES, padding and payload MD5 all match.', flush=True)
            print('Index body bytes:', len(body), 'prefix:', repr(body[:64]), flush=True)
            break
    else:
        print('No embedded-constant match. Valid-padding candidates:', padding_candidates, flush=True)

if __name__ == '__main__':
    main()
