# expert_search

Fragt den Preis eines Produkts in allen expert-Märkten ab und listet die günstigsten.

## Installation

Benötigt wird nur Python 3.10 oder neuer. Zusätzliche Pakete braucht es nicht.

**Windows:** Python von [python.org](https://www.python.org/downloads/) installieren
und dabei „Add python.exe to PATH“ anhaken. Alternativ in der PowerShell:

```powershell
winget install Python.Python.3.13
```

**macOS:** Python von [python.org](https://www.python.org/downloads/) installieren
oder mit [Homebrew](https://brew.sh):

```sh
brew install python
```

Danach dieses Repository herunterladen, entweder mit
`git clone https://github.com/stherm/expert_search.git` oder auf GitHub über
„Code“ → „Download ZIP“ (dann entpacken).

## Nutzung

Im Ordner `expert_search` ein Terminal öffnen und als Argument die Artikelnummer
oder die Produkt-URL von expert.de übergeben.

**Windows** (PowerShell):

```powershell
py expert_checker.py 12220178771
py expert_checker.py 12220178771 --filter "Köln,53"   # nur bestimmte Märkte (Name, Ort, PLZ)
```

**macOS** (Terminal):

```sh
python3 expert_checker.py 12220178771
python3 expert_checker.py 12220178771 --filter "Köln,53"
```

**Nix:**

```sh
nix run . -- 12220178771
nix run github:stherm/expert_search -- 12220178771   # ohne Klonen
```

Das Ergebnis landet in `expert_<artikelnummer>.csv`, sortiert nach Preis. Am Ende
steht der günstigste Markt samt Link in der Ausgabe. Ein abgebrochener Lauf macht
beim nächsten Start dort weiter. Alle Optionen: `--help`.
