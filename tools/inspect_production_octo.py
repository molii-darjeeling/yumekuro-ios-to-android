from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Inspect shipped Android Production settings; never print secret fields."""
from pathlib import Path
import struct
import zipfile
import UnityPy

ENTRY = 'assets/bin/Data/b90345c910aed41ca8dd60ee3b92e4e3'


def production_settings():
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.54f1'
    with zipfile.ZipFile(ROOT / 'android-original/base.apk') as archive:
        environment = UnityPy.load(archive.read(ENTRY))
    for obj in environment.objects:
        if obj.type.name != 'MonoBehaviour':
            continue
        raw = obj.get_raw_data()
        position = 28

        def string_field():
            nonlocal position
            size = struct.unpack_from('<i', raw, position)[0]
            assert 0 <= size <= len(raw) - position - 4
            value = raw[position + 4:position + 4 + size]
            position = (position + 4 + size + 3) // 4 * 4
            return value

        if string_field() != b'Production':
            continue
        string_field()  # API URL
        app_id = struct.unpack_from('<i', raw, position)[0]
        position += 4
        for _ in range(3):
            string_field()  # Client secret, AES key, optional A
        caching_type = raw[position]
        version = struct.unpack_from('<i', raw, position + 4)[0]
        return app_id, caching_type, version
    raise ValueError('Production settings not found in this APK version')


if __name__ == '__main__':
    app_id, caching_type, version = production_settings()
    print('Production appId:', app_id)
    print('CachingType:', caching_type)
    print('Production Version:', version)
