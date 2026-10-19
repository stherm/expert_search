# expert_search

Fragt den Preis eines Produkts in allen expert-Märkten ab und listet die günstigsten.

## Nutzung

```sh
nix run . -- 12220178771                      # Artikelnummer oder Produkt-URL
nix run . -- 12220178771 --filter "Köln,53"   # nur bestimmte Märkte (Name, Ort, PLZ)
```

Ohne Nix: `python3 expert_checker.py 12220178771` (Python 3.10+, keine Zusatzpakete).

Ergebnis: `expert_<artikelnummer>.csv`, sortiert nach Preis. Ein abgebrochener Lauf
macht beim nächsten Start dort weiter. Alle Optionen: `--help`.
