"""Private Google Play metadata probe; never downloads APKs automatically.

All credentials and raw authenticated responses stay under the private workspace.
Pairing codes are read from stdin, never command-line arguments.
"""
from __future__ import annotations
from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

PRIVATE = WORK / 'private-googleplay-auth'
os.environ.setdefault('TMP', str(BUILD))
os.environ.setdefault('TEMP', str(BUILD))

import httpx
import gplaydl.auth as auth

auth.CONFIG_DIR = PRIVATE
auth._LINK_PATH = PRIVATE / 'config.json'

from gplaydl import api, onboarding

PACKAGE = 'com.gcrest.yumekuro'


def store(name: str, value) -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    target = PRIVATE / name
    if isinstance(value, bytes):
        target.write_bytes(value)
    else:
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'link', 'query'])
    parser.add_argument('--version', type=int, default=0)
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps({'config_directory': str(PRIVATE),
                          'linked': bool(auth.api_key_for(auth.dispenser_base()))}))
        return 0
    if args.action == 'link':
        code = sys.stdin.readline().strip()
        if not code:
            print('A one-time app pairing code is required on stdin.')
            return 2
        key = onboarding._claim(auth.DEFAULT_DISPENSER, code)
        auth.save_link(auth.DEFAULT_DISPENSER, key)
        print('Pairing succeeded. Credentials saved privately in the local workspace.')
        return 0
    if not auth.api_key_for(auth.dispenser_base()):
        print('Waiting for the user to complete app pairing.')
        return 2
    credentials = auth.ensure_auth(arch='arm64')
    if not credentials:
        print('The linked service did not provide a Google Play token.')
        return 3
    raw_details = api._fetch_details_raw(PACKAGE, credentials)
    store('yumekuro-details.pb', raw_details)
    details = api._parse_details_proto(raw_details)
    version = args.version or details.version_code
    print(json.dumps({'title': details.title, 'version': details.version_string,
                      'version_code': details.version_code, 'requested_version': version},
                     ensure_ascii=False))
    if not version:
        print('No package version returned for this account/device profile.')
        return 4
    delivery_token = api.purchase(PACKAGE, version, credentials)
    params = {'doc': PACKAGE, 'ot': '1', 'vc': str(version)}
    if delivery_token:
        params['dtok'] = delivery_token
    response = httpx.get(api.DELIVERY_URL, headers=api._proto_headers(credentials),
                         params=params, timeout=45)
    store('yumekuro-delivery.pb', response.content)
    print(f'Delivery HTTP status: {response.status_code}')
    if response.status_code != 200:
        return 5
    result = api._parse_delivery(response.content)
    store('yumekuro-delivery-private.json', dataclasses.asdict(result))
    safe = {'base_size': result.download_size,
            'base_available': bool(result.download_url),
            'splits': [{'name': s.name, 'size': s.size} for s in result.splits],
            'additional_files': [{'type': f.file_type, 'size': f.size,
                                  'version_code': f.version_code}
                                 for f in result.additional_files],
            'delivery_status': api._first_int(api._navigate(response.content, 1, 21), 1)}
    store('yumekuro-delivery-summary.json', safe)
    print(json.dumps(safe, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except auth.DispenserError as exc:
        print(f'Authorization service refused the request (HTTP {exc.status}).')
        raise SystemExit(10)
    except httpx.HTTPStatusError as exc:
        print(f'HTTP request failed: {exc.response.status_code}')
        raise SystemExit(11)
    except httpx.HTTPError as exc:
        # Some exception strings contain authenticated URLs; do not print them.
        print(f'Network request failed: {type(exc).__name__}')
        raise SystemExit(12)
    except api.PlayAPIError as exc:
        print(f'Google Play metadata request failed: {type(exc).__name__}')
        raise SystemExit(13)
