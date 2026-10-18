# Source-review validation — 18 October 2026

Reference: `LOTF_Save_Sync_1.0.1_Beta_Windows_x64.zip`, 15,229,844 bytes, 1,117 files.

Reference SHA-256:

```text
0504c6b37724775a2a7c48339254b45f73a870cda5c8b1c13af193077ee54833
```

This is the original locally retained release prepared for Nexus. We have not downloaded the quarantined server copy to independently confirm its container hash; moderators can compare it with the hash and file manifest provided here.

## Checks performed

- Original release ZIP integrity check passed.
- All 40 repository-provided release files match their original release bytes. This includes 39 source/documentation/license/image files and the one runtime configuration file.
- All 33 remaining CPython files match the official CPython 3.13.16 embeddable package.
- All 1,044 Tcl/Tk-related runtime files match the official Python 3.13.16 `tcltk.msi` payload.
- A fresh assembly using the provided script and Linux `msiextract` completed successfully with hash-verified offline dependencies.
- The rebuilt archive's complete file list and **all 1,117 uncompressed file contents match the original byte for byte**.
- Five public synthetic unit tests passed.

The rebuilt ZIP has normalized metadata. Its archive SHA-256 in the validation environment was:

```text
b13423a340fa571b2c94b544605e841a078a504baf8558438a3c0f0c8e81c091
```

The differing ZIP hash does not mean different application files. Compression-library versions may also change ZIP bytes across environments; the manifest verifies the extracted contents.

## Limits and history

The Windows `msiexec` branch of the new build script and native Windows execution of the launcher were not tested here. The Linux assembly does not execute Windows binaries. The five public tests do not cover the full synchronization algorithm with real saves.

Earlier private regression testing and a reported successful Steam in-game repair are described in the original [`docs/VALIDATION.txt`](docs/VALIDATION.txt). Private fixtures, account data and their test reports are excluded. No compatibility with arbitrary game versions is claimed.

The repository is an initial public source snapshot prepared for the Nexus review, not a reconstructed history of earlier development. The application's 1.0.1 source is unchanged. This README, review/build documentation, packaging script and manifests were added after that release. Later private save investigations are not part of this 1.0.1 snapshot.
