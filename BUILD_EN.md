# Building and reviewing LOTF Save Sync 1.0.1

## What is built

LOTF Save Sync is Python source interpreted by CPython. There is no PyInstaller, executable wrapper, custom native DLL, obfuscation, compiler or pip dependency. `AVVIA_START.bat` starts the official `runtime/pythonw.exe` with `app.py`; the diagnostic launcher uses `runtime/python.exe` and `diagnostics.py`.

These instructions reconstruct the **file contents** of the Windows x64 1.0.1 package. They do not compile CPython or Tcl/Tk from their upstream C source or reproduce the vendor's signatures. Official upstream binaries are reused, pinned and verified.

## Review or run without downloading build dependencies

Prerequisite: Python 3.12+ with Tkinter to run the GUI. Tkinter is not needed for the five public tests or the archive verifier.

From the repository root:

```text
python -m unittest discover -s tests -v
python tools/build_release.py source-check
python app.py
```

Use `py -3.13` instead of `python` on Windows if needed. There is no `pip install` step.

`source-check` validates the 40 repository-supplied application, release-documentation and configuration files against the original release. It intentionally fails if those files were changed. New build/review documents are not part of the old release manifest.

## Build on Windows

Prerequisites: a Python 3.12+ installation, Windows Installer (`msiexec.exe`, included with Windows), and internet access for the first build.

Open a normal terminal in the repository root:

```text
python tools/build_release.py build
```

The script verifies all inputs, then uses `msiexec.exe /a ... /qn TARGETDIR=...` to extract the official `tcltk.msi` into a temporary directory. This is administrative extraction, not a Python system installation. If Windows policy prevents MSI extraction, use the tested Linux route below; do not disable security software. Windows execution of this packaging branch has not been tested in our development environment.

Default output:

```text
dist/LOTF_Save_Sync_1.0.1_Beta_Windows_x64_rebuilt.zip
```

The script refuses to overwrite an existing output. Use a different `--output` filename for another build.

Extract the resulting ZIP and double-click `AVVIA_START.bat` on Windows x64. No system Python or network connection is required to run that assembled application.

## Build on Linux — validated route

Prerequisites: Python 3.12+ and `msiextract` from the `msitools` package. On Debian/Ubuntu, install `msitools` using your normal package-management process. The packaging script itself does not need root privileges.

```text
python3 tools/build_release.py build
```

If `msiextract` is not on PATH, pass its path:

```text
python3 tools/build_release.py build --msiextract /path/to/msiextract
```

This creates the same Windows package contents without executing the Windows runtime. It does not establish that the Windows GUI starts correctly on every machine.

## Pinned dependencies and offline builds

The authoritative URLs, file sizes and SHA-256 hashes are in [`packaging/dependencies.json`](packaging/dependencies.json). Only these two build inputs are needed:

| Input | Official source | SHA-256 |
| --- | --- | --- |
| CPython 3.13.16 embeddable x64 ZIP | https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip | `97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297` |
| Matching Tcl/Tk MSI | https://www.python.org/ftp/python/3.13.16/amd64/tcltk.msi | `968fc0acb37c42439ae4cf96181ee2e8148a89a22707414d980f7a2a84c2e67b` |

Place these exact filenames in a cache directory and run:

```text
python tools/build_release.py build --offline --cache path/to/cache
```

The default cache is `.build-cache`. A missing or incorrect cached file is rejected; an incorrect file is never silently accepted. Only an explicit `build` command without `--offline` downloads dependencies. No user saves are read or transmitted by the build script.

## Exact composition of the portable runtime

- 33 files copied without byte changes from the official embeddable ZIP.
- 1,044 files copied without byte changes from the official Tcl/Tk MSI. These include `DLLs`, `Lib/tkinter` and `tcl` files selected by the manifest. Unselected installer components are not copied.
- One custom `runtime/python313._pth` file from [`packaging/python313._pth`](packaging/python313._pth), containing the stdlib ZIP, runtime directory, DLLs, Lib and parent application search paths.
- 39 application/source/documentation/license/image files from the original release, including its original `SHA256SUMS.json`.

Every mapping and resulting hash is listed in [`packaging/release-manifest.json`](packaging/release-manifest.json). The official runtime contains `python313.zip`, which is the standard library archive. It is a nested ZIP in the portable download and is explicitly disclosed for Nexus's security review.

## Verify a submitted or rebuilt archive

```text
python tools/build_release.py verify path/to/LOTF_Save_Sync_1.0.1_Beta_Windows_x64.zip
```

The verifier does not execute or extract the archive. It checks the complete file list, rejects duplicate members, and checks each uncompressed file's size and SHA-256. Expected result: **1,117 files match**.

The original supplied release ZIP SHA-256 is:

```text
0504c6b37724775a2a7c48339254b45f73a870cda5c8b1c13af193077ee54833
```

The rebuilt ZIP uses normalized metadata and can have a different archive hash because of timestamps, ZIP attributes or compression-library differences. A false result for the original ZIP-container hash is expected for a rebuild; matching every extracted file is the relevant comparison. The verifier prints both results separately.

## Upstream source and licensing

- [CPython 3.13.16 source release and official binary checksums](https://www.python.org/downloads/release/python-31316/)
- [CPython upstream repository](https://github.com/python/cpython), release tag `v3.13.16`; see its `PCbuild` and `Tools/msi` documentation for rebuilding Python itself.
- [Tcl upstream source](https://core.tcl-lang.org/tcl/) and [Tk upstream source](https://core.tcl-lang.org/tk/), version 8.6.15 as declared in the bundled scripts.
- Bundled licenses: [`licenses/`](licenses) and [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt).

Rebuilding the vendor runtime from C source is a separate upstream task and is not claimed to produce byte-identical signed binaries. The provided application build uses the exact official packages above so reviewers can reproduce and compare the distributed contents.
