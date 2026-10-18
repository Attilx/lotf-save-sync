# LOTF Save Sync — Co-op Save Repair (EN / IT)

**Version 1.0.1 beta · First mod/utility · Tested repair on Steam saves 2.5.624**

An unofficial, offline desktop utility for Lords of the Fallen (2023). Load a host save and a guest save, compare them, then choose which groups to synchronize: modifiers, story/NPC progress, passages/shortcuts, and checkpoints/vestiges. The program exports repaired copies and guest backups into a new folder.

This repository contains the application source corresponding to the 1.0.1 Windows package submitted to [Nexus Mods, mod 123](https://www.nexusmods.com/lordsofthefallen2023/mods/123). It was prepared for the additional source and build review requested by Nexus. **Publication of this source does not mean Nexus has approved or cleared the download.**

## Run the source

Install Python 3.12 or later with Tkinter, open a terminal in the repository root, and run:

```text
python app.py
```

No pip packages or API keys are required. On Windows, the standard Python installer includes the optional Tcl/Tk component; select it. The source tree does not include a portable runtime: the two original `.bat` launchers are intended for the assembled Windows package.

## Build and review

- [Build instructions — English](BUILD_EN.md)
- [Istruzioni di build — Italiano](BUILD_IT.md)
- [Security review and file provenance](SECURITY_REVIEW.md)
- [Verification performed for this source release](REVIEW_VALIDATION.md)
- [Detailed application architecture](docs/DEVELOPER.txt)
- [User guide — English](docs/GUIDE_EN.txt) / [Guida utente — Italiano](docs/GUIDE_IT.txt)
- [Disclaimer — Italian and English](DISCLAIMER_IT_EN.txt)

The app is interpreted Python: there is no custom application EXE to compile. The Windows package bundles unmodified official CPython 3.13.16 and Tcl/Tk 8.6.15 files. The build script downloads two pinned official Python.org packages, verifies their SHA-256 hashes, assembles the application and verifies all 1,117 resulting files against the original release. It can also use pre-downloaded files with `--offline`.

The application source files themselves are unchanged from the submitted 1.0.1 package. Build/review documentation, the manifest and packaging script were added later for this review. See the validation document for the distinction between identical extracted contents and an identical ZIP container.

## Scope and limitations

- Writes only recognized game version 2.5.624 / MasterSaveVersion 12 saves.
- Host and guest difficulty and NG level must match. The utility does not change difficulty.
- Preserves guest inventory, equipment, runes, stats, appearance and identity. Unselected data is preserved.
- Does not overwrite input files. `GeneralSave.sav` and unrelated character slots are not rewritten.
- No game process injection, Steam API integration or achievement unlocker is included.
- No saved games, account data, private crash dumps or real-save fixtures are included in this repository.
- The public tests use synthetic data. Private in-game/regression tests are described, but are not independently reproducible from this public repository without compatible saves.

This is our first mod/utility. We tested the underlying repair on our own Steam saves. We do not know whether it works with every game version or configuration; other versions are not guaranteed. Not every option combination or Windows configuration has been tested. Use at your own risk and keep a separate complete backup. The program is provided as is, without warranties or acceptance of liability to the extent permitted by law. Read the full disclaimer before use.

## AI disclosure and credits

The application code, interface, translations and documentation were developed with extensive ChatGPT/Codex assistance, including AI-generated content. Human testing confirmed the underlying repair in the reported Steam scenario. This is not a claim of an independent security audit or comprehensive human code review.

Save-format research was informed by [Dedrich/lotf2-difficulty-fix-gui](https://github.com/Dedrich/lotf2-difficulty-fix-gui). Its MIT license and attribution are retained; this application does not invoke that project's difficulty patch. See [third-party notices](THIRD_PARTY_NOTICES.txt) and [licenses](licenses).

Application source: [MIT license](LICENSE.txt). Third-party components retain their own licenses. This project is not affiliated with HEXWORKS, CI Games, Valve or Nexus Mods.

## Italiano

Questa utility locale confronta i salvataggi di host e ospite e permette di scegliere se sincronizzare modificatori, storia/NPC, passaggi e vestigi. Esporta copie corrette e backup senza sovrascrivere i file di ingresso.

Questo repository contiene il sorgente della versione 1.0.1 inviata a Nexus e la procedura per ricostruirne il pacchetto Windows. Non contiene i nostri salvataggi, dati degli account o prove private. I sorgenti dell'applicazione coincidono con quelli della release: gli strumenti di build e la documentazione di revisione sono aggiunte successive.

E' la nostra prima mod/utility, realizzata con ampio supporto di ChatGPT/Codex. La riparazione di base e' stata provata su Steam con salvataggi 2.5.624. Non garantiamo altre versioni o configurazioni. Utilizzo a proprio rischio, senza garanzie e senza assunzione di responsabilita' nei limiti consentiti dalla legge. Conservare sempre un backup completo separato.

Per iniziare: [guida utente](docs/GUIDE_IT.txt), [build](BUILD_IT.md) e [avvertenze complete](DISCLAIMER_IT_EN.txt).
