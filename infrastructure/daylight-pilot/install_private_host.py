#!/usr/bin/env python3
"""D194 private staging/TLS only. No listener, model call or traffic activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import tarfile
import tempfile

SHA = 'aaa19850dd02ccd61b25f633e170bc8f01d0321cbe26e5b1715874e2cfe3ec42'
BUCKET = 'daylight-pilot-foundation-backupbucket-zmzwmrv5ebp3'
KEY = 'deployment/rehearsal/' + SHA + '.tar.gz'
CERT = 'arn:aws:acm:us-east-1:020055445580:certificate/7dc53f28-855c-46c1-8683-81b3f6661957'
TLS = Path('/etc/daylight-pilot/tls')


def run(*args, input=None):
    # Capture both streams: certificate export/passin values must never enter SSM logs.
    value = subprocess.run(args, input=input, capture_output=True, check=False)
    if value.returncode:
        raise RuntimeError('Command failed: ' + args[0] + ' ' + args[1])
    return value.stdout


def aws(*args):
    return run('aws', '--region', 'us-east-1', '--no-cli-pager', *args)


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Private directory is not a regular directory.')
    path.chmod(0o700)


def inspect_archive(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Archive SHA-256 mismatch.')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or len(names) > 1000:
            raise ValueError('Duplicate or excessive archive members.')
        if sum(m.size for m in members) > 128 * 1024 * 1024:
            raise ValueError('Expanded archive exceeds bound.')
        for m in members:
            p = PurePosixPath(m.name)
            if (not m.isfile() or p.is_absolute() or '..' in p.parts
                    or str(p) != m.name or not m.name):
                raise ValueError('Unsafe archive member.')
        manifest = json.load(archive.extractfile('release-manifest.json'))
        if manifest['scope'] != 'fictional_display_rehearsal':
            raise ValueError('Unexpected artifact scope.')
        inventory = manifest['files_sha256']
        if set(names) != set(inventory) | {'release-manifest.json'}:
            raise ValueError('Unmanifested artifact file.')
        for name, sha in inventory.items():
            if hashlib.sha256(archive.extractfile(name).read()).hexdigest() != sha:
                raise ValueError('Artifact member SHA-256 mismatch.')
        return inventory


def stage():
    root = Path('/opt/daylight-pilot')
    private_dir(root)
    archive = root / (SHA + '.tar.gz')
    if not archive.exists():
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            download = Path(tmp) / 'download.tar.gz'
            aws('s3api', 'get-object', '--bucket', BUCKET, '--key', KEY, str(download))
            inspect_archive(download, SHA)
            download.chmod(0o600)
            os.replace(download, archive)
    inventory = inspect_archive(archive, SHA)
    releases = root / 'releases'
    private_dir(releases)
    target = releases / SHA
    if target.exists():
        if target.is_symlink() or any(hashlib.sha256((target / name).read_bytes()).hexdigest() != sha
                                      for name, sha in inventory.items()):
            raise ValueError('Existing release differs; never overwrite it.')
    else:
        with tempfile.TemporaryDirectory(dir=releases) as tmp:
            contents = Path(tmp) / 'contents'
            private_dir(contents)
            with tarfile.open(archive, 'r:gz') as source:
                for member in source.getmembers():
                    path = contents / member.name
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with path.open('xb') as out:
                        out.write(source.extractfile(member).read())
                    path.chmod(0o600)
            os.rename(contents, target)
    print(json.dumps({'stage': 'private_artifact', 'sha256': SHA, 'files': len(inventory),
                      'release': str(target), 'activated': False}))


def tls():
    private_dir(TLS)
    remote = json.loads(aws('acm', 'get-certificate', '--certificate-arn', CERT))['Certificate']
    current = TLS / 'certificate.pem'
    if current.exists() and current.read_text() == remote and (TLS / 'private-key.pem').is_file():
        print(json.dumps({'stage': 'origin_tls', 'changed': False}))
        return
    with tempfile.TemporaryDirectory(dir=TLS) as tmp:
        tmp = Path(tmp)
        passfile = tmp / 'passphrase'
        passfile.write_bytes(secrets.token_hex(32).encode())
        passfile.chmod(0o600)
        value = json.loads(aws('acm', 'export-certificate', '--certificate-arn', CERT,
                              '--passphrase', 'fileb://' + str(passfile)))
        for name, field in [('certificate.pem', 'Certificate'), ('chain.pem', 'CertificateChain'),
                            ('encrypted-key.pem', 'PrivateKey')]:
            (tmp / name).write_text(value[field])
            (tmp / name).chmod(0o600)
        key = tmp / 'private-key.pem'
        run('openssl', 'pkey', '-in', str(tmp / 'encrypted-key.pem'), '-passin',
            'file:' + str(passfile), '-out', str(key))
        key.chmod(0o600)
        certificate = tmp / 'certificate.pem'
        cert_public = run('openssl', 'x509', '-in', str(certificate), '-pubkey', '-noout')
        key_public = run('openssl', 'pkey', '-in', str(key), '-pubout')
        if cert_public != key_public:
            raise ValueError('Certificate and private key do not match.')
        run('openssl', 'x509', '-in', str(certificate), '-noout', '-checkhost', 'origin.daylightmedicare.com')
        run('openssl', 'x509', '-in', str(certificate), '-noout', '-checkend', '2592000')
        run('openssl', 'verify', '-CAfile', '/etc/pki/tls/certs/ca-bundle.crt',
            '-untrusted', str(tmp / 'chain.pem'), str(certificate))
        (tmp / 'fullchain.pem').write_text(value['Certificate'] + value['CertificateChain'])
        (tmp / 'fullchain.pem').chmod(0o600)
        for name in ['certificate.pem', 'chain.pem', 'fullchain.pem', 'private-key.pem']:
            os.replace(tmp / name, TLS / name)
    print(json.dumps({'stage': 'origin_tls', 'changed': True, 'key_mode': '0600',
                      'certificate_and_key_match': True, 'publicly_listening': False}))


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['artifact', 'tls'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Requires the approved host administrator.')
    {'artifact': stage, 'tls': tls}[args.stage]()
