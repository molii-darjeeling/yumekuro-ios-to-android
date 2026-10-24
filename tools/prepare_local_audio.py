from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Adapt portable Vorbis bundles by changing only the serialized platform field.

The iPad source is read-only. Every decompressed file is retained byte for byte,
except the single BuildTarget integer. Recompression may change bundle hashes;
such results are explicitly distinguished from original Android MD5 matches.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import struct
import subprocess
import sys
import tarfile

sys.path[:0] = [str(ROOT), str(ROOT / 'offline-player')]
from source_assets import SourceAssets
from inspect_octo_index import fields
import UnityPy
from UnityPy.streams import EndianBinaryReader
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.54f1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-file', type=Path, required=True)
    parser.add_argument('--allow-verified-cache-variants', action='store_true')
    args = parser.parse_args()
    names = json.loads(args.selection_file.read_text(encoding='utf-8'))
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        raise ValueError('Invalid resource selection')
    build = WORK / 'build'
    known = set()
    for filename in ['local-snapshot.json', 'play-assets-supplement.json']:
        known.update(row[0] for row in json.loads((build / filename).read_text())['files'])
    wanted = set(names) - known
    records, by_id = {}, {}
    for n, wire, value in fields((ROOT / 'resource-analysis/android-octo-index.bin').read_bytes()):
        if n == 2:
            fs = list(fields(value))
            d = {k: v for k, w, v in fs}
            name = d[3].decode()
            by_id[d[1]] = name
            if name in wanted:
                records[name] = (d, [v for k, w, v in fs if k == 8])
    source = SourceAssets(allow_cache_variants=args.allow_verified_cache_variants)
    rows, proof, payloads = [], [], []
    for name in sorted(wanted):
        if not name.startswith('sound/audioclips/') or name not in records:
            raise ValueError('Only indexed AudioClip resources may be adapted: ' + name)
        env = source.load(name)
        if env is None:
            raise ValueError('Source audio not present: ' + name)
        types = {obj.type.name for obj in env.objects}
        if not types <= {'AssetBundle', 'AudioClip'} or 'AudioClip' not in types:
            raise ValueError('Non-audio object in selected bundle: ' + name)
        before = {obj.path_id: obj.read_typetree() for obj in env.objects}
        clips = [obj.read() for obj in env.objects if obj.type.name == 'AudioClip']
        if any(clip.m_CompressionFormat != 1 for clip in clips):
            raise ValueError('Audio codec is not portable Vorbis: ' + name)
        expected_files = {}
        for key, file in list(env.file.files.items()):
            raw = file.reader.bytes if hasattr(file, 'target_platform') else file.bytes
            if hasattr(file, 'target_platform'):
                if int(file.target_platform) != 9 or file.header.version < 9:
                    raise ValueError('Unexpected source serialized platform')
                start = 48 if file.header.version >= 22 else 20
                offset = raw.index(b'\0', start) + 1
                order = '<' if file.header.endian == '<' else '>'
                if struct.unpack_from(order + 'i', raw, offset)[0] != 9:
                    raise ValueError('Serialized platform field could not be located')
                raw = raw[:offset] + struct.pack(order + 'i', 13) + raw[offset + 4:]
                replacement = EndianBinaryReader(raw)
                replacement.flags = file.flags
                env.file.files[key] = replacement
            expected_files[key] = hashlib.sha256(raw).hexdigest()
        data = env.file.save(packer='original')
        test = UnityPy.load(data)
        after = {obj.path_id: obj.read_typetree() for obj in test.objects}
        if before != after:
            raise ValueError('Audio object metadata changed: ' + name)
        for key, file in test.file.files.items():
            raw = file.reader.bytes if hasattr(file, 'target_platform') else file.bytes
            if hasattr(file, 'target_platform') and int(file.target_platform) != 13:
                raise ValueError('Converted audio is not Android-targeted')
            if hashlib.sha256(raw).hexdigest() != expected_files[key]:
                raise ValueError('Decompressed audio bytes changed: ' + name)
        d, deps = records[name]
        wrapped = b'\x1f' + bytes(x ^ 255 for x in data[1:48]) + data[48:]
        exact = d[10].decode() in [hashlib.md5(data).hexdigest(), hashlib.md5(wrapped).hexdigest()]
        actual_deps=source.dependencies_for(name,[by_id[i] for i in deps],set(by_id.values()))
        rows.append([name, d[1], len(data), hashlib.sha256(data).hexdigest(), actual_deps])
        payloads.append((f'offline/payload/{d[1]}', data))
        proof.append({'name': name, 'id': d[1], 'bytes': len(data),
                      'original_android_md5_match': exact,
                      'validation': 'Only serialized BuildTarget changed; all audio metadata and stream bytes preserved',
                      'source_variant': source.variant_metadata.get(name)})
    source.close()
    path = build / 'audio-supplement.json'
    meta = json.loads(path.read_text()) if path.exists() else {
        'format': 1, 'kind': 'iPad_portable_Vorbis_platform_metadata_adaptation', 'files': []}
    merged = {row[0]: row for row in meta['files']}
    merged.update({row[0]: row for row in rows})
    meta['files'] = sorted(merged.values(), key=lambda row: row[0])
    encoded = json.dumps(meta, ensure_ascii=False, separators=(',', ':')).encode()
    path.write_bytes(encoded)
    proof_path = build / 'audio-platform-verification.json'
    old_proof = json.loads(proof_path.read_text()) if proof_path.exists() else []
    proof_rows = {row['name']: row for row in old_proof}
    proof_rows.update({row['name']: row for row in proof})
    proof_path.write_text(json.dumps(list(proof_rows.values()), indent=2), encoding='utf-8')
    adb = adb_args()
    process = subprocess.Popen(adb + ['exec-in', 'run-as', PACKAGE,
                                    'tar', '-xf', '-', '-C', 'files'], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdin, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
        for name, data in payloads + [('offline/audio-supplement.json', encoded)]:
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(data), 0o600
            tar.addfile(entry, io.BytesIO(data))
    process.stdin.close()
    if process.wait():
        raise ValueError('Phone transfer failed')
    checks = ''.join(f'{row[3]}  payload/{row[1]}\n' for row in rows).encode()
    result = subprocess.run(adb + ['shell', '-T', 'run-as', PACKAGE,
                                  'sh', '-c', "'cd files/offline && sha256sum -c -'"],
                            input=checks, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = result.stdout.decode().splitlines()
    if result.returncode or len(lines) != len(rows) or any(not x.endswith(': OK') for x in lines):
        raise ValueError('Phone audio SHA-256 verification failed')
    print(f'Imported {len(rows)} portable Vorbis bundles; preserved audio bytes; phone SHA-256 verified.')
    print('Original Android bundle MD5 matches:', sum(x['original_android_md5_match'] for x in proof))


if __name__ == '__main__':
    main()
