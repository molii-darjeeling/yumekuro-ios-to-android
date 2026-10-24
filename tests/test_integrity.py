"""Synthetic checks only: no game files, credentials, device, or network required."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from repair_save_fields import decode, prepare
from local_asset_pack import check_row, validate_manifest
from export_ios import validate_container


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))

    def encrypt(self, value):
        data = json.dumps(value).encode(); pad = 16-len(data)%16
        cipher = Cipher(algorithms.AES(self.key[:16]), modes.CBC(self.key[16:])).encryptor()
        return cipher.update(data+bytes([pad])*pad)+cipher.finalize()

    def test_repair_preserves_new_progress(self):
        original = {'_userGuildList':[{'level':7}], '_userHomeConfigList':['original'], 'progress':{'chapter':1}}
        current = {'_userGuildList':[], '_userHomeConfigList':['current'], 'progress':{'chapter':9}}
        result, changed = prepare(self.encrypt(original), self.encrypt(current), self.key, ['_userGuildList'])
        expected = copy.deepcopy(current); expected['_userGuildList'] = original['_userGuildList']
        self.assertEqual(decode(result,self.key), expected)
        self.assertEqual(changed, ['_userGuildList'])

    def test_progress_repair_rejected(self):
        data = self.encrypt({'progress':1})
        with self.assertRaises(ValueError):
            prepare(data,data,self.key,['progress'])

    def test_corrupted_save_rejected(self):
        with self.assertRaises(ValueError):
            decode(b'x'*17,self.key)

    def test_pack_authentic_payload_and_mapping(self):
        payload = b'UnityFS\x00'+bytes(range(100))
        row = ['synthetic/resource',42,len(payload),hashlib.sha256(payload).hexdigest(),[]]
        catalog = {row[0]:{'id':42,'size':len(payload),'md5':hashlib.md5(payload).hexdigest(),'deps':[]}}
        check_row(row,payload,catalog)
        for position,value in [(1,43),(2,len(payload)+1),(3,'0'*64),(4,['unknown'])]:
            invalid = copy.deepcopy(row); invalid[position] = value
            with self.assertRaises(ValueError):
                check_row(invalid,payload,catalog)
        altered = b'UnityFS\x00'+b'Z'*100
        forged = copy.deepcopy(row); forged[3] = hashlib.sha256(altered).hexdigest()
        with self.assertRaises(ValueError):
            check_row(forged,altered,catalog)

    def test_pack_version_and_duplicates_rejected(self):
        profile = {'version_code':1,'abi':'arm64-v8a','sha256':{'resource-analysis/libil2cpp.so':'synthetic'}}
        row = ['synthetic/resource',42,8,'0'*64,[]]
        meta = {'format':1,'package':'com.gcrest.yumekuro','version_code':1,'abi':'arm64-v8a',
                'native_sha256':'synthetic','files':[row]}
        self.assertEqual(validate_manifest(meta,profile),[row])
        for patch in [{'version_code':2},{'files':[row,row]},{'native_sha256':'wrong'},{'package':'other'}]:
            invalid = copy.deepcopy(meta); invalid.update(patch)
            with self.assertRaises(ValueError):
                validate_manifest(invalid,profile)

    def test_container_scope(self):
        uid = '00000000-1111-2222-3333-444444444444'
        validate_container('/var/containers/Bundle/Application/'+uid,'app')
        validate_container('/private/var/mobile/Containers/Data/Application/'+uid,'data')
        for path in ['/var/mobile/Containers/Data/Application/', '/var/containers/Bundle/Application/'+uid+'/../', '/var/mobile']:
            with self.assertRaises(ValueError):
                validate_container(path,'data')


if __name__ == '__main__':
    unittest.main()
