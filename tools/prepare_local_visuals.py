from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Adapt original iPad visual/text bundles, using original Android shaders.

Textures, sprites, prefab objects, and resource streams remain unchanged.
Adaptations are explicitly separate from exact Android bundle reconstructions.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile

BUILD = WORK / 'build'
sys.path[:0] = [str(ROOT), str(ROOT / 'offline-player')]
from source_assets import SourceAssets
from inspect_octo_index import fields
import UnityPy
from UnityPy.enums import BuildTarget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-file', type=Path, required=True)
    parser.add_argument('--skip-unsupported-shaders', action='store_true',
                        help='Import compatible resources and record unsupported shader names separately')
    parser.add_argument('--allow-verified-cache-variants', action='store_true')
    parser.add_argument('--defer-invalid-resources', action='store_true')
    parser.add_argument('--replace-existing', action='store_true')
    args = parser.parse_args()
    names = json.loads(args.selection_file.read_text(encoding='utf-8'))
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        raise ValueError('Invalid resource selection')
    known = set()
    for filename in ['local-snapshot.json', 'play-assets-supplement.json']:
        known.update(r[0] for r in json.loads((BUILD / filename).read_text())['files'])
    if not args.replace_existing and (BUILD/'visual-supplement.json').exists():
        known.update(r[0] for r in json.loads((BUILD/'visual-supplement.json').read_text())['files'])
    wanted = set(names) - known
    if not wanted:
        print('Selection already imported; no resource writes needed.')
        return
    records, by_id = {}, {}
    for n, wire, value in fields((ROOT / 'resource-analysis/android-octo-index.bin').read_bytes()):
        if n == 2:
            fs = list(fields(value))
            d = {k: v for k, w, v in fs}
            name = d[3].decode()
            by_id[d[1]] = name
            if name in wanted:
                records[name] = (d, [v for k, w, v in fs if k == 8])
    inventory = json.loads((BUILD / 'android-shader-inventory.json').read_text())['shaders']
    shader_locations = {r['name']: r for r in inventory}
    shaders = {}
    original_apk = zipfile.ZipFile(ROOT / 'android-original/base.apk')
    original_files = {}

    def android_shader(name):
        if name in shaders:
            return shaders[name]
        if name not in shader_locations:
            raise ValueError('No same-name original Android shader: ' + name)
        loc = shader_locations[name]
        path = loc['path']
        if path not in original_files:
            if path in original_apk.namelist():
                data = original_apk.read(path)
            else:
                parts = sorted((int(n.rsplit('.split', 1)[1]), n)
                               for n in original_apk.namelist() if n.startswith(path + '.split'))
                if not parts:
                    raise ValueError('Original shader serialized file is absent')
                data = b''.join(original_apk.read(n) for _, n in parts)
            original_files[path] = UnityPy.load(data)
        obj = next(o for o in original_files[path].objects if o.path_id == loc['path_id'])
        tree = obj.read_typetree()
        if not tree.get('platforms') or 14 in tree['platforms']:
            raise ValueError('Shader does not contain verified Android programs')
        shaders[name] = (obj.get_raw_data(), tree, path, loc['path_id'], obj.assets_file)
        return shaders[name]

    def remap_shader_references(tree, original_file, target_file):
        updated = copy.deepcopy(tree)
        remappings = []
        def walk(value):
            if isinstance(value, dict):
                if 'm_FileID' in value and 'm_PathID' in value and value['m_PathID']:
                    file_id = value['m_FileID']
                    if file_id <= 0:
                        raise ValueError('Shader references an original internal object that must be imported explicitly')
                    original_path = original_file.externals[file_id - 1].path
                    matches = [i + 1 for i, external in enumerate(target_file.externals)
                               if external.path == original_path]
                    if len(matches) != 1:
                        raise ValueError('Shader external file is not uniquely present in target: ' + original_path)
                    value['m_FileID'] = matches[0]
                    remappings.append({'external_path': original_path, 'path_id': value['m_PathID'],
                                       'from_file_id': file_id, 'to_file_id': matches[0]})
                else:
                    for child in value.values():
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        # Only object references change. Compiled programs, material properties,
        # render states, and every other Shader field retain original Android data.
        for key in ['m_Dependencies', 'm_NonModifiableTextures']:
            walk(updated.get(key, []))
        return updated, remappings

    source = SourceAssets(allow_cache_variants=args.allow_verified_cache_variants)
    rows, proof, payloads, skipped = [], [], [], []
    def prepare_one(name):
        if name not in records or not name.startswith(('unit/', 'gallery/', 'spine/', 'guildspine/', 'guildhouse/', 'battle/units/', 'battle/bullets/', 'effectlibrarys/03_meshs/', 'story/scripts/', 'story/background/', 'effectlibrarys/02_materials/', 'effectlibrarys/00_purchase/', 'actor/atlas/', 'background/', 'story/effect/', 'panelbackgroundliveimage/', 'effectsoutgame/', 'fairysd/', 'effects/', 'effectlibrarys/01_textures/')):
            raise ValueError('Only indexed original visual resources may be adapted: ' + name)
        env = source.load(name)
        if env is None:
            raise ValueError('Original iPad visual is absent: ' + name)
        if args.skip_unsupported_shaders:
            unsupported = []
            for shader in env.objects:
                if shader.type.name != 'Shader':
                    continue
                tree = shader.read_typetree()
                shader_name = tree.get('m_ParsedForm', {}).get('m_Name') or tree.get('m_Name')
                if shader_name not in shader_locations and shader_name != 'Spine/Blend Modes/Skeleton PMA Multiply':
                    unsupported.append(shader_name)
            if unsupported:
                skipped.append({'name': name, 'unsupported_shaders': unsupported})
                return None
        if any(o.type.name == 'ComputeShader' for o in env.objects):
            raise ValueError('Compute shaders require a separate verified platform conversion: ' + name)
        if name.startswith('story/scripts/') and any(o.type.name not in ('AssetBundle', 'TextAsset') for o in env.objects):
            raise ValueError('Story script contains an unexpected object: ' + name)
        if name.startswith('story/background/') and any(
                o.type.name not in ('AssetBundle', 'Texture2D', 'Sprite') for o in env.objects):
            raise ValueError('Story background contains an unexpected object: ' + name)
        if name.startswith(('effectlibrarys/02_materials/', 'effectlibrarys/00_purchase/')) and any(
                o.type.name not in ('AssetBundle', 'Material', 'Shader', 'Texture2D', 'Sprite') for o in env.objects):
            raise ValueError('Effect material/texture contains an unexpected object: ' + name)
        if name.startswith('effectlibrarys/03_meshs/') and any(
                o.type.name not in ('AssetBundle', 'Mesh', 'MeshFilter', 'MeshRenderer',
                                   'GameObject', 'Transform', 'Material', 'Shader') for o in env.objects):
            raise ValueError('A portable mesh bundle contains an unexpected object')
        original_objects = {o.path_id: o.get_raw_data() for o in env.objects}
        original_streams = {k: hashlib.sha256(f.bytes).hexdigest()
                            for k, f in env.file.files.items() if not hasattr(f, 'target_platform')}
        replaced, expected_shaders = {}, {}
        for obj in env.objects:
            if obj.type.name == 'Shader':
                old = obj.read_typetree()
                shader_name = old.get('m_ParsedForm', {}).get('m_Name') or old.get('m_Name')
                extra = {}
                if shader_name == 'Spine/Blend Modes/Skeleton PMA Multiply':
                    from port_spine_multiply import port
                    _, normal, path, path_id, _ = android_shader('Spine/Skeleton')
                    raw, tree, extra = port(source, env, obj, normal)
                else:
                    raw, tree, path, path_id, original_file = android_shader(shader_name)
                    if old['m_ParsedForm']['m_PropInfo'] != tree['m_ParsedForm']['m_PropInfo']:
                        raise ValueError('Original shader property definitions differ: ' + shader_name)
                    if tree.get('m_Dependencies') or tree.get('m_NonModifiableTextures'):
                        original_hash = hashlib.sha256(raw).hexdigest()
                        tree, references = remap_shader_references(tree, original_file, obj.assets_file)
                        raw = obj.save_typetree(tree)
                        extra = {'original_android_shader_sha256': original_hash,
                                 'external_reference_remapping': references}
                    else:
                        # Old cached bundles can have a different Shader type
                        # layout even with identical property definitions.
                        # Serialize the full Android tree through this object's
                        # actual schema; never reinterpret foreign raw bytes.
                        # The reload below must retain the entire tree exactly.
                        raw = obj.save_typetree(tree)
                expected_shaders[obj.path_id] = tree
                replaced[obj.path_id] = {'name': shader_name, 'apk_entry': path,
                                         'original_path_id': path_id,
                                         'sha256': hashlib.sha256(raw).hexdigest(), **extra}
        for file in env.file.files.values():
            if hasattr(file, 'target_platform'):
                if int(file.target_platform) != 9:
                    raise ValueError('Unexpected source target platform')
                file.target_platform = BuildTarget.Android
                file._m_target_platform = int(BuildTarget.Android)
                file.mark_changed()
        data = env.file.save(packer='original')
        check = UnityPy.load(data)
        checked_objects = {o.path_id: o for o in check.objects}
        if set(checked_objects) != set(original_objects):
            raise ValueError('Visual object IDs changed')
        for path_id, raw in original_objects.items():
            obj = checked_objects[path_id]
            if path_id in replaced:
                if hashlib.sha256(obj.get_raw_data()).hexdigest() != replaced[path_id]['sha256']:
                    raise ValueError('Android shader bytes changed after repacking')
                # Parse again after repacking: ObjectReader reads its original
                # reader until a new serialized file is loaded.
                if obj.read_typetree() != expected_shaders[path_id]:
                    raise ValueError('Original Android shader serialization is incompatible')
            elif obj.get_raw_data() != raw:
                raise ValueError('Non-shader object changed: ' + obj.type.name)
        for key, file in check.file.files.items():
            if hasattr(file, 'target_platform'):
                if int(file.target_platform) != 13:
                    raise ValueError('Visual serialized target was not adapted')
            elif hashlib.sha256(file.bytes).hexdigest() != original_streams[key]:
                raise ValueError('Texture/resource stream bytes changed')
        d, deps = records[name]
        real_deps=source.dependencies_for(name,[by_id[i] for i in deps],set(by_id.values()))
        row = [name, d[1], len(data), hashlib.sha256(data).hexdigest(), real_deps]
        payload = (f'offline/payload/{d[1]}', data)
        item_proof = {'name': name, 'id': d[1], 'bytes': len(data),
                      'original_android_md5_match': False,
                      'validation': 'All non-shader objects and resource streams byte-identical; '
                                    'Android BuildTarget; original Android shader programs where present',
                      'shaders': list(replaced.values()),
                      'source_variant': source.variant_metadata.get(name)}
        return row, payload, item_proof
    for name in sorted(wanted):
        try:
            result=prepare_one(name)
        except (ValueError, EOFError, KeyError, AssertionError, StopIteration) as error:
            if not args.defer_invalid_resources:
                raise
            skipped.append({'name':name,'reason':type(error).__name__+': '+str(error)})
            print('Deferred original visual:',name,type(error).__name__,flush=True)
            continue
        if result is not None:
            row,payload,item_proof=result
            rows.append(row);payloads.append(payload);proof.append(item_proof)
            print('Prepared original visual:',name,flush=True)
    source.close()
    original_apk.close()
    meta_path = BUILD / 'visual-supplement.json'
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {
        'format': 1, 'kind': 'iPad_original_visuals_with_original_Android_shaders', 'files': []}
    merged = {r[0]: r for r in meta['files']}
    merged.update({r[0]: r for r in rows})
    meta['files'] = sorted(merged.values(), key=lambda r: r[0])
    encoded = json.dumps(meta, ensure_ascii=False, separators=(',', ':')).encode()
    meta_path.write_bytes(encoded)
    proof_path = BUILD / 'visual-platform-verification.json'
    old_proof = json.loads(proof_path.read_text()) if proof_path.exists() else []
    merged_proof = {r['name']: r for r in old_proof}
    merged_proof.update({r['name']: r for r in proof})
    proof_path.write_text(json.dumps(list(merged_proof.values()), ensure_ascii=False, indent=2), encoding='utf-8')
    adb = adb_args()
    process = subprocess.Popen(adb + ['exec-in', 'run-as', PACKAGE,
                                    'tar', '-xf', '-', '-C', 'files'], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdin, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
        for path, data in payloads + [('offline/visual-supplement.json', encoded)]:
            entry = tarfile.TarInfo(path)
            entry.size, entry.mode = len(data), 0o600
            tar.addfile(entry, io.BytesIO(data))
    process.stdin.close()
    if process.wait():
        raise ValueError('Visual transfer to phone failed')
    checks = ''.join(f'{r[3]}  payload/{r[1]}\n' for r in rows).encode()
    result = subprocess.run(adb + ['shell', '-T', 'run-as', PACKAGE,
                                  'sh', '-c', "'cd files/offline && sha256sum -c -'"],
                            input=checks, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = result.stdout.decode().splitlines()
    if result.returncode or len(lines) != len(rows) or any(not x.endswith(': OK') for x in lines):
        raise ValueError('Phone visual SHA-256 verification failed')
    print(f'Imported and phone-verified {len(rows)} original visual adaptations.')
    if args.skip_unsupported_shaders or args.defer_invalid_resources:
        (BUILD / 'visual-platform-skipped.json').write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Resources reserved for explicit shader adaptation:', len(skipped))


if __name__ == '__main__':
    main()
