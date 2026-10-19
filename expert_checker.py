#!/usr/bin/env python3
"""
expert Filial-Checker
=====================
Fragt für ein Produkt auf expert.de den Preis in allen (oder ausgewählten)
expert-Märkten ab – langsam, nacheinander und mit Rücksicht auf Rate-Limits.

So funktioniert's:
  1. Die aktuelle Märkteliste kommt direkt von expert.de (Marktfinder).
  2. Für jeden Markt wird der Preis-Endpunkt abgefragt, den auch die
     Produktseite selbst nutzt (/api/pricepds). Rein lesend – es landet
     nichts im Warenkorb, ein Browser ist nicht nötig.
  3. Ergebnisse (Preis, Rabatt, Bestand im Markt/online) werden laufend in
     eine CSV geschrieben. Bricht der Lauf ab, macht ein erneuter Start dort
     weiter, wo er aufgehört hat. Fehlgeschlagene Märkte werden dabei
     erneut versucht.

Rate-Limits:
  - Immer nur EINE Anfrage gleichzeitig.
  - Pause zwischen Anfragen (Standard 3 s, plus Zufall).
  - Bei 429 / 403 / 503 / Cloudflare-Seite: Wartezeit verdoppelt sich
    (1 → 2 → 4 … bis 15 Min), "Retry-After" wird respektiert.
  - Nach mehreren Blockaden in Folge stoppt das Skript sauber.
    Einfach später nochmal starten – es macht dort weiter.

Benötigt nur Python 3.10+ (keine Zusatzpakete).

Beispiele:
  python expert_checker.py 12220178771
  python expert_checker.py "https://www.expert.de/shop/....html"
  python expert_checker.py 12220178771 --filter "Köln,Bonn,53"   # Name/Ort/PLZ
  python expert_checker.py 12220178771 --delay 6                 # noch vorsichtiger
  python expert_checker.py 12220178771 --neu                     # Fortschritt verwerfen
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

BASE = "https://www.expert.de"
API = "https://production.brntgs.expert.de/api"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

BLOCK_MARKER = ("cf-chl", "challenge-platform", "Just a moment", "Attention Required")
FERTIG = ("ok", "kein_preis")          # diese Märkte werden beim Fortsetzen übersprungen


# ----------------------------------------------------------------- Hilfen
def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def hole(url: str, timeout: float = 30) -> tuple[int, dict, str]:
    """GET mit Browser-Headern. Liefert (Status, Header, Body)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "de-DE,de;q=0.9",
        "Origin": BASE,
        "Referer": BASE + "/",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read().decode("utf-8", "replace")


def ist_blockiert(status: int, body: str) -> bool:
    return status in (403, 429, 503) or any(m in body[:5000] for m in BLOCK_MARKER)


class Drossel:
    """Adaptive Pause mit exponentiellem Backoff."""

    def __init__(self, delay: float, max_blocks: int):
        self.basis = delay
        self.delay = delay
        self.backoff = 60.0
        self.blocks_in_folge = 0
        self.max_blocks = max_blocks

    def ok(self) -> None:
        self.blocks_in_folge = 0
        self.backoff = 60.0
        # langsam wieder Richtung Basistempo
        self.delay = max(self.basis, self.delay * 0.9)
        time.sleep(self.delay + random.uniform(0, self.delay * 0.5))

    def blockiert(self, retry_after: str | None = None) -> bool:
        """Wartet. Gibt False zurück, wenn aufgegeben werden soll."""
        self.blocks_in_folge += 1
        if self.blocks_in_folge > self.max_blocks:
            return False
        warte = self.backoff
        if retry_after and retry_after.isdigit():
            warte = max(warte, float(retry_after))
        self.delay = min(self.delay * 1.5, 30)          # danach generell langsamer
        log(f"  ⚠ Rate-Limit/Blockade ({self.blocks_in_folge}/{self.max_blocks}). "
            f"Warte {int(warte)} s …")
        time.sleep(warte)
        self.backoff = min(self.backoff * 2, 900)
        return True


# ------------------------------------------------------------- Abfragen
def produkt_aufloesen(eingabe: str) -> tuple[str, str]:
    """Webcode (Artikelnummer) + Produkt-URL aus Nummer oder URL ermitteln."""
    if eingabe.isdigit():
        webcode, url = eingabe, ""
    else:
        pfad = urlparse(eingabe).path
        m = re.search(r"/(\d{6,})-[^/]*\.html", pfad)
        if not m:
            sys.exit(f"Keine Artikelnummer in der URL gefunden: {eingabe}")
        webcode, url = m.group(1), BASE + pfad
    if not url:                        # nur für den Link in der CSV
        try:
            req = urllib.request.Request(f"{BASE}/shop/suche?q={quote(webcode)}",
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                if f"/{webcode}-" in r.url:
                    url = BASE + urlparse(r.url).path
        except (urllib.error.URLError, TimeoutError):
            pass
    return webcode, url


def lade_maerkte(cache: Path) -> list[dict]:
    """Aktuelle Märkteliste vom expert-Marktfinder; Cache als Rückfall."""
    try:
        status, _, body = hole(f"{API}/storeFinder?maxResults=5000")
        if status != 200:
            raise ValueError(f"HTTP {status}")
        maerkte = [e["store"] for e in json.loads(body)]
        try:
            cache.write_text(json.dumps(maerkte, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        except OSError:
            pass
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError) as e:
        if not cache.exists():
            sys.exit(f"Märkteliste nicht abrufbar ({e}) und kein Cache vorhanden.")
        log(f"Märkteliste nicht abrufbar ({e}) – nutze Cache {cache.name}.")
        maerkte = json.loads(cache.read_text(encoding="utf-8"))
    return [{"id": m["id"], "exp_id": m.get("expId") or m["id"].removeprefix("e_"),
             "name": m.get("name", ""), "ort": m.get("city", ""), "plz": m.get("zip", "")}
            for m in maerkte]


def preis_abfragen(webcode: str, store_id: str) -> tuple[int, dict, str, dict | None]:
    status, header, body = hole(f"{API}/pricepds?webcode={webcode}&storeId={store_id}")
    daten = None
    if status == 200:
        try:
            daten = json.loads(body)
        except ValueError:
            pass
    return status, header, body, daten


def auswerten(daten: dict | None) -> dict:
    p = (daten or {}).get("price") or {}
    promo = (daten or {}).get("promotionPrice") or {}
    preis = promo.get("checkoutPrice") or p.get("bruttoPrice")
    nach_cb = promo.get("afterCashbackPrice")
    aktion = " / ".join(t for t in (promo.get("directDiscountTitle"),
                                     promo.get("cashbackTitle")) if t)
    return {
        "preis": f"{preis:.2f}" if preis else "",
        "nach_cashback": f"{nach_cb:.2f}" if nach_cb and nach_cb != preis else "",
        "listenpreis": f"{p['bruttoPrice']:.2f}" if p.get("bruttoPrice") else "",
        "aktion": aktion,
        "bestand_markt": p.get("storeStock", ""),
        "bestand_online": p.get("onlineStock", ""),
        "online": p.get("onlineAvailability", ""),
        "markt_verfuegbar": p.get("storeAvailability", ""),
    }


# ------------------------------------------------------------------ Main
def main() -> None:
    ap = argparse.ArgumentParser(description="expert-Märkte nach Produktpreis durchsuchen")
    ap.add_argument("produkt", help="Artikelnummer (z.B. 12220178771) oder Produkt-URL")
    ap.add_argument("--filter", help="Nur Märkte, deren Name, Ort oder PLZ einen dieser "
                                     "Begriffe enthält (kommagetrennt, z.B. 'Köln,Bonn,53')")
    ap.add_argument("--delay", type=float, default=3.0, help="Pause zw. Anfragen in s (Std: 3)")
    ap.add_argument("--max-blocks", type=int, default=5,
                    help="Abbruch nach so vielen Blockaden in Folge (Std: 5)")
    ap.add_argument("--versuche", type=int, default=3,
                    help="Versuche pro Markt bei Netzwerkfehlern (Std: 3)")
    ap.add_argument("--out", help="CSV-Datei (Std: expert_<artikelnummer>.csv)")
    ap.add_argument("--neu", action="store_true", help="Bisherigen Fortschritt verwerfen")
    args = ap.parse_args()

    def _stopp(*_):                      # auch "kill" speichert sauber den Fortschritt
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _stopp)
    signal.signal(signal.SIGINT, _stopp)

    webcode, url = produkt_aufloesen(args.produkt.strip())
    log(f"Artikel {webcode}" + (f" – {url}" if url else ""))

    maerkte = lade_maerkte(Path("maerkte.json"))
    if args.filter:
        begriffe = [b.strip().lower() for b in args.filter.split(",") if b.strip()]
        maerkte = [m for m in maerkte
                   if any(b in f"{m['name']} {m['ort']} {m['plz']}".lower() for b in begriffe)]
    if not maerkte:
        sys.exit("Keine Märkte passen zum Filter.")

    out = Path(args.out or f"expert_{webcode}.csv")
    felder = ["preis", "nach_cashback", "listenpreis", "aktion", "markt", "ort", "plz",
              "bestand_markt", "bestand_online", "online", "markt_verfuegbar",
              "store_id", "status", "link"]
    ergebnisse: dict[str, dict] = {}
    if out.exists() and not args.neu:
        with out.open(encoding="utf-8") as f:
            ergebnisse = {r["store_id"]: r for r in csv.DictReader(f) if r.get("store_id")}
        erledigt = sum(r["status"] in FERTIG for r in ergebnisse.values())
        if erledigt:
            log(f"Setze fort: {erledigt} Märkte bereits erledigt.")

    offen = [m for m in maerkte if ergebnisse.get(m["id"], {}).get("status") not in FERTIG]
    if not offen:
        log(f"Alle Märkte bereits erledigt – siehe {out} (mit --neu frisch abfragen).")
        return
    log(f"{len(offen)} Märkte abzufragen (~{int(len(offen) * args.delay * 1.3 / 60) + 1} Min).")

    def speichern() -> None:
        tmp = out.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=felder, extrasaction="ignore")
            w.writeheader()
            for r in sorted(ergebnisse.values(),
                            key=lambda r: float(r["preis"]) if r.get("preis") else 1e12):
                w.writerow(r)
        tmp.replace(out)                # atomar – CSV ist nie halb geschrieben

    drossel = Drossel(args.delay, args.max_blocks)
    i = fehlversuche = 0
    nochmal: set[str] = set()                              # Fehler am Ende einmal wiederholen
    preise = [float(r["preis"]) for r in ergebnisse.values() if r.get("preis")]
    bestpreis = min(preise, default=None)
    try:
        while i < len(offen):
            m = offen[i]
            try:
                status, header, body, daten = preis_abfragen(webcode, m["id"])
                grund = f"HTTP {status}"
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                status, header, body, daten = 0, {}, "", None
                grund = str(e)
            # Netzwerkfehler / 500er sind meist vorübergehend → kurz warten, nochmal
            if (status == 0 or status in (500, 502, 504)) and fehlversuche + 1 < args.versuche:
                fehlversuche += 1
                log(f"  {grund} bei {m['name']} – neuer Versuch in {5 * fehlversuche} s …")
                time.sleep(5 * fehlversuche)
                continue

            if ist_blockiert(status, body):
                if not drossel.blockiert(header.get("Retry-After")):
                    log("Zu viele Blockaden in Folge – stoppe. "
                        "Später einfach erneut starten, es geht hier weiter.")
                    break
                continue                                       # gleichen Markt nochmal

            werte = auswerten(daten)
            if status == 200 and daten is not None:
                zustand = "ok" if werte["preis"] else "kein_preis"
            elif status == 404:
                zustand = "kein_preis"
            else:
                zustand = f"fehler_{status}"
                if m["id"] not in nochmal:
                    nochmal.add(m["id"])
                    offen.append(m)                            # am Ende nochmal versuchen
            ergebnisse[m["id"]] = {
                **werte, "markt": m["name"], "ort": m["ort"], "plz": m["plz"],
                "store_id": m["id"], "status": zustand,
                "link": f"{url}?branch_id={m['exp_id']}" if url else "",
            }
            i += 1
            fehlversuche = 0
            info = (f"{werte['preis']} €" if werte["preis"] else zustand)
            if werte["preis"] and werte["bestand_markt"] not in ("", None):
                info += f"  (Markt: {werte['bestand_markt']} Stk.)"
            log(f"[{i}/{len(offen)}] {m['name']} {m['ort']}: {info}")
            if werte["preis"] and (bestpreis is None or float(werte["preis"]) < bestpreis):
                bestpreis = float(werte["preis"])
                log(f"  ★ Neuer Bestpreis: {bestpreis:.2f} € – {m['name']}, {m['plz']} {m['ort']}")
            if i % 10 == 0:
                speichern()
            drossel.ok()
    except KeyboardInterrupt:
        log("Abgebrochen – Fortschritt wird gespeichert.")
    finally:
        speichern()

    mit_preis = sorted((r for r in ergebnisse.values() if r.get("preis")),
                       key=lambda r: float(r["preis"]))
    fehler = sum(r["status"].startswith("fehler") for r in ergebnisse.values())
    print(f"\nErgebnis: {len(mit_preis)} von {len(maerkte)} Märkten mit Preis → {out}"
          + (f"  ({fehler} Fehler – erneut starten zum Wiederholen)" if fehler else ""))
    for r in mit_preis[:15]:
        bestand = f"Markt {r['bestand_markt'] or 0} Stk." if r["bestand_markt"] != "" else ""
        print(f"  {float(r['preis']):>9.2f} €  {r['markt']} – {r['plz']} {r['ort']}  {bestand}")
    if mit_preis:
        b = mit_preis[0]
        gleich = sum(r["preis"] == b["preis"] for r in mit_preis)
        bestand = f", Markt {b['bestand_markt'] or 0} Stk." if b["bestand_markt"] != "" else ""
        print(f"\nBilligster: {float(b['preis']):.2f} € – {b['markt']}, {b['plz']} {b['ort']}{bestand}"
              + (f" (gleicher Preis in {gleich} Märkten)" if gleich > 1 else ""))
        if b["link"]:
            print(f"Link: {b['link']}")


if __name__ == "__main__":
    main()
