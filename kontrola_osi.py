#!/usr/bin/env python3
"""Stráži, či sa Časová os a databáza osôb nerozchádzajú.

Časová os sa NEGENERUJE — spája viacero ľudí do jednej vety a pridáva
dobový kontext aj úsudok, ktoré do databázy nepatria. Automatické
prepísanie by ich zmazalo. Namiesto toho porovnávame dátumy: čo databáza
vie a os o tom mlčí (a naopak).

    python3 kontrola_osi.py
"""
import re
import sys
from pathlib import Path

import osoby as O


def datumy_v_osi(text):
    """Roky, ktoré sa v osi objavujú ako začiatok datovaného záznamu."""
    roky = set()
    presne = set()
    for riadok in text.splitlines():
        if not riadok.startswith("- "):
            continue
        hlava = riadok[:60]
        for m in re.finditer(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", hlava):
            d, mm, r = m.groups()
            presne.add(f"{r}-{int(mm):02d}-{int(d):02d}")
            roky.add(r)
        for m in re.finditer(r"\b(1[5-9]\d{2}|20\d{2})\b", hlava):
            roky.add(m.group(1))
    return presne, roky


def udalosti_v_db(db):
    """(dátum, id osoby, popis) pre všetko datované, čo o ľuďoch vieme."""
    von = []
    for o in db.values():
        for pole, stitok in (("narodenie", "narodenie"), ("umrtie", "úmrtie")):
            ev = o.get(pole)
            if isinstance(ev, dict) and ev.get("datum") and ev.get("presnost") in ("den", "mesiac", "rok"):
                von.append((str(ev["datum"]), o["id"], stitok))
        for u in o.get("udalosti") or []:
            if isinstance(u, dict) and u.get("datum") and u.get("presnost") in ("den", "mesiac", "rok"):
                von.append((str(u["datum"]), o["id"], u.get("typ") or (u.get("popis") or "")[:40]))
    return sorted(von)


def main():
    db = O.nacitaj()
    vault = O.cesta_k_databaze().parent.parent
    os_text = (vault / "Časová os.md").read_text(encoding="utf-8")

    presne, roky = datumy_v_osi(os_text)
    udalosti = udalosti_v_db(db)

    chyba_v_osi = []
    for datum, oid, co in udalosti:
        rok = datum.split("-")[0]
        if len(datum) == 10:
            if datum not in presne and rok not in roky:
                chyba_v_osi.append((datum, oid, co))
        elif rok not in roky:
            chyba_v_osi.append((datum, oid, co))

    print(f"Datovaných údajov v databáze: {len(udalosti)}")
    print(f"Rokov spomenutých v časovej osi: {len(roky)}")

    if chyba_v_osi:
        print(f"\n⚠️  V DATABÁZE JE, V ČASOVEJ OSI CHÝBA: {len(chyba_v_osi)}")
        for datum, oid, co in chyba_v_osi:
            meno = O.cele_meno(db[oid])
            print(f"   {datum:12} {meno} — {co}")
    else:
        print("\nČasová os pokrýva všetko, čo databáza datuje.")

    # roky, ktoré os spomína, ale databáza o nich nevie nič
    db_roky = {d.split("-")[0] for d, _, _ in udalosti}
    len_v_osi = sorted(r for r in roky if r not in db_roky)
    if len_v_osi:
        print(f"\nRoky, ktoré os spomína a databáza k nim nemá osobu: {', '.join(len_v_osi)}")
        print("   (často dobový kontext — vojny, hranice, revolúcie — a to je v poriadku)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
