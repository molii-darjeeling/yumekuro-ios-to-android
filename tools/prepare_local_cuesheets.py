from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Port original AudioClipSoundCueSheet bundles without rewriting their data.

Only the serialized BuildTarget changes. Every descriptor object, external
reference, cue/track setting and decompressed file is verified unchanged.
Outputs stream to the phone; the original archives remain read-only.
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-file', type=Path, required=True)
    parser.add_argument('--allow-verified-cache-variants', action='store_true')
    args = parser.parse_args()
    selected = json.loads(args.selection_file.read_text(encoding='utf-8'))
    if not isinstance(selected, list) or any(not isinstance(n, str) for n in selected):
        raise ValueError('Selection must contain logical cue sheet names')
    build = WORK / 'build'
    known = {}
    for filename in ['local-snapshot.json', 'metadata-supplement.json',
                     'audio-supplement.json', 'visual-supplement.json',
                     'play-assets-supplement.json']:
        known.update({r[0]: r for r in json.loads((build / filename).read_text())['files']})
    records, by_id = {}, {}
    for number, _, value in fields((ROOT / 'resource-analysis/android-octo-index.bin').read_bytes()):
        if number != 2:
            continue
        fs = list(fields(value))
        d = {k: v for k, _, v in fs}
        name = d[3].decode()
        by_id[d[1]] = name
        if name in selected:
            records[name] = d, [v for k, _, v in fs if k == 8]
    source = SourceAssets(allow_cache_variants=args.allow_verified_cache_variants)
    rows, proofs, payloads = [], [], []
    for name in sorted(set(selected) - set(known)):
        if not name.startswith(('sound/cuesheet/', 'sound/cuesheetoptional/')) or name not in records:
            raise ValueError('Resource is not an indexed cue sheet: ' + name)
        d, ids = records[name]
        dependencies = [by_id[i] for i in ids]
        env = source.load(name)
        if env is None:
            raise ValueError('Cue sheet missing in original export: ' + name)
        dependencies=source.dependencies_for(name,dependencies,set(by_id.values()))
        missing = [n for n in dependencies if n not in known]
        if missing:
            raise ValueError('Cue sheet has missing local audio: ' + name + ': ' + str(missing))
        types = {o.type.name for o in env.objects}
        if types != {'AssetBundle', 'MonoBehaviour', 'MonoScript'}:
            raise ValueError('Unexpected cue sheet objects: ' + name + ': ' + str(types))
        before = {o.path_id: o.read_typetree() for o in env.objects}
        scripts = [o for o in env.objects if o.type.name == 'MonoScript']
        if len(scripts) != 1:
            raise ValueError('Unexpected cue sheet script count')
        script = before[scripts[0].path_id]
        if (script['m_ClassName'], script['m_Namespace'], script['m_AssemblyName']) != (
                'AudioClipSoundCueSheet', 'Sge.Sound', 'SGE-Sound.Runtime.dll'):
            raise ValueError('Unsupported cue sheet script')
        descriptors = [before[o.path_id] for o in env.objects if o.type.name == 'MonoBehaviour']
        # Original resource paths and runtime sheet names can be aliases:
        # subgameruntop contains SubgameRunTop with cueSheetName "Rungame".
        # The source index/hash identifies the resource; preserve that alias.
        if len(descriptors) != 1 or not isinstance(descriptors[0].get('cueSheetName'), str) or not descriptors[0]['cueSheetName']:
            raise ValueError('Invalid original cue sheet descriptor: ' + name)
        if descriptors[0]['m_Script'] != {'m_FileID': 0, 'm_PathID': scripts[0].path_id}:
            raise ValueError('Cue sheet does not reference its original local script')
        expected = {}
        for key, file in list(env.file.files.items()):
            raw = file.reader.bytes if hasattr(file, 'target_platform') else file.bytes
            if hasattr(file, 'target_platform'):
                if int(file.target_platform) != 9 or file.header.version < 9:
                    raise ValueError('Unexpected source platform')
                offset = raw.index(b'\0', 48 if file.header.version >= 22 else 20) + 1
                order = '<' if file.header.endian == '<' else '>'
                if struct.unpack_from(order + 'i', raw, offset)[0] != 9:
                    raise ValueError('Source platform field was not found')
                raw = raw[:offset] + struct.pack(order + 'i', 13) + raw[offset + 4:]
                replacement = EndianBinaryReader(raw)
                replacement.flags = file.flags
                env.file.files[key] = replacement
            expected[key] = hashlib.sha256(raw).hexdigest()
        data = env.file.save(packer='original')
        test = UnityPy.load(data)
        if before != {o.path_id: o.read_typetree() for o in test.objects}:
            raise ValueError('Cue/track data or external object references changed')
        for key, file in test.file.files.items():
            raw = file.reader.bytes if hasattr(file, 'target_platform') else file.bytes
            if hasattr(file, 'target_platform') and int(file.target_platform) != 13:
                raise ValueError('Output is not Android-targeted')
            if hashlib.sha256(raw).hexdigest() != expected[key]:
                raise ValueError('Decompressed descriptor bytes changed')
        wrapped = b'\x1f' + bytes(x ^ 255 for x in data[1:48]) + data[48:]
        exact = d[10].decode() in (hashlib.md5(data).hexdigest(), hashlib.md5(wrapped).hexdigest())
        rows.append([name, d[1], len(data), hashlib.sha256(data).hexdigest(), dependencies])
        payloads.append((f'offline/payload/{d[1]}', data))
        proofs.append({'name': name, 'id': d[1], 'bytes': len(data),
                       'cues': len(descriptors[0]['cues']), 'dependencies': len(dependencies),
                       'original_object_name': descriptors[0]['m_Name'],
                       'original_runtime_sheet_name': descriptors[0]['cueSheetName'],
                       'original_android_md5_match': exact,
                       'validation': 'Only serialized BuildTarget changed; all cue/track and external reference bytes retained',
                       'source_variant': source.variant_metadata.get(name)})
    source.close()
    path = build / 'cuesheet-supplement.json'
    meta = json.loads(path.read_text()) if path.exists() else {
        'format': 1, 'kind': 'iPad_original_cuesheets_platform_metadata_adaptation', 'files': []}
    merged = {r[0]: r for r in meta['files']}
    merged.update({r[0]: r for r in rows})
    meta['files'] = sorted(merged.values(), key=lambda r: r[0])
    encoded = json.dumps(meta, ensure_ascii=False, separators=(',', ':')).encode()
    adb = adb_args()
    process = subprocess.Popen(adb + ['exec-in', 'run-as', PACKAGE,
        'tar', '-xf', '-', '-C', 'files'], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdin, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
        for filename, content in payloads + [('offline/cuesheet-supplement.json', encoded)]:
            entry = tarfile.TarInfo(filename)
            entry.size, entry.mode = len(content), 0o600
            tar.addfile(entry, io.BytesIO(content))
    process.stdin.close()
    if process.wait():
        raise ValueError('Phone transfer failed')
    checks = ''.join(f'{r[3]}  payload/{r[1]}\n' for r in rows).encode()
    result = subprocess.run(adb + ['shell', '-T', 'run-as', PACKAGE,
        'sh', '-c', "'cd files/offline && sha256sum -c -'"], input=checks, capture_output=True)
    lines = result.stdout.decode().splitlines()
    if result.returncode or len(lines) != len(rows) or any(not line.endswith(': OK') for line in lines):
        raise ValueError('Phone descriptor SHA-256 verification failed')
    path.write_bytes(encoded)
    proof_path = build / 'cuesheet-platform-verification.json'
    prior = json.loads(proof_path.read_text()) if proof_path.exists() else []
    merged_proof = {r['name']: r for r in prior}
    merged_proof.update({r['name']: r for r in proofs})
    proof_path.write_text(json.dumps(list(merged_proof.values()), indent=2), encoding='utf-8')
    print(f'Imported {len(rows)} original cue sheets, {sum(r[2] for r in rows)} bytes; phone SHA-256 verified.')
    print('Original Android bundle MD5 matches:', sum(r['original_android_md5_match'] for r in proofs))


if __name__ == '__main__':
    main()
