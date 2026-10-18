"""Reconstruct the 1.0.1 distribution from reviewed source and pinned PSF files.

Packaging only: no custom EXE compilation, no pip dependencies, no game saves.
The application never invokes this script. Downloads occur only during an
explicit `build` command and can be disabled with --offline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'packaging/release-manifest.json'
DEPENDENCIES = ROOT / 'packaging/dependencies.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative_path(value):
    path = PurePosixPath(value)
    require(not path.is_absolute() and value and '\\' not in value
            and ':' not in value and '..' not in path.parts, 'Unsafe manifest path')
    return path


def read_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    seen = set()
    for entry in manifest['files']:
        for key in ('path', 'source'):
            relative_path(entry[key])
        require(entry['path'] not in seen, 'Duplicate manifest file')
        seen.add(entry['path'])
        require(entry['origin'] in ('repository', 'embed', 'tcltk'), 'Unknown origin')
    return manifest


def validate(data, entry):
    require(len(data) == entry['bytes'] and digest(data) == entry['sha256'],
            'Content differs from reference: ' + entry.get('path', entry.get('file', '?')))


def repository_bytes(entry):
    path = (ROOT / entry['source']).resolve()
    require(path.is_relative_to(ROOT), 'Repository symlink escapes source tree')
    data = path.read_bytes()
    validate(data, entry)
    return data


def source_check(manifest):
    checked = 0
    for entry in manifest['files']:
        if entry['origin'] == 'repository':
            repository_bytes(entry)
            checked += 1
    print(f'{checked} application, documentation and configuration files match 1.0.1.')


def dependency(item, cache, offline):
    path = cache / item['file']
    require(path.parent == cache, 'Unsafe dependency filename')
    if path.exists():
        validate(path.read_bytes(), item)
        return path
    require(not offline, f'Missing offline dependency: {path}')
    require(item['url'].startswith('https://www.python.org/ftp/python/3.13.16/'),
            'Unexpected dependency URL')
    print('Downloading official dependency: ' + item['file'])
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as file:
        temporary = Path(file.name)
        try:
            with urllib.request.urlopen(item['url'], timeout=60) as response:
                remaining = item['bytes'] + 1
                while remaining:
                    chunk = response.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    file.write(chunk)
                    remaining -= len(chunk)
            file.close()
            validate(temporary.read_bytes(), item)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return path


def extract_tcltk(msi, output, msiextract):
    output.mkdir()
    if os.name == 'nt':
        # Administrative extraction of the hash-verified official installer.
        # This does not run the Python installer or register Python globally.
        result = subprocess.run(['msiexec.exe', '/a', str(msi), '/qn',
                                 'TARGETDIR=' + str(output)], check=False)
        require(result.returncode == 0, f'msiexec extraction failed: {result.returncode}')
    else:
        binary = shutil.which(msiextract)
        require(binary is not None, 'Install msitools (msiextract), or use --msiextract PATH.')
        subprocess.run([binary, '-C', str(output), str(msi)], check=True,
                       stdout=subprocess.DEVNULL)


def verify_archive(path, manifest):
    expected = {manifest['archive_root'] + '/' + e['path']: e for e in manifest['files']}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate ZIP members')
        files = {n for n in names if not n.endswith('/')}
        require(files == set(expected), 'Archive file list differs from the reference')
        for name, entry in expected.items():
            info = archive.getinfo(name)
            require(info.file_size == entry['bytes'], 'Archive size differs: ' + name)
            with archive.open(name) as file:
                validate(file.read(entry['bytes'] + 1), entry)
    same_zip = digest(path.read_bytes()) == manifest['release_sha256']
    print(f'{len(expected)} extracted files match the reference byte for byte.')
    print('Original ZIP container hash matches: ' + str(same_zip))
    return same_zip


def build(args, manifest):
    source_check(manifest)
    cache = Path(args.cache).resolve()
    output = Path(args.output).resolve()
    require(not output.exists(), 'Output already exists; choose a new --output path.')
    cache.mkdir(parents=True, exist_ok=True)
    deps = {item['id']: dependency(item, cache, args.offline)
            for item in json.loads(DEPENDENCIES.read_text(encoding='utf-8'))}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lotfsync-build-') as temporary:
        stage = Path(temporary)
        tcltk = stage / 'tcltk'
        extract_tcltk(deps['tcltk'], tcltk, args.msiextract)
        # Both extraction methods normally place DLLs/Lib/tcl at the root. Some
        # MSI implementations add a directory. Resolve only the known landmark.
        candidates = list(tcltk.rglob('_tkinter.pyd'))
        require(len(candidates) == 1, 'Unexpected Tcl/Tk MSI extraction layout')
        tcl_root = candidates[0].parent.parent
        staged_zip = stage / 'release.zip'
        with zipfile.ZipFile(deps['embed']) as embed, zipfile.ZipFile(
                staged_zip, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for entry in manifest['files']:
                if entry['origin'] == 'repository':
                    data = repository_bytes(entry)
                elif entry['origin'] == 'embed':
                    info = embed.getinfo(entry['source'])
                    require(info.file_size == entry['bytes'], 'Unexpected embedded runtime size')
                    data = embed.read(entry['source'])
                else:
                    path = (tcl_root / entry['source']).resolve()
                    require(path.is_relative_to(tcl_root), 'Extracted file escapes root')
                    data = path.read_bytes()
                validate(data, entry)
                info = zipfile.ZipInfo(manifest['archive_root'] + '/' + entry['path'],
                                       date_time=(2026, 10, 11, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compresslevel=9)
        verify_archive(staged_zip, manifest)
        # Exclusive creation prevents an existing output being silently replaced.
        with output.open('xb') as target, staged_zip.open('rb') as source:
            shutil.copyfileobj(source, target)
    print('Created: ' + str(output))
    print('SHA256: ' + digest(output.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('source-check', help='Check source files against the 1.0.1 release')
    verify = sub.add_parser('verify', help='Verify a ZIP without extracting or executing it')
    verify.add_argument('archive', type=Path)
    package = sub.add_parser('build', help='Package source plus official runtime dependencies')
    package.add_argument('--cache', default=str(ROOT / '.build-cache'))
    package.add_argument('--output', default=str(ROOT / 'dist/LOTF_Save_Sync_1.0.1_Beta_Windows_x64_rebuilt.zip'))
    package.add_argument('--offline', action='store_true')
    package.add_argument('--msiextract', default='msiextract')
    args = parser.parse_args()
    try:
        manifest = read_manifest()
        if args.command == 'source-check':
            source_check(manifest)
        elif args.command == 'verify':
            verify_archive(args.archive.resolve(), manifest)
        else:
            build(args, manifest)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
