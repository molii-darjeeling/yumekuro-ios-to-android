from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Constrained shader port for original Spine cards with neutral material tint.

The original iOS normal/multiply programs must differ only by the documented
neutral tint and texture-transform expressions. Fragment programs must match
byte for byte. Android programs come from the shipped Android Spine/Skeleton.
Original multiply render states and shader properties are retained.
"""
import copy
import hashlib
from UnityPy.export.ShaderConverter import ShaderProgram
from UnityPy.helpers import CompressionHelper
from UnityPy.streams import EndianBinaryReader
import UnityPy


def metal_programs(obj):
    tree = obj.read_typetree()
    if tree['platforms'] != [14]:
        raise ValueError('Expected one original Metal shader platform')
    off, size, length = [tree[k][0][0] for k in ('offsets', 'compressedLengths', 'decompressedLengths')]
    raw = CompressionHelper.decompress_lz4(bytes(tree['compressedBlob'])[off:off + size], length)
    program = ShaderProgram(EndianBinaryReader(raw, endian='<'), (2021, 3, 56, 2))
    return [p for p in program.m_SubPrograms if int(p.m_ProgramType) in (23, 24)]


def normalize_neutral_vertex(text):
    return (text.replace('    float4 _Color;\n', '')
            .replace('    float4 _MainTex_ST;\n', '')
            .replace('    u_xlat0.xyz = VGlobals._Color.www * VGlobals._Color.xyz;\n'
                     '    u_xlat0.w = VGlobals._Color.w;\n'
                     '    output.COLOR0 = u_xlat0 * input.COLOR0;',
                     '    output.COLOR0 = input.COLOR0;')
            .replace('    output.TEXCOORD1.xy = fma(input.TEXCOORD0.xy, VGlobals._MainTex_ST.xy, VGlobals._MainTex_ST.zw);\n'
                     '    output.TEXCOORD1.z = 0.0;',
                     '    output.TEXCOORD1.xyz = input.TEXCOORD0.xyz;'))


def port(source, env, obj, android_normal_tree):
    old = obj.read_typetree()
    name = old['m_ParsedForm']['m_Name']
    if name != 'Spine/Blend Modes/Skeleton PMA Multiply':
        raise ValueError('Unsupported shader port')
    materials = []
    for item in env.objects:
        if item.type.name == 'Material':
            tree = item.read_typetree()
            if tree['m_Shader'] != {'m_FileID': 0, 'm_PathID': obj.path_id}:
                continue
            colors = dict(tree['m_SavedProperties']['m_Colors'])
            tint = colors.get('_Color', dict(r=1.0, g=1.0, b=1.0, a=1.0))
            if tint != dict(r=1.0, g=1.0, b=1.0, a=1.0):
                raise ValueError('Multiply port requires a neutral material tint')
            main = dict(tree['m_SavedProperties']['m_TexEnvs'])['_MainTex']
            if main['m_Scale'] != dict(x=1.0, y=1.0) or main['m_Offset'] != dict(x=0.0, y=0.0):
                raise ValueError('Multiply port requires an identity texture transform')
            materials.append(tree['m_Name'])
        elif item.type.name == 'AnimationClip':
            tree = item.read_typetree()
            for curve in tree.get('m_FloatCurves', []):
                attribute = curve.get('attribute', '').lower()
                if 'material' in attribute and ('color' in attribute or '_maintex' in attribute):
                    raise ValueError('Animated material parameters invalidate the shader port')
    if not materials:
        raise ValueError('Multiply material was not found')
    offset, size = source.db.execute("SELECT offset,size FROM members WHERE kind='app' "
        "AND name='./ProductName.app/Data/sharedassets0.assets'").fetchone()
    source.files['app'].seek(offset)
    original = UnityPy.load(source.files['app'].read(size))
    normal = next(o for o in original.objects if o.type.name == 'Shader'
                  and o.read_typetree().get('m_ParsedForm', {}).get('m_Name') == 'Spine/Skeleton')
    a, b = metal_programs(normal), metal_programs(obj)
    if len(a) != len(b):
        raise ValueError('Shader variant counts differ')
    fragment_hashes, vertices = [], 0
    for left, right in zip(a, b):
        if left.m_ProgramType != right.m_ProgramType or left.m_Keywords != right.m_Keywords:
            raise ValueError('Shader program/keyword mappings differ')
        if int(left.m_ProgramType) == 24:
            if left.m_ProgramCode != right.m_ProgramCode:
                raise ValueError('Original fragment programs differ')
            fragment_hashes.append(hashlib.sha256(right.m_ProgramCode).hexdigest())
        else:
            if normalize_neutral_vertex(right.Export()) != left.Export():
                raise ValueError('Original vertex math differs beyond neutral uniforms')
            vertices += 1
    tree = copy.deepcopy(android_normal_tree)
    tree['m_ParsedForm']['m_Name'] = name
    tree['m_ParsedForm']['m_PropInfo'] = old['m_ParsedForm']['m_PropInfo']
    aa, bb = tree['m_ParsedForm']['m_SubShaders'], old['m_ParsedForm']['m_SubShaders']
    if len(aa) != len(bb):
        raise ValueError('Original shader subshader counts differ')
    for adapted, original in zip(aa, bb):
        if len(adapted['m_Passes']) != len(original['m_Passes']):
            raise ValueError('Original shader pass counts differ')
        for ap, op in zip(adapted['m_Passes'], original['m_Passes']):
            if ap['m_Name'] != op['m_Name']:
                raise ValueError('Shader pass names differ')
            ap['m_State'] = copy.deepcopy(op['m_State'])
    raw = obj.save_typetree(tree)
    proof = {'strategy': 'original Android Spine/Skeleton GPU programs with original PMA multiply render states',
             'fixed_neutral_materials': materials, 'identical_fragment_sha256': fragment_hashes,
             'verified_neutral_vertex_variants': vertices}
    return raw, tree, proof
