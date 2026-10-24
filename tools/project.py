"""Local paths and device selection. Importing this module never contacts a device."""
from pathlib import Path
import hashlib
import json
import os
import re

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get('YUMEKURO_CONFIG', REPO / 'local-config.json'))
CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf8')) if CONFIG_PATH.exists() else {}
ROOT = Path(os.environ.get('YUMEKURO_WORKDIR', CONFIG.get('work_dir', REPO / 'work'))).resolve()
WORK = ROOT / 'native-offline'
BUILD = WORK / 'build'
ADB = str(CONFIG.get('adb', 'adb'))
PACKAGE = CONFIG.get('package', 'com.yumekuro.local')
if int(CONFIG.get('android_user', 0)) != 0:
    raise ValueError('This native profile supports Android user 0 only; other profiles require path adaptation')
if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}', PACKAGE) or PACKAGE == 'com.gcrest.yumekuro':
    raise ValueError('Choose a separate local package name; never target the official app')


def adb_args():
    serial = CONFIG.get('android_serial', '')
    if not re.fullmatch(r'[A-Za-z0-9._:-]+', serial) or serial == 'CHOOSE_YOUR_DEVICE':
        raise ValueError('Select the intended Android serial in local-config.json first')
    return [ADB, '-P', str(int(CONFIG.get('adb_port', 5037))), '-s', serial]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024**2):
            digest.update(block)
    return digest.hexdigest()


def require_profile():
    profile = json.loads((REPO / 'profiles/yumekuro-5.0.1-arm64.json').read_text())
    for relative, expected in profile['sha256'].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError('Unsupported input build: ' + relative + '. Re-map native offsets before proceeding.')
    return profile
