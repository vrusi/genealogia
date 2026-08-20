#!/usr/bin/env python3
"""Čítanie, kontrola a vykresľovanie databázy osôb (`vault/data/osoby.json`).

Formátovanie dátumov NIE JE v dátach — v nich je `datum` + `presnost`
a tvar sa rozhoduje až tu. Vďaka tomu sa rovnaká osoba nikde nemôže
zobraziť dvoma spôsobmi. Schéma: `vault/data/SCHEMA.md`.

Spustenie samostatne = kontrola databázy:
    python3 osoby.py            # skontroluje a vypíše problémy
"""
import json
import re
import sys
from pathlib import Path

PRESNOSTI = {"den", "mesiac", "rok", "okolo", "po", "pred", "rozsah", "neznama"}
VETVY = {"rusinko", "fejercak-gulas", "hanis-dzurenda", "hajman-skodova", "licko-lorenowicz"}
MESIACE_SK = "január február marec apríl máj jún júl august september október november december".split()


# ---------------------------------------------------------------- načítanie

def cesta_k_databaze():
    """Vault sa hľadá rovnako ako v publish.py — cesty sa líšia podľa stroja."""
    import os
    env = os.environ.get("GENEALOGIA_VAULT")
    kandidati = ([Path(env)] if env else []) + [
        Path("/Users/vrusi/Documents/Genealogia"),
        Path(__file__).resolve().parent.parent / "vault",
    ]
    for c in kandidati:
        if (c / "data" / "osoby.json").exists():
            return c / "data" / "osoby.json"
    raise SystemExit("osoby.json sa nenašiel. Nastav GENEALOGIA_VAULT=/cesta/k/vaultu")


def nacitaj(cesta=None):
    cesta = Path(cesta) if cesta else cesta_k_databaze()
    osoby = json.loads(cesta.read_text(encoding="utf-8"))
    return {o["id"]: o for o in osoby}


def nacitaj_pramene(cesta=None):
    cesta = Path(cesta) if cesta else cesta_k_databaze().parent / "pramene.json"
    if not cesta.exists():
        return {}
    return {p["id"]: p for p in json.loads(cesta.read_text(encoding="utf-8"))}


def ids(zoznam):
    """`rodicia`/`deti` sú objekty `{id, pramene}`; vráti holé id."""
    out = []
    for x in zoznam or []:
        if isinstance(x, dict):
            if x.get("id"):
                out.append(x["id"])
        else:
            out.append(x)
    return out


# ------------------------------------------------------------ vykresľovanie

def _rok(datum):
    return str(datum).split("-")[0]


def formatuj_udalost(ev):
    """Dátum bez značky (\\* alebo †). Vracia None, ak nie je čo vypísať."""
    if not ev:
        return None
    p = ev.get("presnost", "neznama")
    d = ev.get("datum")

    if p == "neznama" or (d is None and p != "rozsah"):
        return "?"
    if p == "den":
        r, m, den = str(d).split("-")
        return f"{int(den)}.{int(m)}.{r}"
    if p == "mesiac":
        r, m = str(d).split("-")[:2]
        return f"{int(m)}/{r}"
    if p == "rok":
        return _rok(d)
    if p == "okolo":
        return f"~{_rok(d)}"
    if p == "po":
        return f"po {_rok(d)}"
    if p == "pred":
        return f"pred {_rok(d)}"
    if p == "rozsah":
        rozsah = ev.get("rozsah") or []
        if len(rozsah) == 2:
            a, b = _rok(rozsah[0]), _rok(rozsah[1])
            if len(a) == 4 and len(b) == 4 and a[:2] == b[:2]:
                b = b[2:]          # 1838–41
            return f"~{a}–{b}"
        return "?"
    return "?"


def formatuj_zivot(osoba, s_miestom=True):
    """Riadok pre register osôb: `\\*1.4.1919 Košice, †5.4.1994 Košice`.

    Ak sa človek narodil a zomrel v ten istý deň, skráti sa na `\\*†15.2.1892`.
    """
    nar, umr = osoba.get("narodenie"), osoba.get("umrtie")

    if (nar and umr and nar.get("presnost") == "den"
            and nar.get("datum") == umr.get("datum")):
        kus = "\\*†" + formatuj_udalost(nar)
        if s_miestom and nar.get("miesto"):
            kus += f" {nar['miesto']}"
        return kus

    casti = []
    for ev, znak in ((nar, "\\*"), (umr, "†")):
        if not ev:
            continue
        if ev.get("presnost") == "neznama" and not ev.get("miesto"):
            # `\*?` píšeme len vtedy, keď o udalosti naozaj nič nevieme
            casti.append(znak + "?")
            continue
        kus = znak + formatuj_udalost(ev)
        if s_miestom and ev.get("miesto"):
            kus += f" {ev['miesto']}"
        casti.append(kus)
    return ", ".join(casti) if casti else "\\*? †?"


def cele_meno(osoba):
    meno = f"{osoba['meno']} {osoba['priezvisko']}".strip()
    if osoba.get("rodne_priezvisko"):
        meno += f" rod. {osoba['rodne_priezvisko']}"
    return meno


# ----------------------------------------------------------------- kontrola

def skontroluj(db):
    """Vráti zoznam problémov. Prázdny zoznam = databáza je v poriadku."""
    problemy = []
    P = problemy.append

    for oid, o in db.items():
        kde = f"[{oid}]"

        if not re.fullmatch(r"[a-z0-9-]+", oid):
            P(f"{kde} id nie je slug (malé písmená, číslice, pomlčky)")
        for pole in ("meno", "priezvisko", "pohlavie", "vetva", "dolozeny", "na_web"):
            if pole not in o:
                P(f"{kde} chýba povinné pole `{pole}`")
        if o.get("vetva") not in VETVY:
            P(f"{kde} neznáma vetva: {o.get('vetva')!r}")
        if o.get("pohlavie") not in ("m", "z", None):
            P(f"{kde} pohlavie musí byť m/z/null, je {o.get('pohlavie')!r}")

        for pole in ("narodenie", "umrtie"):
            ev = o.get(pole)
            if ev is None:
                continue
            p = ev.get("presnost")
            if p not in PRESNOSTI:
                P(f"{kde} {pole}: neznáma presnosť {p!r}")
                continue
            d = ev.get("datum")
            if p == "den" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d)):
                P(f"{kde} {pole}: presnosť `den` chce dátum RRRR-MM-DD, je {d!r}")
            if p == "mesiac" and not re.fullmatch(r"\d{4}-\d{2}", str(d)):
                P(f"{kde} {pole}: presnosť `mesiac` chce RRRR-MM, je {d!r}")
            if p in ("rok", "okolo", "po", "pred") and not re.fullmatch(r"\d{4}", _rok(d)):
                P(f"{kde} {pole}: presnosť `{p}` chce rok, je {d!r}")
            if p == "rozsah" and len(ev.get("rozsah") or []) != 2:
                P(f"{kde} {pole}: presnosť `rozsah` chce dvojicu v poli `rozsah`")
            if p == "neznama" and d is not None:
                P(f"{kde} {pole}: presnosť `neznama`, ale dátum je vyplnený ({d!r})")

        # udalosti majú rovnaké pravidlá dátumu ako narodenie a úmrtie
        for i, u in enumerate(o.get("udalosti") or []):
            if not isinstance(u, dict):
                P(f"{kde} udalosti[{i}]: očakáva sa objekt")
                continue
            if u.get("presnost") not in PRESNOSTI:
                P(f"{kde} udalosti[{i}]: neznáma presnosť {u.get('presnost')!r}")
            if not (u.get("popis") or u.get("typ")):
                P(f"{kde} udalosti[{i}]: udalosť bez popisu aj bez typu")
        for i, f in enumerate(o.get("fakty") or []):
            if not isinstance(f, dict) or not str(f.get("text") or "").strip():
                P(f"{kde} fakty[{i}]: fakt musí mať neprázdny `text`")
        h = o.get("hrob")
        if h is not None and (not isinstance(h, dict) or not h.get("miesto")):
            P(f"{kde} hrob: musí byť objekt s `miesto`")

        nar, umr = o.get("narodenie"), o.get("umrtie")
        if nar and umr and nar.get("datum") and umr.get("datum"):
            if _rok(umr["datum"]) < _rok(nar["datum"]):
                P(f"{kde} úmrtie je pred narodením")

        # odkazy musia viesť na existujúce osoby
        for pole in ("rodicia", "deti"):
            for ref in ids(o.get(pole)):
                if ref not in db:
                    P(f"{kde} {pole}: odkaz na neexistujúce id {ref!r}")
        for m in o.get("manzelia") or []:
            if isinstance(m, dict):
                if m.get("id") and m["id"] not in db:
                    P(f"{kde} manzelia: odkaz na neexistujúce id {m['id']!r}")
            else:
                P(f"{kde} manzelia: očakáva sa objekt s `id`, nie {type(m).__name__}")

        if o.get("dolozeny") is False and o.get("na_web") is True and not o.get("poznamka"):
            # Web zámerne ukazuje aj predkov, ktorých spojenie ešte nie je doložené
            # (v strome sú 🟡). Vyžadujeme však, aby výhrada bola napísaná v poznámke.
            P(f"{kde} nedoložená osoba ide na web, ale nemá `poznamka` s výhradou")

    # obojsmernosť vzťahov
    for oid, o in db.items():
        for dieta in ids(o.get("deti")):
            if dieta in db and oid not in ids(db[dieta].get("rodicia")):
                P(f"[{oid}] uvádza dieťa {dieta!r}, ale to ho nemá medzi rodičmi")
        for rodic in ids(o.get("rodicia")):
            if rodic in db and oid not in ids(db[rodic].get("deti")):
                P(f"[{oid}] uvádza rodiča {rodic!r}, ale ten ho nemá medzi deťmi")
        for m in o.get("manzelia") or []:
            if isinstance(m, dict) and m.get("id") in db:
                partner = db[m["id"]]
                partneri = [x.get("id") for x in (partner.get("manzelia") or []) if isinstance(x, dict)]
                if oid not in partneri:
                    P(f"[{oid}] uvádza manžela/ku {m['id']!r}, ale ten/tá ho/ju neuvádza")

    # odkazy na pramene musia viesť na existujúci záznam
    reg = nacitaj_pramene()
    if reg:
        def skontroluj_pramene(kde, zoznam):
            for pid in zoznam or []:
                if pid not in reg:
                    P(f"{kde}: odkaz na neexistujúci prameň {pid!r}")

        for oid, o in db.items():
            skontroluj_pramene(f"[{oid}] pramene", o.get("pramene"))
            for pole in ("narodenie", "umrtie"):
                ev = o.get(pole)
                if isinstance(ev, dict):
                    skontroluj_pramene(f"[{oid}] {pole}", ev.get("pramene"))
            for pole in ("rodicia", "deti", "manzelia", "bydliska", "povolanie",
                         "mena", "udalosti", "fakty"):
                for x in o.get(pole) or []:
                    if isinstance(x, dict):
                        skontroluj_pramene(f"[{oid}] {pole}", x.get("pramene"))
            if isinstance(o.get("hrob"), dict):
                skontroluj_pramene(f"[{oid}] hrob", o["hrob"].get("pramene"))

    return problemy


def main():
    cesta = cesta_k_databaze()
    db = nacitaj(cesta)
    problemy = skontroluj(db)
    print(f"Osôb v databáze: {len(db)}  ({cesta})")
    dolozenych = sum(1 for o in db.values() if o.get("dolozeny"))
    print(f"Z toho doložených: {dolozenych}, na web: {sum(1 for o in db.values() if o.get('na_web'))}")
    if problemy:
        print(f"\n⚠️  PROBLÉMOV: {len(problemy)}")
        for p in problemy:
            print("  " + p)
        return 1
    print("\nKONTROLA OSÔB: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
