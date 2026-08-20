#!/usr/bin/env python3
"""Generuje čitateľské súbory z databázy osôb.

Zdroj pravdy je `vault/data/osoby.json`. Tento skript z neho vyrába:
  - `vault/Stav osôb.md`                      (register osôb)
  - `vault/prilohy/interaktivny-rodokmen.html` (dátové pole stromu)

Súbory sa preto **needitujú ručne** — zmena patrí do databázy.

    python3 generuj.py           # zapíše
    python3 generuj.py --diff    # len ukáže, čo by sa zmenilo
"""
import json
import re
import sys
from pathlib import Path

import osoby as O

VETVY_PORADIE = [
    ("rusinko", "Vetva Rusinko"),
    ("fejercak-gulas", "Vetva Fejerčák–Guľas"),
    ("hanis-dzurenda", "Vetva Hanis–Dzurenda"),
    ("hajman-skodova", "Vetva Hajman–Škodová"),
    ("licko-lorenowicz", "Vetva Ličko–Lorenowicz"),
]

HLAVICKA = """# Register osôb — kto je kto

Súvisí: [[Prehľad]] · [[Rodokmeň]]

Prehľad doložených členov rodiny po vetvách. Uvedení sú ľudia, ktorých príbuznosť máme podloženú dokladom — matrikou, sčítacím hárkom, náhrobkom alebo úradným zápisom. Odkazy v stĺpci „Kto to je" fungujú na webe (skáču medzi boxíkmi osôb).

**Ako čítať dátumy:** \\*narodenie · †úmrtie · \\*† narodil sa a zomrel v ten istý deň · \\~približne · ? nevieme. Miesto sa uvádza, ak ho poznáme.

<!-- Tento súbor GENERUJE `web/generuj.py` z `vault/data/osoby.json`. Needituj ho ručne — zmena patrí do databázy. -->
"""


def register_md(db):
    riadky = [HLAVICKA]
    for vetva, nadpis in VETVY_PORADIE:
        ludia = [o for o in db.values() if o.get("v_registri") and o.get("vetva") == vetva]
        if not ludia:
            continue
        ludia.sort(key=lambda o: (o.get("poradie", 999), o["id"]))
        riadky.append(f"\n## {nadpis}\n")
        riadky.append("| Osoba | Kto to je | Dátumy |")
        riadky.append("|---|---|---|")
        for o in ludia:
            meno = o.get("zobrazenie") or O.cele_meno(o)
            if o.get("zvyraznene"):
                meno = f"**{meno}**"
            riadky.append(f"| {meno} {{#{o['id']}}} | {o.get('popis', '')} | {O.formatuj_zivot(o)} |")
    return "\n".join(riadky) + "\n"


def zamestnania_md(db, postrehy):
    """Tabuľky povolaní po vetvách. Meno odkazuje do registra osôb."""
    r = ["""# Zamestnania a povolania v rodine

Súvisí: [[Prehľad]] · [[Stav osôb]]

Ľudia s **doloženou príbuznosťou**, pri ktorých poznáme povolanie. Menovci sem nepatria. Meno odkazuje na ich záznam v registri osôb.

**Stĺpec „Život"** je dĺžka života, nie roky, v ktorých je človek doložený — tie sú
uvedené priamo pri povolaní (napr. „nádenník (1861, osada Csehi)"). Ak sa dátumy
nezachovali, stojí tam `\\*?`.

<!-- Tabuľky GENERUJE `web/generuj.py` z `vault/data/osoby.json`. Needituj ich ručne. -->

## Po vetvách"""]

    for vetva, nadpis in VETVY_PORADIE:
        # len doložená rodina — menovci (gréckokatolícky kňaz, bádateľ rusínskej
        # literatúry a i.) do prehľadu rodinných remesiel nepatria
        ludia = [o for o in db.values()
                 if o.get("vetva") == vetva and o.get("povolanie") and o.get("dolozeny")]
        if not ludia:
            continue
        ludia.sort(key=lambda o: (o.get("poradie", 999), o["id"]))
        r.append(f"\n### {nadpis.replace('Vetva ', '')}\n")
        r.append("| Osoba | Vzťah | Život | Zamestnanie | Prameň |")
        r.append("|---|---|---|---|---|")
        for o in ludia:
            # v registri stačí „Ján" (stojí pod hlavičkou vetvy), tu nie
            meno = o.get("zobrazenie") or O.cele_meno(o)
            if len(meno.split()) == 1:
                meno = O.cele_meno(o)
            odkaz = f"[{meno}](stav-osob.md#{o['id']})" if o.get("v_registri") else meno
            praca, pramene, texty = [], [], []
            for x in o["povolanie"]:
                praca.append(x.get("hodnota") if isinstance(x, dict) else str(x))
                if isinstance(x, dict):
                    pramene += x.get("pramene") or []
                    # prameň, ktorý zatiaľ nemá záznam v registri, ostáva ako veta
                    if x.get("pramen_text"):
                        texty.append(x["pramen_text"])
            zdroje = ", ".join(sorted(set(pramene)) + sorted(set(texty))) or "—"
            r.append(f"| {odkaz} | {o.get('vztah') or ''} | {O.formatuj_zivot(o, s_miestom=False)} "
                     f"| {'; '.join(praca)} | {zdroje} |")

    return "\n".join(r) + "\n\n" + postrehy.strip() + "\n"


def strom_data(db):
    """Dátové pole pre family-chart. Krátke id stromu zostávajú zachované."""
    kratke = {o["id"]: (o.get("strom_id") or o["id"]) for o in db.values()}

    def kr(oid):
        return kratke.get(oid)

    von = []
    for o in sorted((x for x in db.values() if x.get("v_strome")),
                    key=lambda x: (x.get("strom_poradie", 999), x["id"])):
        # family-chart pozná len dvoch rodičov; pri adopcii je v databáze aj tretí,
        # do stromu ide biologická dvojica (prvá v poradí) a adopcia je v poznámke
        rodicia = [kr(x["id"]) for x in o.get("rodicia") or [] if kr(x["id"]) and db.get(x["id"], {}).get("v_strome")][:2]
        manzelia = [kr(m["id"]) for m in o.get("manzelia") or []
                    if m.get("id") and kr(m["id"]) and db.get(m["id"], {}).get("v_strome")]
        deti = [kr(x["id"]) for x in o.get("deti") or [] if kr(x["id"]) and db.get(x["id"], {}).get("v_strome")]

        label = o.get("strom_label") or O.cele_meno(o)
        dates = O.formatuj_zivot(o, s_miestom=False).replace("\\*", "*").replace(", ", " ")
        # v strome je „*?" len šum — ak o narodení nevieme nič, nevypisuje sa
        dates = dates.replace("*? ", "").strip()
        if dates == "*?":
            dates = ""
        gender = "M" if o.get("pohlavie") == "m" else "F"

        rels = []
        if rodicia:
            rels.append("parents:[" + ",".join(f'"{x}"' for x in rodicia) + "]")
        if manzelia:
            rels.append("spouses:[" + ",".join(f'"{x}"' for x in manzelia) + "]")
        if deti:
            rels.append("children:[" + ",".join(f'"{x}"' for x in deti) + "]")

        link = f', link:P+"{o["id"]}"' if o.get("v_registri") else ""
        von.append(
            f'  {{id:"{kr(o["id"])}", data:{{gender:"{gender}", label:"{label}", '
            f'dates:"{dates}"{link}}},\n   rels:{{{", ".join(rels)}}}}},'
        )
    return "const DATA = [\n" + "\n".join(von) + "\n];"


def zapis(cesta, novy, diff_only):
    stary = cesta.read_text(encoding="utf-8") if cesta.exists() else ""
    if stary == novy:
        print(f"  = {cesta.name} (bez zmeny)")
        return 0
    if diff_only:
        import difflib
        rozdiel = list(difflib.unified_diff(
            stary.splitlines(), novy.splitlines(),
            fromfile=f"{cesta.name} (teraz)", tofile=f"{cesta.name} (z DB)", lineterm="", n=1))
        print(f"\n--- {cesta.name}: {sum(1 for l in rozdiel if l.startswith('+') and not l.startswith('+++'))} pridaných, "
              f"{sum(1 for l in rozdiel if l.startswith('-') and not l.startswith('---'))} odobraných riadkov")
        for l in rozdiel[:80]:
            print("   " + l)
        if len(rozdiel) > 80:
            print(f"   … ďalších {len(rozdiel) - 80} riadkov")
    else:
        cesta.write_text(novy, encoding="utf-8")
        print(f"  ✓ {cesta.name}")
    return 1


def main():
    diff_only = "--diff" in sys.argv
    db = O.nacitaj()
    problemy = O.skontroluj(db)
    if problemy:
        print(f"⚠️  Databáza má {len(problemy)} problémov — negenerujem.")
        for p in problemy[:10]:
            print("   " + p)
        return 1

    vault = O.cesta_k_databaze().parent.parent
    zmien = 0
    zmien += zapis(vault / "Stav osôb.md", register_md(db), diff_only)

    zam = vault / "Zamestnania v rodine.md"
    if zam.exists():
        stary = zam.read_text(encoding="utf-8")
        i = stary.find("## Postrehy")
        postrehy = stary[i:] if i >= 0 else ""
        zmien += zapis(zam, zamestnania_md(db, postrehy), diff_only)

    strom = vault / "prilohy" / "interaktivny-rodokmen.html"
    if strom.exists() and any(o.get("v_strome") for o in db.values()):
        html = strom.read_text(encoding="utf-8")
        novy_blok = strom_data(db)
        nove_html = re.sub(r"const DATA = \[.*?\n\];", novy_blok, html, flags=re.S)
        zmien += zapis(strom, nove_html, diff_only)

    if diff_only and zmien:
        print("\n(iba náhľad — zapíš spustením bez --diff)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
