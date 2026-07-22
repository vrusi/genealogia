# Mapa migrácií rodiny

Súvisí: [Prehľad](prehlad.md) · [Štatistiky](statistiky.md) · Interaktívna mapa presunov jednotlivých vetiev (farebne). Súradnice sú približné (obec, nie dom). Zostavené 22.7.2026.

<div id="mapa-migracie" style="height: 560px; border-radius: 8px; margin: 1em 0;"></div>

**Legenda:** 🟤 Hajman (Somogy→Budapešť→Košice) · 🟠 Suver (Mokrance→Budapešť→Košice) · 🔵 Ličko (Valaská→Jasov→Košice) · 🟢 Rusinko (Brežany→Rokycany→Košice) · 🟡 Hanis (Žipov→Košice) · 🔴 Lorenowicz (Halič→Chomutov→Košice) · 🟣 emigrácie (Montreal, USA, Nemecko, Bratislava)

Všetkých šesť línií sa zbieha v **Košiciach** — mesto pritiahlo rodinu z troch štátov a piatich regiónov v priebehu ~80 rokov (1900–1980), takmer vždy **za prácou** (železnica, železiarne VSS/VSŽ, remeslá).

## Košická mikromapa (kde rodina bývala)

<div id="mapa-kosice" style="height: 420px; border-radius: 8px; margin: 1em 0;"></div>

Hajmanovský klan býval v 30. rokoch **v jednom bloku**: matka Alžbeta so slobodnými synmi na Daniela Licharda 37, Jozef s rodinou na Skladnej 47 a Rudolf neskôr dostaval rodinný dom na Lichardovej 30 (rodina ho drží dodnes).

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
document.addEventListener("DOMContentLoaded", function() {
  var KE = [48.716, 21.256];
  var map = L.map('mapa-migracie').setView([48.5, 18.5], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '&copy; OpenStreetMap'}).addTo(map);

  function route(points, color, label) {
    L.polyline(points, {color: color, weight: 3, opacity: 0.75}).addTo(map).bindPopup(label);
    points.forEach(function(p, i) {
      L.circleMarker(p, {radius: i === points.length - 1 ? 5 : 4, color: color, fillOpacity: 0.9}).addTo(map).bindPopup(label);
    });
  }

  route([[46.75, 17.72], [47.50, 19.04], KE], '#8d6e63', 'Hajman: Szőlőskislak (Somogy) → Budapešť (1898) → Košice (1900)');
  route([[48.62, 21.03], [47.50, 19.04], KE], '#ef6c00', 'Suver: Mokrance → Budapešť (služba, 1898) → Košice (1900)');
  route([[48.79, 19.55], [48.68, 20.97], KE], '#1565c0', 'Ličko: Valaská (*1942) → Jasov → Košice (VSS)');
  route([[49.03, 21.12], [48.98, 21.10], KE], '#2e7d32', 'Rusinko: Brežany/Bujakov → Rokycany (1922) → Košice (dedo)');
  route([[48.99, 21.05], KE], '#f9a825', 'Hanis: Žipov → Košice (babka Anna)');
  route([[49.86, 22.60], [50.46, 13.41], KE], '#c62828', 'Lorenowicz: okolie Przemyśla → Chomutov (~1946) → Košice (VSŽ, ~60. roky)');
  route([KE, [45.50, -73.57]], '#6a1b9a', 'Rudolf Hajman ml.: Košice → Montreal (50.–60. roky)');
  route([[49.03, 21.65], [41.58, -73.96]], '#6a1b9a', 'Kartis (DNA vetva): Jasenovce → Roseton, NY (1909)');
  route([KE, [48.15, 17.11]], '#6a1b9a', 'Štefan Rusinko: Košice/Rokycany → Bratislava');
  route([KE, [48.37, 10.90]], '#6a1b9a', 'Zdena (Diana Fünfer): Košice → Augsburg');

  var mk = L.map('mapa-kosice').setView([48.709, 21.253], 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '&copy; OpenStreetMap'}).addTo(mk);
  [
    [[48.7085, 21.2555], 'Lichardova 30 — rodinný dom (Rudolf ho dostaval; predtým Hajmanovci, dnes Peter)'],
    [[48.7098, 21.2530], 'Skladná 47 — dom Jozefa Hajmana (hárok 1930)'],
    [[48.7090, 21.2565], 'Daniela Licharda 37 (1930: vdova Alžbeta + synovia, vr. Jána kožušníka)'],
    [[48.7060, 21.2500], 'Nemocnica Rastislavova (UNLP) — pôsobisko oboch Tiborov'],
    [[48.7000, 21.2530], 'Verejný cintorín — hroby sk. 1, 7B, 91, 1MÚZEUM'],
    [[48.7280, 21.2560], 'Košický rozhlas — orchester (Ladislav Hajman + Ferdinand Ginelli)']
  ].forEach(function(x) {
    L.marker(x[0]).addTo(mk).bindPopup(x[1]);
  });
});
</script>
