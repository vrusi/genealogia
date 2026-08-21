#!/usr/bin/env python3
"""Stráži, či čísla v textoch nezostarli oproti databáze.

Počty sú najtichšia forma zastarania: veta „~32 osôb s úplnými dátumami"
vyzerá rovnako dôveryhodne, keď je ich 48. Kontrola rozporných dátumov ju
nezachytí, lebo tam nie je meno ani dátum — len číslo.

Tolerancia sa riadi tvarom čísla v texte:
  „48"    presne     — musí sedieť
  „~48"   približne  — do 20 %
  „48+"   aspoň      — nesmie byť menej; ak je oveľa viac, tvrdenie podceňuje

    python3 kontrola_cisel.py
"""
import re
import sys
from pathlib import Path

import osoby as O


# ------------------------------------------------------------------ metriky

def generacie_nad(db, koren="veronika"):
    """Najhlbšia doložená línia predkov (koreň sa počíta ako generácia 0)."""
    if koren not in db:
        return 0
    hlbka, videne = {koren: 0}, {koren}
    front = [koren]
    while front:
        oid = front.pop()
        for r in db[oid].get("rodicia") or []:
            rid = r["id"] if isinstance(r, dict) else r
            if rid in db and rid not in videne:
                videne.add(rid)
                hlbka[rid] = hlbka[oid] + 1
                front.append(rid)
    return max(hlbka.values()) if hlbka else 0


def metriky(db):
    def ma_datum(o, pole):
        ev = o.get(pole)
        return isinstance(ev, dict) and bool(ev.get("datum"))

    return {
        "osoby": len(db),
        "dolozeni": sum(1 for o in db.values() if o.get("dolozeny")),
        "uplne_datumy": sum(1 for o in db.values() if ma_datum(o, "narodenie") and ma_datum(o, "umrtie")),
        "presny_den": sum(1 for o in db.values()
                          if isinstance(o.get("narodenie"), dict)
                          and o["narodenie"].get("presnost") == "den"),
        # dve rôzne, obe legitímne definície: „nad Veronikou" a „vrátane jej"
        "generacie": generacie_nad(db),
        "generacie_vratane": generacie_nad(db) + 1,
        "v_registri": sum(1 for o in db.values() if o.get("v_registri")),
    }


# ------------------------------------------------- tvrdenia, ktoré v textoch sú

TVRDENIA = [
    ("Časová os.md", None, None, None),  # (držané prázdne — os čísla netvrdí)
]

# (súbor, regex s jednou skupinou = číslo, metrika, popis tvrdenia)
KONTROLY = [
    ("../vault/Štatistiky.md",
     r"\*\*(\d+)\s*osôb má doložený rok narodenia aj úmrtia\*\*", "uplne_datumy",
     "osôb s narodením aj úmrtím"),
    ("../vault/Výskum v číslach.md",
     r"Doložené generácie nad Veronikou:\s*\**(\d+)", "generacie",
     "generácií nad Veronikou"),
    ("../vault/Výskum v číslach.md",
     r"Osôb v databáze:\s*\*\*(\d+)\*\*", "osoby",
     "osôb v poznámkach"),
    ("../vault/Výskum v číslach.md",
     r"s doloženým rokom narodenia aj úmrtia\s*\*\*(\d+)\*\*", "uplne_datumy",
     "osôb s doloženými dátumami"),
    ("landing.md",
     r"🌳\s*(\d+)\s*doložených generácií", "generacie_vratane",
     "doložených generácií (fakt-pas)"),
    ("landing.md",
     r"👥\s*(\d+)\+?\s*osôb", "osoby",
     "osôb (fakt-pas)"),
]


def tolerancia(surovy, text):
    """Z tvaru čísla v texte odvodí, ako prísne ho porovnávať."""
    okolie = text[max(0, surovy.start() - 3):surovy.end() + 2]
    if "~" in okolie or "≈" in okolie:
        return "priblizne"
    if "+" in text[surovy.end():surovy.end() + 2]:
        return "aspon"
    return "presne"


def main():
    db = O.nacitaj()
    m = metriky(db)
    tu = Path(__file__).parent

    print("Databáza hovorí:")
    for k, v in m.items():
        print(f"   {k:16} {v}")

    problemy, nenajdene = [], []
    for subor, vzor, metrika, popis in KONTROLY:
        cesta = (tu / subor).resolve()
        if not cesta.exists():
            nenajdene.append(f"{subor} (súbor neexistuje)")
            continue
        text = cesta.read_text(encoding="utf-8")
        # niektoré súbory sú vedomý snímok k dátumu, nie živé tvrdenie
        snimok = re.search(r"stav k (\d{1,2}\.\d{1,2}\.\d{4})", text[:400])
        n = re.search(vzor, text)
        if not n:
            nenajdene.append(f"{cesta.name}: „{popis}\" — tvrdenie sa nenašlo (prepísali ho?)")
            continue
        tvrdi, skutocnost = int(n.group(1)), m[metrika]
        rezim = tolerancia(n, text)

        znacka = f" [snímok k {snimok.group(1)}]" if snimok else ""
        if rezim == "presne" and tvrdi != skutocnost:
            problemy.append(f"{cesta.name}{znacka}: {popis} — text {tvrdi}, databáza {skutocnost}")
        elif rezim == "priblizne" and abs(tvrdi - skutocnost) > max(1, 0.2 * skutocnost):
            problemy.append(f"{cesta.name}{znacka}: {popis} — text ~{tvrdi}, databáza {skutocnost}"
                            f" (rozdiel nad 20 %)")
        elif rezim == "aspon":
            if skutocnost < tvrdi:
                problemy.append(f"{cesta.name}{znacka}: {popis} — text sľubuje aspoň {tvrdi},"
                                f" databáza má len {skutocnost}")
            elif skutocnost > tvrdi * 1.15:
                problemy.append(f"{cesta.name}{znacka}: {popis} — text hovorí {tvrdi}+,"
                                f" databáza {skutocnost} (tvrdenie sa podceňuje)")

    if problemy:
        print(f"\n⚠️  ZASTARANÉ ČÍSLA: {len(problemy)}")
        for p in problemy:
            print("   " + p)
    else:
        print("\nČísla v textoch sedia s databázou.")

    if nenajdene:
        print(f"\nnenašlo sa ({len(nenajdene)}) — kontrola stratila stopu, treba doladiť vzor:")
        for n in nenajdene:
            print("   " + n)

    return 1 if problemy else 0


if __name__ == "__main__":
    sys.exit(main())
