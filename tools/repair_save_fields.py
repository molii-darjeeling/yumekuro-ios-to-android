"""Prepare a minimal local save repair. Never uploads a save or discovers keys."""
import argparse
import json
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ALLOWED = {'_userHomeConfigList', '_userGuildList'}


def decode(data, key):
    if len(key) != 32 or not data or len(data) % 16:
        raise ValueError('Unrecognized key or save length')
    decoder=Cipher(algorithms.AES(key[:16]),modes.CBC(key[16:])).decryptor()
    clear=decoder.update(data)+decoder.finalize();pad=clear[-1]
    if not 1<=pad<=16 or clear[-pad:]!=bytes([pad])*pad:
        raise ValueError('Save padding mismatch')
    result=json.loads(clear[:-pad])
    if not isinstance(result,dict):
        raise ValueError('Expected a save object')
    return result


def prepare(original, current, key, fields):
    fields=set(fields)
    if not fields or not fields<=ALLOWED:
        raise ValueError('Only a diagnosed home/guild filtering repair is supported')
    source, before=decode(original,key),decode(current,key)
    repaired=json.loads(json.dumps(before))
    for name in fields:
        if name not in source or name not in before or not isinstance(source[name],list):
            raise ValueError('Unexpected save schema')
        repaired[name]=source[name]
    changed={name for name in set(before)|set(repaired) if before.get(name)!=repaired.get(name)}
    if not changed<=fields:
        raise ValueError('An unrelated progress field would change')
    data=json.dumps(repaired,ensure_ascii=False,separators=(',',':')).encode()
    pad=16-len(data)%16
    encoder=Cipher(algorithms.AES(key[:16]),modes.CBC(key[16:])).encryptor()
    encoded=encoder.update(data+bytes([pad])*pad)+encoder.finalize()
    if decode(encoded,key)!=repaired:
        raise ValueError('Repair encryption round-trip failed')
    return encoded,sorted(changed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ['original','current','key','output']:
        parser.add_argument('--'+flag,type=Path,required=True)
    parser.add_argument('--field',action='append',required=True,choices=sorted(ALLOWED))
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new private output path')
    encoded,changed=prepare(args.original.read_bytes(),args.current.read_bytes(),args.key.read_bytes(),args.field)
    args.output.write_bytes(encoded)
    print('Prepared local-only repair. Changed fields:',','.join(changed) or 'none')
    print('No device write performed; verify prerequisite assets, retain the current encrypted backup, then deploy deliberately.')


if __name__=='__main__':
    main()
