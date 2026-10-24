from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Fetch a bounded original Play on-demand asset pack, with declared hashes.

Protocol reference: microg/GmsCore, vending-app/src/main/proto/AssetModule.proto
and vending-app/src/main/kotlin/com/google/android/finsky/extensions.kt.
Authenticated responses and signed URLs remain in the private workspace.
"""
import argparse
import base64
import hashlib
import io
import json
import zipfile

import googleplay_probe as p
from gplaydl.protobuf import ProtoDecoder


def varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def integer(number, value):
    return varint(number << 3) + varint(value)


def blob(number, value):
    if isinstance(value, str):
        value = value.encode()
    return varint((number << 3) | 2) + varint(len(value)) + value


def fields(raw):
    return ProtoDecoder(raw).read_all_ordered()


def check_hash(data, declared):
    if not declared:
        raise ValueError('Google Play did not provide a SHA-256 hash')
    if len(declared) == 64:
        expected = bytes.fromhex(declared)
    else:
        expected = base64.urlsafe_b64decode(declared + '=' * (-len(declared) % 4))
    if hashlib.sha256(data).digest() != expected:
        raise ValueError('Google Play SHA-256 mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack')
    parser.add_argument('--version', type=int, default=551)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--max-mb', type=int, default=32)
    args = parser.parse_args()
    if not args.pack.replace('_', '').isalnum():
        raise ValueError('Invalid asset pack name')
    credentials = p.auth.ensure_auth()
    if not credentials:
        raise ValueError('Google Play authentication is unavailable')
    payload = (blob(1, p.PACKAGE) + blob(2, integer(1, args.version))
               + integer(3, 20202) + integer(4, 0)
               + blob(6, blob(1, args.pack)))
    response = p.httpx.post(
        'https://play-fe.googleapis.com/fdfe/assetModuleDelivery',
        headers=p.api._proto_headers(credentials), content=payload, timeout=45)
    p.store(f'{args.pack}-asset-response.pb', response.content)
    if response.status_code != 200:
        raise ValueError(f'Asset delivery HTTP {response.status_code}')
    info = p.api._navigate(response.content, 1, 151)
    status = p.api._first_int(info, 4)
    if status is not None:
        raise ValueError(f'Asset delivery refused, status={status}')
    modules = [fields(x) for x in p.api._all_bytes(info, 3)]
    if len(modules) != 1 or p.api._first_string(modules[0], 1) != args.pack:
        raise ValueError('Unexpected asset module response')
    module = modules[0]
    if p.api._first_int(module, 2) != args.version:
        raise ValueError('Asset module version mismatch')
    summary = {'pack': args.pack, 'version': args.version, 'slices': []}
    for raw in p.api._all_bytes(module, 3):
        sf = fields(raw)
        metadata = fields(p.api._first_bytes(sf, 1))
        full = fields(p.api._first_bytes(sf, 2))
        name = p.api._first_string(metadata, 1)
        size = p.api._first_int(full, 1)
        compression = p.api._first_int(full, 3) or 0
        chunks = [fields(x) for x in p.api._all_bytes(full, 4)]
        total = sum(p.api._first_int(x, 1) or 0 for x in chunks)
        row = {'slice': name, 'size': size, 'transfer_size': total,
               'compression': compression, 'chunks': len(chunks)}
        print(json.dumps(row), flush=True)
        if args.download:
            if size > args.max_mb * 1024**2 or total > args.max_mb * 1024**2:
                raise ValueError('Pack exceeds the configured download size limit')
            if compression != 0:
                raise ValueError('Unsupported compression; requested uncompressed APK')
            pieces = []
            for chunk in chunks:
                url = p.api._first_string(chunk, 3)
                expected_size = p.api._first_int(chunk, 1)
                # Stream with a strict size bound even if the CDN misreports length.
                with p.httpx.stream('GET', url, follow_redirects=True, timeout=60) as r:
                    if r.status_code != 200:
                        raise ValueError(f'Chunk download HTTP {r.status_code}')
                    out = bytearray()
                    for piece in r.iter_bytes():
                        out.extend(piece)
                        if len(out) > expected_size:
                            raise ValueError('Chunk exceeds declared size')
                data = bytes(out)
                if len(data) != expected_size:
                    raise ValueError('Truncated asset chunk')
                check_hash(data, p.api._first_string(chunk, 2))
                pieces.append(data)
            apk = b''.join(pieces)
            if len(apk) != size:
                raise ValueError('Uncompressed slice size mismatch')
            check_hash(apk, p.api._first_string(full, 2))
            with zipfile.ZipFile(io.BytesIO(apk)) as z:
                bad = z.testzip()
                if bad:
                    raise ValueError('Asset APK ZIP CRC mismatch')
                row['entries'] = [{'name': x.filename, 'size': x.file_size}
                                  for x in z.infolist()]
            row['sha256'] = hashlib.sha256(apk).hexdigest()
            target = p.BUILD / f'play-{args.pack}-{args.version}.apk'
            if len(p.api._all_bytes(module, 3)) != 1:
                raise ValueError('Multiple slices require separate output names')
            target.write_bytes(apk)
            print(f'Verified asset APK: {target.name}', flush=True)
        summary['slices'].append(row)
    (p.BUILD / f'play-{args.pack}-{args.version}-verification.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except p.httpx.HTTPError as exc:
        print(f'Network error: {type(exc).__name__}')
        raise SystemExit(1)
