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

## Regelmäßig suchen und benachrichtigen lassen

Damit nicht jedes Mal alles eingetippt werden muss, liest das Skript die Datei
`expert.ini` im selben Ordner. Am einfachsten `expert.beispiel.ini` kopieren, in
`expert.ini` umbenennen und mit einem Texteditor anpassen:

```ini
[suche]
produkt = 12220178771
filter =
alle = 12h

[mail]
an = ich@example.de
server = mail.gmx.net
port = 587
benutzer = ich@gmx.de
passwort = geheim

[push]
thema = expert-preise-bitte-aendern
```

Danach reicht `py expert_checker.py` (Windows) bzw. `python3 expert_checker.py`
(macOS). Unter Windows genügt auch ein Doppelklick auf `expert_checker.py`.

- **`[suche]`**: `produkt` und `filter` wie oben beschrieben. `alle` wiederholt
  die Suche regelmäßig, z.B. `12h`, `30m` oder `1d`. Leer lassen für eine
  einmalige Suche. Ein Lauf über alle Märkte dauert etwa 20 Minuten. Das Fenster
  muss offen und der Rechner an bleiben, beenden mit Strg+C.
- **`[mail]`**: Eine E-Mail mit den drei günstigsten Märkten samt Preis,
  Bestand und Link. Haben mehrere Märkte den gleichen Preis, werden es bis zu
  fünf. Mehrere Empfänger in `an` mit Komma trennen. Wer nur Push möchte, lässt
  den Abschnitt weg.
- **`[push]`**: Push-Nachricht aufs Handy über [ntfy](https://ntfy.sh). Die
  kostenlose ntfy-App (Android/iOS) installieren und dort das gleiche `thema`
  abonnieren. Das Thema ist wie ein Passwort: Jeder, der es kennt, kann
  mitlesen, also einen eigenen, schwer erratbaren Namen wählen.

Benachrichtigt wird nach der ersten Suche und danach nur, wenn sich die Liste
ändert, also ein Preis darin oder ein Markt dazukommt oder wegfällt. Geänderte
Stückzahlen allein lösen nichts aus. Im Betreff steht dann auch der vorherige
Bestpreis.

Bei den meisten Anbietern braucht es für `passwort` ein eigenes App-Passwort
statt des normalen Passworts:

| Anbieter | `server`             | `port` | Hinweis                                              |
|----------|----------------------|--------|------------------------------------------------------|
| GMX      | `mail.gmx.net`       | 587    | In den Einstellungen „POP3/IMAP Abruf“ erlauben      |
| WEB.DE   | `smtp.web.de`        | 587    | In den Einstellungen „POP3/IMAP Abruf“ erlauben      |
| Gmail    | `smtp.gmail.com`     | 587    | App-Passwort anlegen (benötigt Bestätigung in zwei Schritten) |
| Yahoo    | `smtp.mail.yahoo.com`| 465    | App-Passwort anlegen                                 |

Ob alles passt, zeigt ein Test ohne Suchlauf:

```sh
py expert_checker.py --test-nachricht        # Windows
python3 expert_checker.py --test-nachricht   # macOS
```

Alle Werte lassen sich auch einmalig auf der Kommandozeile setzen, z.B.
`--alle 6h`. Für mehrere Produkte je eine eigene Datei anlegen und mit
`--einstellungen tv.ini` auswählen.
