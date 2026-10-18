# Ricostruire LOTF Save Sync 1.0.1

## Applicazione e prerequisiti

Il programma e' sorgente Python interpretato. Non esiste un nostro EXE da compilare, non viene usato PyInstaller e non servono pacchetti pip o chiavi API. Il pacchetto Windows include il runtime ufficiale CPython 3.13.16 e Tcl/Tk 8.6.15.

Per provare i sorgenti: installa Python 3.12 o successivo con Tkinter e apri un terminale nella cartella del repository:

```text
python -m unittest discover -s tests -v
python tools/build_release.py source-check
python app.py
```

Su Windows puoi usare `py -3.13` al posto di `python`. I due file `.bat` originali funzionano nel pacchetto assemblato, dove e' presente la cartella `runtime`.

## Creare il pacchetto Windows

Su Windows servono Python 3.12+ e Windows Installer (`msiexec.exe`). Su Linux servono Python 3.12+ e `msiextract`, fornito dal pacchetto `msitools`.

```text
python tools/build_release.py build
```

Lo script scarica due distribuzioni ufficiali da Python.org, verifica dimensioni e hash SHA-256, estrae Tcl/Tk in una cartella temporanea e ricostruisce lo ZIP. Su Windows usa l'estrazione amministrativa MSI, non l'installazione globale di Python. Non sono richiesti privilegi amministrativi dal programma di riparazione. Se i criteri del PC impediscono l'estrazione MSI, usa la procedura Linux senza disabilitare le protezioni.

Il ramo Linux della build e' stato provato; il ramo Windows con `msiexec` e l'avvio nativo del pacchetto Windows non sono stati eseguiti nell'ambiente di sviluppo.

Risultato predefinito:

```text
dist/LOTF_Save_Sync_1.0.1_Beta_Windows_x64_rebuilt.zip
```

Per ripetere la build scegli un nuovo nome con `--output`: lo script non sovrascrive uno ZIP esistente. Per specificare `msiextract` su Linux usa `--msiextract /percorso/msiextract`.

## Build senza rete

Scarica i due file elencati in [`packaging/dependencies.json`](packaging/dependencies.json), mantenendone i nomi, e mettili in una cartella cache:

```text
python tools/build_release.py build --offline --cache percorso/cache
```

Servono solo `python-3.13.16-embed-amd64.zip` e `tcltk.msi`, entrambi della versione 3.13.16. Lo script rifiuta file mancanti o con hash errato. Le URL e gli hash completi sono anche nella [guida inglese](BUILD_EN.md).

La rete viene usata soltanto dallo script di build quando richiesto. L'applicazione distribuita lavora in locale e non invia i salvataggi.

## Verifica della corrispondenza

```text
python tools/build_release.py verify percorso/LOTF_Save_Sync_1.0.1_Beta_Windows_x64.zip
```

Il verificatore controlla l'elenco completo, le dimensioni e gli hash dei 1.117 file senza estrarre o avviare lo ZIP. La ricostruzione e' stata confrontata con la release originale: tutti i contenuti estratti coincidono byte per byte.

L'hash dell'intero ZIP puo' essere diverso per metadati, date e compressione. Lo script distingue chiaramente l'identita' dei contenuti da quella del contenitore ZIP.

I 40 file forniti dal repository per la release comprendono sorgenti, documentazione e il file personalizzato `python313._pth`. Gli altri 1.077 file arrivano senza modifiche dalle distribuzioni ufficiali. Il file `runtime/python313.zip` e' la libreria standard ufficiale di Python: costituisce un archivio ZIP annidato, dichiarato nella documentazione per la revisione Nexus.

## Cosa non comprende la build

Non ricompila da C il runtime Python o Tcl/Tk e non riproduce le firme digitali del fornitore. La [guida inglese](BUILD_EN.md) collega i relativi sorgenti upstream. Non include salvataggi, dati Steam, account, dump privati o test con dati reali. Non include uno sblocco degli achievement Steam.

I test pubblici sono sintetici e non dimostrano compatibilita' universale con il gioco. Leggere [le avvertenze](DISCLAIMER_IT_EN.txt) e conservare sempre un backup completo dei salvataggi prima di usare l'utility.
