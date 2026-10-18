# Security review notes for Nexus Mods

These notes describe the submitted **1.0.1 beta** application and the separate build/review tools. They do not assert that Nexus has approved the application or that an antivirus finding is a false positive.

## Entry points and executable provenance

`AVVIA_START.bat` launches official CPython `runtime/pythonw.exe` with `app.py`. `DIAGNOSTICA_DIAGNOSTICS.bat` invokes official `runtime/python.exe` with `diagnostics.py`. Application behavior is readable in `app.py`, `diagnostics.py` and `lotfsync/*.py`. There are no custom compiled native binaries or generated application bytecode files in the original release.

The runtime files are byte-identical copies of two pinned official PSF distributions, except for the explicitly supplied `python313._pth` configuration. The 1,117-file manifest maps every distributed file to a repository file, an embeddable Python ZIP member or a Tcl/Tk MSI member. The exact binary origins are documented in [BUILD_EN.md](BUILD_EN.md).

Python's embeddable package contains `python313.zip` with its standard library bytecode. This archive is retained in the portable runtime, rather than hidden or renamed. It is a nested archive inside the mod ZIP and may be relevant to automated scanning. We do not know whether it was the reason for the quarantine.

The runtime also includes standard modules such as `_socket.pyd` and `_ssl.pyd`, although the application's source does not call network APIs. Their presence comes from the official distribution, not custom networking code.

## Runtime data flow

1. The user explicitly chooses a host and guest character save, folder or ZIP.
2. `workflow.py` reads the selected slot and optional matching rotating backups. ZIP input members are read in memory; they are not extracted to paths supplied by an archive.
3. `format.py` validates the GVAS container, CRC, compressed sizes and decoded bounds. `properties.py` parses tagged fields.
4. `engine.py` applies the selected version-specific groups, validates preservation and audits references.
5. The user chooses an output directory. `workflow.py` writes corrected files, original guest backups, a local JSON report and user guides to a uniquely named staging directory, then renames it into place.

The source inputs are checked for changes before and after output creation. They are not overwritten. The host is a donor, not a file modified by the app. No unrelated saves or `GeneralSave.sav` are rewritten.

## Network, system and privacy behavior

- No application telemetry, remote upload, auto-update, HTTP requests, authentication or API keys.
- No game-process access, injection, memory editing, anti-cheat manipulation, registry persistence or Steam achievement API calls.
- No bundled service, scheduled task or startup installation.
- The UI's explicit open-output action opens the local result directory using `os.startfile` on Windows, or `open` / `xdg-open` on other platforms. This is the only application subprocess use found in the source.
- Startup exceptions may write `LOTF_Save_Sync_startup_error.txt` in the user's home directory and display an error dialog. Diagnostics print local executable/application paths.
- The local repair report can contain character metadata, source hashes and existing saved diagnostics. Users should inspect reports before sharing them; none are transmitted automatically.
- Cleanup on a failed output attempt removes only the new staging directory created for that attempt.

## Build tools are separate

`tools/build_release.py` was added to this repository for the review. It is not included in the original 1.0.1 application ZIP. An explicit build may download the two fixed official Python.org dependencies, checks their hashes, and invokes an MSI extraction tool. `--offline` disables those downloads. The build script does not run when the save-repair application starts.

## Validation limits

Only save version 2.5.624 / MasterSaveVersion 12 is writable. The writer rejects mismatched NG/difficulty and certain unknown or conflicting reference layouts. Some native serialized tails remain opaque; preserving them and checking reference structure is not a full gameplay validator.

The published tests contain synthetic data. Separate private regression and in-game checks informed the initial repair, but those saves are not distributed. Not every game version, option combination or Windows setup was tested. Native Windows launcher execution was not performed in the development environment. See [REVIEW_VALIDATION.md](REVIEW_VALIDATION.md).

## AI and licensing

Code, interface, translations and documentation were produced with extensive ChatGPT/Codex assistance, including generated content. We disclose this instead of claiming comprehensive independent human review. Application code is MIT; PSF, Tcl/Tk and Dedrich notices are retained. [Nexus submission guidelines](https://help.nexusmods.com/article/28-file-submission-guidelines) require appropriate AI content/media tags and accurate claims.

No private saves, player/account identifiers, real-save fixtures, crash dumps or screenshots showing loaded personal saves are included. The two bundled UI screenshots show an empty interface.
