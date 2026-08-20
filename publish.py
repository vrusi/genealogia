#!/usr/bin/env python3
"""Publikuje genealogický vault na GitHub Pages: kopíruje obsahové .md,
prevádza wikilinky, sanitizuje kontakty žijúcich osôb. Spustiť z genealogia-web."""
import re, shutil
from pathlib import Path

# Cesta k vaultu sa líši podľa stroja: dá sa vynútiť premennou GENEALOGIA_VAULT,
# inak sa skúšajú známe umiestnenia (osobný laptop, firemný laptop, súrodenecký adresár).
import os
def _find_vault():
    env = os.environ.get("GENEALOGIA_VAULT")
    candidates = ([Path(env)] if env else []) + [
        Path("/Users/vrusi/Documents/Genealogia"),
        Path(__file__).resolve().parent.parent / "vault",
    ]
    for c in candidates:
        if (c / "Prehľad.md").exists():
            return c
    raise SystemExit(
        "Vault sa nenašiel. Skúšané:\n  " + "\n  ".join(str(c) for c in candidates)
        + "\nNastav GENEALOGIA_VAULT=/cesta/k/vaultu"
    )

VAULT = _find_vault()
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
    "Vetva Hajman-Škodová": "vetva-hajman-skodiova",
    "Štatistiky": "statistiky",
    "Mapa migrácií": "mapa-migracii",
}
# NEpublikované: Drafty emailov, Korešpondencia a úlohy, DNA matche (kontakty, stratégia, žijúci matchovia)

# samostatné HTML stránky v prilohy/ — dostanú wrapper .md s iframe + kontrolu JS syntaxe
HTML_PAGES = {
    "mapa-rodokmena": "Mapa rodokmeňa",
    "interaktivny-rodokmen": "Interaktívny rodokmeň",
}

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

def slugify(h: str) -> str:
    import unicodedata
    h = unicodedata.normalize("NFKD", h).encode("ascii", "ignore").decode()
    h = re.sub(r"[^\w\s-]", "", h).strip().lower()
    return re.sub(r"[\s]+", "-", h)

def osoby_boxes(text: str) -> str:
    """Stav osôb: tabuľky osôb -> boxíky s kotvami. Kotva = slugify(bunka Osoba);
    na tieto kotvy mieria tlačidlá ⓘ v interaktívnom rodokmeni."""
    out, lines = [], text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("| Osoba |"):
            i += 2  # hlavička + oddeľovač
            out.append('<div class="osoby-grid">')
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                name = cells[0].replace("\\", "")
                # kotvu môže bunka určiť výslovne cez `{#id}` (tak ju píše generátor
                # z databázy); bez nej sa odvodí z mena ako doteraz
                m_kotva = re.search(r"\{#([\w-]+)\}\s*$", name)
                explicit = m_kotva.group(1) if m_kotva else None
                if m_kotva:
                    name = name[:m_kotva.start()].strip()
                who = cells[1] if len(cells) > 1 else ""
                # markdown odkazy [text](#kotva) -> HTML (bunky sa emitujú ako čisté HTML)
                who = re.sub(r"\[([^\]]+)\]\((#[\w-]+)\)", r'<a href="\2">\1</a>', who)
                dates = (cells[2] if len(cells) > 2 else "").replace("\\", "")
                sl = explicit or slugify(name.replace("*", " "))
                out.append(f'<div class="osoba" id="{sl}"><b>{name.replace("**", "")}</b>'
                           f'<span class="osoba-kto">{who}</span>'
                           f'<span class="osoba-datumy">{dates}</span></div>')
                i += 1
            out.append('</div>')
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)

def main():
    # Register osôb a interaktívny strom sa GENERUJÚ z `vault/data/osoby.json`.
    # Robí sa to tu, aby sa nedalo omylom publikovať zo zastaraných súborov.
    try:
        import generuj
        print("Generujem z databázy osôb:")
        if generuj.main() != 0:
            raise SystemExit("Databáza osôb má problémy — publikovanie zastavené.")
    except ImportError:
        print("⚠️  generuj.py nenájdený — publikujem existujúce súbory")

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)
    for name, slug in FILES.items():
        src = VAULT / f"{name}.md"
        text = convert(src.read_text(encoding="utf-8"))
        if slug == "stav-osob":
            text = osoby_boxes(text)
        (DOCS / f"{slug}.md").write_text(text, encoding="utf-8")
        print(f"OK {name} -> {slug}.md")
    shutil.copytree(VAULT / "prilohy", DOCS / "prilohy")
    print("OK prilohy/")
    # wrapper pre interaktívnu mapu rodokmeňa (samostatný HTML v prílohách)
    # cache-buster z obsahu súboru — po každej zmene mapy sa iframe načíta nanovo
    import hashlib
    for stem, title in HTML_PAGES.items():
        vh = hashlib.md5((VAULT / "prilohy" / f"{stem}.html").read_bytes()).hexdigest()[:8]
        (DOCS / f"{stem}.md").write_text(
            f"# {title}\n\n"
            f"[Otvoriť na celú obrazovku](prilohy/{stem}.html?v={vh}){{target=_blank}}\n\n"
            f'<iframe src="../prilohy/{stem}.html?v={vh}" style="width:100%;height:80vh;border:1px solid #ccc;border-radius:8px;"></iframe>\n',
            encoding="utf-8")
        print(f"OK {stem} wrapper")
    shutil.copy(Path(__file__).parent / "landing.md", DOCS / "index.md")
    print("OK landing -> index.md")
    # panel stavu žiadostí — web-only, ručne udržiavaný (zdroj: Korešpondencia a úlohy, ktorá sa nepublikuje)
    shutil.copy(Path(__file__).parent / "stav-vyskumu.md", DOCS / "stav-vyskumu.md")
    print("OK stav-vyskumu.md")
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
    # 2) mŕtve interné kotvy (slug.md#kotva musí existovať ako nadpis alebo id boxíka)
    anchors = {}
    for f in DOCS.glob("*.md"):
        t = f.read_text(encoding="utf-8")
        anchors[f.name] = {slugify(m.group(1)) for m in re.finditer(r"^#+\s+(.*)$", t, re.M)} \
                        | {m.group(1) for m in re.finditer(r'id="([^"]+)"', t)}
    for f in sorted(DOCS.glob("*.md")):
        for m in re.finditer(r"\]\(([a-z0-9-]+\.md)#([^)\s]+)\)", f.read_text(encoding="utf-8")):
            tgt, a = m.group(1), m.group(2)
            if tgt in anchors and a not in anchors[tgt]:
                warn.append(f"{f.name}: mŕtva kotva → {tgt}#{a}")
    # 3) vault súbor, ktorý nie je publikovaný ani vedome vylúčený
    EXCLUDED = {"Drafty emailov", "Korešpondencia a úlohy", "DNA matche (Ancestry)", "Výskumný denník", "Výskum v číslach"}
    for f in sorted(VAULT.glob("*.md")):
        if f.stem not in FILES and f.stem not in EXCLUDED:
            warn.append(f"vault: '{f.name}' nie je vo FILES ani vo vylúčených — pridať alebo vylúčiť")
    # 4) clutter: procesné poznámky a nedoložení menovci nepatria na web
    CLUTTER = {
        r"`[A-Z0-9]{4}-[A-Z0-9]{3}`": "FamilySearch ID",
        r"ark:?\s*\d:\d:": "citácia ark",
        r"\bfilm 0\d{4,}": "číslo filmu",
        r"\bobr\. \d+": "číslo obrazu",
        r"\binv\. č\.": "inventárne číslo",
        r"\bmenovc?(a|i|ov|om)?\b|\bmenovec\b": "menovec s nedoloženým vzťahom",
        r"vzťah nedolo[žz]en|nedoložen[ýá] vzťah": "nedoložený vzťah",
        r"dohľadať|prelistovať|treba overiť|\bTODO\b": "pracovný pokyn",
    }
    for f in sorted(DOCS.glob("*.md")):
        t = f.read_text(encoding="utf-8")
        for pat, label in CLUTTER.items():
            m = re.search(pat, t)
            if m:
                line = t[:m.start()].count("\n") + 1
                warn.append(f"{f.name}:{line}: clutter ({label}) → patrí do Výskumného denníka: „{t[max(0, m.start()-40):m.end()+40].strip()}“")

    # 5) syntax inline JavaScriptu v samostatných HTML stránkach (chýbajúca čiarka rozbije celú stránku)
    import subprocess, tempfile
    for stem in HTML_PAGES:
        html = (VAULT / "prilohy" / f"{stem}.html").read_text(encoding="utf-8")
        js = "\n".join(re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", html, re.S))
        if js.strip():
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(js)
                tmp = f.name
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            if r.returncode != 0:
                warn.append(f"{stem}.html: CHYBA V JAVASCRIPTE → {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'neznáma'}")
    # 5b) tlačidlá ⓘ v interaktívnom rodokmeni musia mieriť na existujúce kotvy v Stave osôb
    strom = (VAULT / "prilohy" / "interaktivny-rodokmen.html").read_text(encoding="utf-8")
    for m in re.finditer(r'\.\./stav-osob/#([\w-]+)', strom):
        if m.group(1) not in anchors.get("stav-osob.md", set()):
            warn.append(f"interaktivny-rodokmen.html: kotva #{m.group(1)} v Stave osôb neexistuje")
    # 5c) krížové odkazy medzi boxíkmi v Stave osôb musia mieriť na existujúce boxíky
    so = (DOCS / "stav-osob.md").read_text(encoding="utf-8")
    so_ids = set(re.findall(r'id="([\w-]+)"', so))
    for a in re.findall(r'href="#([\w-]+)"', so):
        if a not in so_ids:
            warn.append(f"stav-osob.md: interný odkaz #{a} nemá boxík")

    # 6) web-only obsah zaostáva za vaultom? — porovnaj čerstvosť
    import os
    vault_newest = max(os.path.getmtime(f) for f in VAULT.glob("*.md"))
    for wo in [Path(__file__).parent / "landing.md", Path(__file__).parent / "stav-vyskumu.md", VAULT / "prilohy" / "mapa-rodokmena.html"]:
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
