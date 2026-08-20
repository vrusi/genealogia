#!/usr/bin/env python3
"""Stráži, či ručne písané poznámky nezostarli oproti databáze osôb.

Register a strom sa generujú, takže zostarnúť nemôžu. Rozprávanie
(Časová os, Rodokmeň, Prehľad, vetvy) sa píše ručne a **kopíruje údaje**,
ktoré v databáze medzitým pribudli alebo sa spresnili. Taká kópia potom
ticho klame.

Skutočný prípad z 20.8.2026: Časová os tvrdila „jeho rodičov zatiaľ
nepoznáme" ešte po tom, čo rodný list rodičov Jozefa Lička uviedol.

Kontroluje:
  A. dátum pri mene, ktorý si protirečí s databázou
  B. vety typu „nepoznáme / neznámy" pri človeku, o ktorom už vieme
  C. datované údaje z databázy, ktoré v Časovej osi chýbajú

    python3 kontrola_textov.py
"""
import re
import sys
import unicodedata
from pathlib import Path

import osoby as O

SUBORY = [
    "Časová os.md", "Rodokmeň.md", "Prehľad.md", "Štatistiky.md",
    "Zamestnania v rodine.md", "Mapa migrácií.md", "Výskum v číslach.md",
    "Vetva Rusinko.md", "Vetva Fejerčák-Guľas.md", "Vetva Hanis.md",
    "Vetva Hajman-Škodová.md", "Vetva Ličko.md",
]

NEVEDOMOSŤ = re.compile(
    r"(zatiaľ )?(ne(poznáme|vieme|máme)|neznám[yaeieho]+|nepozná|"
    r"nie (je|sú) (známy|známe|známa)|bez známeho)", re.I)


def bez_diakritiky(t):
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def mena_osoby(o):
    """Tvary, pod ktorými sa človek môže v texte objaviť."""
    von = set()
    meno, pr = o.get("meno") or "", o.get("priezvisko") or ""
    rod = o.get("rodne_priezvisko")
    for v in (f"{meno} {pr}", o.get("zobrazenie"), o.get("strom_label")):
        if v and len(v.split()) >= 2:
            von.add(bez_diakritiky(v))
    if rod:
        von.add(bez_diakritiky(f"{meno} rod. {rod}"))
        von.add(bez_diakritiky(f"{meno} {rod}"))
    return {v for v in von if len(v) > 8}


def znama_datumy(o):
    """{rok: (mesiac, den, čo to je)} pre všetko, čo o človeku datujeme."""
    von = {}
    for pole, stitok in (("narodenie", "narodenie"), ("umrtie", "úmrtie")):
        ev = o.get(pole)
        if isinstance(ev, dict) and ev.get("presnost") == "den" and ev.get("datum"):
            r, m, d = str(ev["datum"]).split("-")
            von.setdefault(r, []).append((int(m), int(d), stitok))
    for u in o.get("udalosti") or []:
        if isinstance(u, dict) and u.get("presnost") == "den" and u.get("datum"):
            r, m, d = str(u["datum"]).split("-")
            von.setdefault(r, []).append((int(m), int(d), u.get("typ") or "udalosť"))
    return von


def main():
    db = O.nacitaj()
    vault = O.cesta_k_databaze().parent.parent

    index = []                       # (vzor mena, osoba)
    for o in db.values():
        for v in mena_osoby(o):
            index.append((v, o))

    rozpory, zastarane = [], []

    for nazov in SUBORY:
        cesta = vault / nazov
        if not cesta.exists():
            continue
        for cislo, riadok in enumerate(cesta.read_text(encoding="utf-8").splitlines(), 1):
            if not riadok.strip() or riadok.startswith(("|---", "#")):
                continue
            hol = bez_diakritiky(riadok)
            # kde presne v riadku je ktoré meno — bez toho by sa každý dátum
            # pároval s každým človekom a vznikli by falošné rozpory
            vyskyty = []
            for v, o in index:
                poz = hol.find(v)
                if poz >= 0:
                    vyskyty.append((poz, poz + len(v), o))
            # „Jozef Ličko" je podreťazec mena „Jozef Ličko st." — na tej istej
            # pozícii si necháme len najdlhšiu zhodu, inak sa tvrdenie o otcovi
            # prilepí synovi
            vyskyty = [x for x in vyskyty
                       if not any(y is not x and y[0] <= x[0] and y[1] >= x[1]
                                  and (y[1] - y[0]) > (x[1] - x[0]) for y in vyskyty)]
            if not vyskyty:
                continue
            spomenuti = [o for _, _, o in vyskyty]

            # --- A. dátum, ktorý si protirečí ---
            # Strážca radšej mlčí, než by klamal: hlási len vtedy, keď je riadok
            # jednoznačný — jeden človek, jeden dátum a nejde o interval „X → Y"
            # (tabuľky odstupu narodenia od krstu). Inak sa dátum prilepí
            # k nesprávnemu menu a hlásenie je na nič.
            datumy = list(re.finditer(r"\b(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\b", riadok))
            jeden_datum = (len(datumy) == 1
                           and "→" not in riadok and "–" not in riadok)
            for m in (datumy if jeden_datum else []):
                den, mes, rok = int(m.group(1)), int(m.group(2)), m.group(3)
                # V rodine je 13 Márií, 13 Ánn a traja Jozefovia Hanisovci, takže
                # zhoda mena sama o sebe nestačí. Z uchádzačov necháme tých, čo
                # v danom roku vôbec nejaký dátum majú — ak zostane práve jeden,
                # vieme, o koho ide; ak viac, radšej mlčíme.
                # …a musia stáť pri dátume, nie kdekoľvek v riadku: „19.1.1945 —
                # oslobodenie Rokycian; 1945 — Ladislav Hajman sa vracia" nie je
                # Ladislavov dátum, hoci je v tom istom riadku
                uchadzaci = [o for z, k, o in vyskyty
                             if znama_datumy(o).get(rok)
                             and min(abs(m.start() - k), abs(z - m.end())) <= 40]
                if len({id(x) for x in uchadzaci}) != 1:
                    continue
                o = uchadzaci[0]
                zname = znama_datumy(o).get(rok)
                if not any(mm == mes and dd == den for mm, dd, _ in zname):
                    co = ", ".join(f"{dd}.{mm}.{rok} ({t})" for mm, dd, t in zname)
                    rozpory.append(
                        f"{nazov}:{cislo}  „{den}.{mes}.{rok}\" pri {O.cele_meno(o)}"
                        f" — databáza pozná v tom roku {co}")

            # --- B. tvrdenie o nevedomosti, hoci už vieme ---
            for mf in NEVEDOMOSŤ.finditer(riadok):
                # tvrdenie o nevedomosti platí pre meno, ktoré stojí najbližšie
                blizke = [o for z, k, o in vyskyty if abs(mf.start() - k) < 90 or abs(z - mf.end()) < 90]
                for o in blizke:
                    okno = bez_diakritiky(riadok[max(0, mf.start() - 90):mf.end() + 90])
                    vie = []
                    if (o.get("rodicia") or []) and re.search(r"rodic|otc|matk", okno):
                        vie.append("rodičov")
                    nar = o.get("narodenie")
                    # „rodisko" je miesto, nie dátum — nezamieňať
                    if isinstance(nar, dict) and re.search(r"rodisk|miesto naroden", okno):
                        if nar.get("miesto"):
                            vie.append(f"rodisko {nar['miesto']}")
                    elif isinstance(nar, dict) and nar.get("presnost") in ("den", "mesiac") \
                            and re.search(r"naroden", okno):
                        vie.append(f"narodenie {nar['datum']}")
                    umr = o.get("umrtie")
                    if isinstance(umr, dict) and umr.get("presnost") in ("den", "mesiac") \
                            and re.search(r"umrt|zomrel", okno):
                        vie.append(f"úmrtie {umr['datum']}")
                    if o.get("povolanie") and re.search(r"povolan|zamestnan", okno):
                        vie.append("povolanie")
                    if vie:
                        zastarane.append(
                            f"{nazov}:{cislo}  text hovorí, že nevieme, ale databáza pozná "
                            f"{', '.join(vie)} — {O.cele_meno(o)}\n      {riadok.strip()[:110]}")

    rozpory = sorted(set(rozpory))
    zastarane = sorted(set(zastarane))
    print(f"Prehľadaných súborov: {len(SUBORY)} · osôb v indexe: {len(db)}")

    if rozpory:
        print(f"\n⚠️  ROZPORNÉ DÁTUMY: {len(rozpory)}")
        for r in rozpory:
            print("   " + r)
    else:
        print("\nRozporné dátumy: žiadne.")

    if zastarane:
        print(f"\n⚠️  ZASTARANÉ TVRDENIA: {len(zastarane)}")
        for z in zastarane:
            print("   " + z)
    else:
        print("Zastarané tvrdenia: žiadne.")

    return 1 if (rozpory or zastarane) else 0


if __name__ == "__main__":
    sys.exit(main())
