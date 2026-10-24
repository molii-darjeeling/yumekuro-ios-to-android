"""Read-only SSH container export. No jailbreak, pairing, or installation is attempted."""
import argparse
from getpass import getpass
import hashlib
from pathlib import Path, PurePosixPath
import plistlib
import re
import shlex
import tarfile
import threading
import paramiko
from project import CONFIG, ROOT


def validate_container(remote, kind):
    prefix = {'app': 'containers/Bundle/Application', 'data': 'mobile/Containers/Data/Application'}.get(kind)
    if not prefix or not re.fullmatch(r'/(?:private/)?var/' + prefix + r'/[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}', remote):
        raise ValueError('Expected the exact app/data container UUID discovered on this device')


def export(client, remote, kind):
    validate_container(remote, kind)
    out = ROOT / 'exports/yumekuro-archives'
    out.mkdir(parents=True, exist_ok=True)
    final = out / (kind + '.tar')
    partial = out / (kind + '.tar.partial')
    if final.exists() or partial.exists():
        raise ValueError('Existing export found; verify/resume it deliberately instead of overwriting')
    command = ('for t in /var/jb/usr/bin/tar /var/jb/bin/tar /usr/bin/tar /bin/tar; '
               'do if [ -x "$t" ]; then exec "$t" -cf - -C ' + shlex.quote(remote) +
               ' .; fi; done; exit 127')
    _, stdout, stderr = client.exec_command(command)
    errors = bytearray()
    thread = threading.Thread(target=lambda: errors.extend(stderr.read()), daemon=True)
    thread.start()
    digest = hashlib.sha256()
    total = 0
    with partial.open('xb') as output:
        while block := stdout.read(1024**2):
            output.write(block)
            digest.update(block)
            total += len(block)
            if total // (256 * 1024**2) != (total - len(block)) // (256 * 1024**2):
                print(kind, 'received MiB', total // 1024**2, flush=True)
    code = stdout.channel.recv_exit_status()
    thread.join(timeout=10)
    if code:
        raise ValueError('Remote tar failed; partial retained. Inspect its private error log.')
    with tarfile.open(partial, 'r:') as archive:
        files = 0
        for entry in archive:
            path = PurePosixPath(entry.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unexpected archive member path')
            if entry.isfile():
                stream = archive.extractfile(entry)
                size = sum(len(b) for b in iter(lambda: stream.read(1024**2), b''))
                if size != entry.size:
                    raise ValueError('Truncated archive member')
                files += 1
    partial.rename(final)
    final.with_suffix('.sha256').write_text(digest.hexdigest() + '\n', encoding='ascii')
    print(kind, 'archive structurally verified;', files, 'files;', total, 'bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-container', required=True, help='Parent containing the verified .app directory')
    parser.add_argument('--data-container', required=True)
    args = parser.parse_args()
    validate_container(args.app_container, 'app')
    validate_container(args.data_container, 'data')
    known = ROOT / 'private/ssh_known_hosts'
    if not known.is_file():
        raise ValueError('Verify the device SSH host key and save private/ssh_known_hosts first. See the runbook.')
    client = paramiko.SSHClient()
    client.load_host_keys(str(known))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(CONFIG.get('ios_ssh_host', '127.0.0.1'),
                       port=int(CONFIG.get('ios_ssh_port', 2222)),
                       username=CONFIG.get('ios_ssh_user', 'mobile'),
                       password=getpass('Device terminal password (not Apple Account password): '),
                       allow_agent=False, look_for_keys=False, timeout=20)
        with client.open_sftp() as sftp:
            apps = [name for name in sftp.listdir(args.app_container) if name.endswith('.app')]
            if len(apps) != 1:
                raise ValueError('Expected exactly one discovered app bundle')
            with sftp.open(args.app_container + '/' + apps[0] + '/Info.plist', 'rb') as stream:
                info = plistlib.loads(stream.read())
            with sftp.open(args.data_container + '/.com.apple.mobile_container_manager.metadata.plist', 'rb') as stream:
                identity = plistlib.loads(stream.read())
            if info.get('CFBundleIdentifier') != 'com.gcrest.yumekuro' or identity.get('MCMMetadataIdentifier') != 'com.gcrest.yumekuro':
                raise ValueError('App/data container identity mismatch')
        export(client, args.app_container, 'app')
        export(client, args.data_container, 'data')
    finally:
        client.close()


if __name__ == '__main__':
    main()
