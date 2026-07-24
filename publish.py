#!/usr/bin/env python3
"""Publikuje genealogický vault na GitHub Pages: kopíruje obsahové .md,
prevádza wikilinky, sanitizuje kontakty žijúcich osôb. Spustiť z genealogia-web."""
import re, shutil
from pathlib import Path

VAULT = Path("/Users/vrusi/Documents/Genealogia")
DOCS = Path(__file__).parent / "docs"

# publikované súbory: vault názov -> slug
FILES = {
    "Prehľad": "prehlad",
    "Rodokmeň": "rodokmen",
    "Časová os": "casova-os",
    "Stav osôb": "stav-osob",
    "Zamestnania v rodine": "zamestnania",
    "Vetva Rusinko": "vetva-rusinko",
    "Vetva Fejerčák-Guľas": "vetva-fejercak-gulas",
    "Vetva Hanis": "vetva-hanis",
    "Vetva Ličko": "vetva-licko",
    "Vetva Hajman-Škodiová": "vetva-hajman-skodiova",
    "Štatistiky": "statistiky",
    "Mapa migrácií": "mapa-migracii",
    "Výskum v číslach": "vyskum-v-cislach",
}
# NEpublikované: Drafty emailov, Korešpondencia a úlohy, DNA matche (kontakty, stratégia, žijúci matchovia)

# sanitizácia — kontakty a presné adresy žijúcich osôb
SANITIZE = [
    ("adresa 3025 Sherbrooke O (Sherbrooke Ouest, downtown/pri Westmount), PSČ H3Z 1A1, tel. 514-937-2590", "presná adresa a telefón v súkromných poznámkach"),
    ("3025 Sherbrooke O, H3Z 1A1, tel. 514-937-2590", "adresa a tel. v súkromných poznámkach"),
    ("3025 Sherbrooke O", "[adresa súkromne]"),
    ("514-937-2590", "[tel. súkromne]"),
    ("mobil **727 813 277**, e-mail **v.loren@seznam.cz**", "kontakt v súkromných poznámkach"),
    ("727 813 277", "[tel. súkromne]"),
    ("v.loren@seznam.cz", "[email súkromne]"),
    ("Kallenbergstr. 29, 70825 Korntal-Münchingen (pri Stuttgarte), tel. 0711 8 82 00 81", "Korntal-Münchingen pri Stuttgarte (detaily súkromne)"),
    ("Unterbergstr. 7, 83088 Kiefersfelden (Bavorsko, pri hraniciach s Rakúskom), tel. 08033 78 81", "Kiefersfelden, Bavorsko (detaily súkromne)"),
    ("Denninger Str. 200, 81927 München-Bogenhausen, tel. 089 93 72 52", "Mníchov-Bogenhausen (detaily súkromne)"),
    ("Trieda dukelských hrdinov 443/31", "[adresa súkromne]"),
    ("(MsÚ Brezno, 048/2856 506, margareta.lickova@brezno.sk)", "(MsÚ Brezno)"),
    ("(MsÚ Brezno, 048/2856 902)", "(MsÚ Brezno)"),
    ("margareta.lickova@brezno.sk", "[kontakt cez MsÚ Brezno]"),
    ("V registri SVJ Okružní 512/16, Liberec II-Nové Město (výbor 2002–2021) → tam zrejme býva/býval. ", ""),
    ("Okružní 512/16", "[adresa súkromne]"),
]

def convert(text: str) -> str:
    for old, new in SANITIZE:
        text = text.replace(old, new)
    # obrázkové embedy ![[prilohy/x.jpg]] -> ![](prilohy/x.jpg)
    text = re.sub(r"!\[\[([^\]]+?)\]\]", lambda m: f"![]({m.group(1).replace(' ', '%20')})", text)
    # wikilinky [[Názov]] / [[Názov|label]]
    def wl(m):
        target, label = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
        slug = FILES.get(target)
        return f"[{label}]({slug}.md)" if slug else label
    text = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", wl, text)
    return text

def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)
    for name, slug in FILES.items():
        src = VAULT / f"{name}.md"
        (DOCS / f"{slug}.md").write_text(convert(src.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"OK {name} -> {slug}.md")
    shutil.copytree(VAULT / "prilohy", DOCS / "prilohy")
    print("OK prilohy/")
    # wrapper pre interaktívnu mapu rodokmeňa (samostatný HTML v prílohách)
    (DOCS / "mapa-rodokmena.md").write_text(
        "# Mapa rodokmeňa\n\n"
        "[Otvoriť na celú obrazovku](prilohy/mapa-rodokmena.html){target=_blank}\n\n"
        '<iframe src="../prilohy/mapa-rodokmena.html" style="width:100%;height:80vh;border:1px solid #ccc;border-radius:8px;"></iframe>\n',
        encoding="utf-8")
    print("OK mapa-rodokmena wrapper")
    shutil.copy(Path(__file__).parent / "landing.md", DOCS / "index.md")
    print("OK landing -> index.md")
    shutil.copytree(Path(__file__).parent / "web-assets", DOCS / "stylesheets")
    print("OK stylesheets/")
    # kontrola, že nič citlivé nepretieklo
    leaked = []
    for f in DOCS.glob("*.md"):
        t = f.read_text(encoding="utf-8")
        for needle in ["21.11.1997", "Šancová 94", "Zvolská 695", "727 813", "514-937", "Sherbrooke", "seznam.cz", "Kallenbergstr", "Denninger", "Unterbergstr", "dukelských hrdinov 443"]:
            if needle in t:
                leaked.append((f.name, needle))
    print("LEAK CHECK:", leaked if leaked else "clean")
    consistency_checks()

def consistency_checks():
    """Kontroly, že sa pri update nezabudlo na nič — spúšťa sa pri každom publish."""
    import unicodedata
    warn = []
    # 1) pozostatky procesných poznámok v čitateľských súboroch
    STALE = ["~~", "predtým chybne", "chybne \u201e", "HYPOTÉZA VYVRÁTENÁ", "vyvrátené 1", "5× prastarí", "5x prastarí"]
    for f in sorted(DOCS.glob("*.md")):
        t = f.read_text(encoding="utf-8")
        for pat in STALE:
            if pat in t:
                warn.append(f"{f.name}: pozostatok iterácie '{pat}'")
    # 2) mŕtve interné kotvy (slug.md#kotva musí existovať ako nadpis)
    def slugify(h):
        h = unicodedata.normalize("NFKD", h).encode("ascii", "ignore").decode()
        h = re.sub(r"[^\w\s-]", "", h).strip().lower()
        return re.sub(r"[\s]+", "-", h)
    anchors = {}
    for f in DOCS.glob("*.md"):
        anchors[f.name] = {slugify(m.group(1)) for m in re.finditer(r"^#+\s+(.*)$", f.read_text(encoding="utf-8"), re.M)}
    for f in sorted(DOCS.glob("*.md")):
        for m in re.finditer(r"\]\(([a-z0-9-]+\.md)#([^)\s]+)\)", f.read_text(encoding="utf-8")):
            tgt, a = m.group(1), m.group(2)
            if tgt in anchors and a not in anchors[tgt]:
                warn.append(f"{f.name}: mŕtva kotva → {tgt}#{a}")
    # 3) vault súbor, ktorý nie je publikovaný ani vedome vylúčený
    EXCLUDED = {"Drafty emailov", "Korešpondencia a úlohy", "DNA matche (Ancestry)", "Výskumný denník"}
    for f in sorted(VAULT.glob("*.md")):
        if f.stem not in FILES and f.stem not in EXCLUDED:
            warn.append(f"vault: '{f.name}' nie je vo FILES ani vo vylúčených — pridať alebo vylúčiť")
    # 4) web-only obsah zaostáva za vaultom? — porovnaj čerstvosť
    import os
    vault_newest = max(os.path.getmtime(f) for f in VAULT.glob("*.md"))
    for wo in [Path(__file__).parent / "landing.md", VAULT / "prilohy" / "mapa-rodokmena.html"]:
        if os.path.getmtime(wo) < vault_newest - 3 * 86400:
            warn.append(f"web-only '{wo.name}' je o 3+ dní starší než najnovší vault súbor — prejsť, či nezaostal za novými faktami (fakt-pas, karty, kotvy, markery mapy)")
    if warn:
        print("KONTROLY: ⚠️")
        for w in warn:
            print("  -", w)
    else:
        print("KONTROLY: OK (pozostatky, kotvy, pokrytie, web-only čerstvosť)")

if __name__ == "__main__":
    main()
