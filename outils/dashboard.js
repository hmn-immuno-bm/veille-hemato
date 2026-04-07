const DATA = %%DATA%%;
const HORS_CHAMP = %%HORS_CHAMP%%;
const DIRECTIONS = %%DIRECTIONS%%;
const KEY_AUTHORS = %%KEY_AUTHORS%%;
const CONFERENCES = %%CONFERENCES%%;
const CLINICAL_TRIALS = %%CLINICAL_TRIALS%%;
function isKeyAuthor(a) {
  return KEY_AUTHORS.some(k => {
    const kl = k.toLowerCase();
    return (a.auteur && a.auteur.toLowerCase().includes(kl)) || (a.senior && a.senior.toLowerCase().includes(kl));
  });
}
const FB_KEY = 'veille_feedback_%%SEMAINE_SAFE%%';
const SAVED_FEEDBACK = %%FEEDBACK%%;
const IS_PUBLIC = window.location.hostname.includes('github.io');
if (IS_PUBLIC) document.body.classList.add('public-mode');
let feedback = {};
// Charger : d'abord les fichiers feedback exportés, puis localStorage par-dessus
if (!IS_PUBLIC) {
  try {
    Object.assign(feedback, SAVED_FEEDBACK);
    const stored = JSON.parse(localStorage.getItem(FB_KEY) || '{}');
    Object.assign(feedback, stored);
  } catch(e) {}
}
function saveFb() { if (!IS_PUBLIC) { try { localStorage.setItem(FB_KEY, JSON.stringify(feedback)); } catch(e) {} } }

const CAT_COLORS = {
  'ctDNA — Lymphomes': '#3b82f6',
  'Lymphomes': '#22c55e',
  'ctDNA — Méthodo': '#a855f7',
  'Immuno + ctDNA/Lymphome': '#eab308',
  'IA + Hémato': '#06b6d4',
  'Hémato générale': '#ef4444',
  'Preprint': '#f97316',
};
function catColor(c) { return CAT_COLORS[c] || '#64748b'; }

// --- KPI ---
function renderKPI() {
  const bar = document.getElementById('kpiBar');
  const total = DATA.length;
  const ifVals = DATA.filter(a => a.if_val > 0).map(a => a.if_val).sort((a,b) => a - b);
  const ifMedian = ifVals.length > 0 ? (ifVals.length % 2 === 0 ? ((ifVals[ifVals.length/2-1]+ifVals[ifVals.length/2])/2).toFixed(1) : ifVals[Math.floor(ifVals.length/2)].toFixed(1)) : '—';
  const journals = new Set();
  const firstAuthors = new Set();
  const seniorAuthors = new Set();
  DATA.forEach(a => {
    journals.add(a.journal);
    if (a.auteur) firstAuthors.add(a.auteur.trim().toLowerCase());
    if (a.senior) seniorAuthors.add(a.senior.trim().toLowerCase());
  });
  const kpis = [
    { val: total, label: 'Articles' },
    { val: ifMedian, label: 'IF médian' },
    { val: journals.size, label: 'Journaux' },
    { val: firstAuthors.size, label: '1ers auteurs' },
    { val: seniorAuthors.size, label: 'Équipes' },
  ];
  bar.innerHTML = kpis.map(k => `<div class="kpi"><div class="val">${k.val}</div><div class="label">${k.label}</div></div>`).join('');
}

// --- Top 3 ---
function renderTop3() {
  // Find the latest non-retro week
  const weeklyData = DATA.filter(a => !a.semaine.includes('retro') && !a.semaine.includes('RETRO') && !a.semaine.includes('-T'));
  const latestWeek = weeklyData.length > 0 ? weeklyData.map(a => a.semaine).sort().reverse()[0] : null;
  const pool = latestWeek ? DATA.filter(a => a.semaine === latestWeek) : DATA;
  const top = [...pool].sort((a,b) => b.score - a.score || b.if_val - a.if_val).slice(0, 3);
  const medals = ['1', '2', '3'];
  const rankClass = ['rank-1','rank-2','rank-3'];
  const weekLabel = latestWeek ? latestWeek : 'toutes périodes';
  document.getElementById('top3').innerHTML = `<div style="font-size:0.72rem;color:#64748b;margin-bottom:8px;text-align:center;grid-column:1/-1;">Semaine : ${esc(weekLabel)}</div>` + top.map((a, i) => `
    <div class="top-card">
      <div class="rank ${rankClass[i]}">#${medals[i]}</div>
      <div class="tc-title"><a href="${esc(a.doi_url)}" target="_blank">${esc(a.titre)}</a></div>
      <div class="tc-meta">
        <span>${esc(a.auteur)} / ${esc(a.senior)}</span> — <span class="journal">${esc(a.journal)}</span>
      </div>
      <div class="tc-tags">${a.tags ? esc(a.tags) : '\u00A0'}</div>
      <div class="tc-badges">
        <span class="badge badge-cat">${esc(a.categorie)}</span>
        ${a.if_val > 0 ? `<span class="badge" style="background:#422006;color:#fbbf24;">IF ${a.if_val.toFixed(1)}</span>` : ''}
        <span class="badge" style="background:#14532d;color:#4ade80;">Score ${a.score}</span>
      </div>
    </div>
  `).join('');
}

// --- Bar chart catégories ---
function renderCatChart() {
  const cats = {};
  DATA.forEach(a => { cats[a.categorie] = (cats[a.categorie] || 0) + 1; });
  const sorted = Object.entries(cats).sort((a,b) => b[1] - a[1]);
  const max = Math.max(...sorted.map(s => s[1]), 1);

  document.getElementById('chartCat').innerHTML = sorted.map(([cat, count]) => {
    const pct = (count / max * 100).toFixed(0);
    const color = catColor(cat);
    return `<div class="journal-row" onclick="document.getElementById('filterCat').value='${esc(cat)}';renderArticles();" title="Filtrer par ${esc(cat)}">
      <div class="journal-name">${esc(cat)}</div>
      <div class="journal-bar-wrap"><div class="journal-bar-fill" style="width:${pct}%;background:${color};">${count}</div></div>
      <div class="journal-if" style="min-width:40px;">${count} art.</div>
    </div>`;
  }).join('');
}

// --- Bubble chart Score vs IF ---
// --- Geo map ---
// Equirectangular projection: x=(lon+180)/360, y=(90-lat)/180
// Equirectangular coords: x=(lon+180)/360, y=(90-lat)/180
const GEO_COORDS = {
  US:[0.286,0.284], CN:[0.823,0.278], DE:[0.537,0.208], FR:[0.506,0.228], GB:[0.500,0.214],
  NL:[0.514,0.209], JP:[0.888,0.302], KR:[0.853,0.291], IT:[0.535,0.267], ES:[0.490,0.276],
  AU:[0.914,0.696], CA:[0.290,0.248], BR:[0.367,0.587], IL:[0.597,0.322], SE:[0.550,0.171],
  CH:[0.521,0.239], BE:[0.513,0.218], DK:[0.535,0.191], NO:[0.530,0.167], AT:[0.545,0.232],
  FI:[0.569,0.166], PL:[0.558,0.210], SG:[0.788,0.493], IN:[0.714,0.342], TW:[0.838,0.361],
  HK:[0.817,0.376], PT:[0.475,0.285], IE:[0.483,0.204], CZ:[0.540,0.222], GR:[0.566,0.289],
  TR:[0.592,0.278], ZA:[0.578,0.643], MX:[0.225,0.392], AR:[0.338,0.692], CL:[0.304,0.686],
  CO:[0.294,0.474], EG:[0.587,0.333], SA:[0.630,0.363], IR:[0.643,0.302], TH:[0.779,0.424],
  TZ:[0.609,0.538], UG:[0.591,0.498], KE:[0.602,0.507], NG:[0.521,0.449], NZ:[0.986,0.730],
};
const GEO_NAMES = {
  US:'États-Unis',CN:'Chine',DE:'Allemagne',FR:'France',GB:'Royaume-Uni',NL:'Pays-Bas',
  JP:'Japon',KR:'Corée du Sud',IT:'Italie',ES:'Espagne',AU:'Australie',CA:'Canada',
  BR:'Brésil',IL:'Israël',SE:'Suède',CH:'Suisse',BE:'Belgique',DK:'Danemark',
  NO:'Norvège',AT:'Autriche',FI:'Finlande',PL:'Pologne',SG:'Singapour',IN:'Inde',
  TW:'Taïwan',HK:'Hong Kong',PT:'Portugal',IE:'Irlande',CZ:'Tchéquie',GR:'Grèce',
  TR:'Turquie',ZA:'Afrique du Sud',MX:'Mexique',AR:'Argentine',CL:'Chili',
  CO:'Colombie',EG:'Égypte',SA:'Arabie Saoudite',IR:'Iran',TH:'Thaïlande',
  TZ:'Tanzanie',UG:'Ouganda',KE:'Kenya',NG:'Nigéria',NZ:'Nouvelle-Zélande',
};

function renderGeoMap() {
  const box = document.getElementById('geoMap');
  const legend = document.getElementById('geoLegend');
  const W = box.clientWidth || 500;
  const H = Math.round(W / 2);  // 2:1 ratio for equirectangular projection
  box.style.height = H + 'px';

  // Collect per-country data with categories
  const countries = {};
  const countryCats = {};
  DATA.forEach(a => {
    if (a.pays) {
      countries[a.pays] = (countries[a.pays] || 0) + 1;
      if (!countryCats[a.pays]) countryCats[a.pays] = {};
      countryCats[a.pays][a.categorie] = (countryCats[a.pays][a.categorie] || 0) + 1;
    }
  });

  if (Object.keys(countries).length === 0) {
    box.innerHTML = '<div style="text-align:center;padding:40px;color:#475569;font-size:0.8rem;">Données géographiques non disponibles</div>';
    return;
  }

  const maxCount = Math.max(...Object.values(countries), 1);

  // PNG world map as background image
  box.style.backgroundImage = 'url(data:image/jpeg;base64,%%WORLD_MAP_B64%%)';
  box.style.backgroundSize = '100% 100%';
  box.style.backgroundPosition = 'center';
  box.style.backgroundRepeat = 'no-repeat';
  let html = '';

  // Place dots with colors by dominant category
  const sorted = Object.entries(countries).sort((a,b) => b[1] - a[1]);
  sorted.forEach(([code, count]) => {
    const coords = GEO_COORDS[code];
    if (!coords) return;
    const x = coords[0] * W;
    const y = coords[1] * H;
    const r = Math.max(14, Math.min(32, 10 + (count / maxCount) * 22));
    // Color by dominant category for this country
    const cats = countryCats[code] || {};
    const domCat = Object.entries(cats).sort((a,b) => b[1] - a[1])[0];
    const color = domCat ? catColor(domCat[0]) : '#38bdf8';
    const name = GEO_NAMES[code] || code;
    const catList = Object.entries(cats).map(([c,n]) => `${c}: ${n}`).join(', ');
    const glow = Math.min(16, 6 + count * 2);
    html += `<div class="geo-dot" style="left:${x-r/2}px;top:${y-r/2}px;width:${r}px;height:${r}px;background:radial-gradient(circle at 35% 35%, ${color}ee, ${color}88);box-shadow:0 0 ${glow}px ${color}50, 0 0 ${glow*2}px ${color}20;cursor:pointer;" onclick="document.getElementById('searchBox').value='pays:${code}';document.getElementById('filterCat').value='';renderArticles();" title="Filtrer par ${esc(name)}">
      <span style="font-size:${Math.max(9,r*0.38)}px;font-weight:700;color:white;text-shadow:0 1px 4px rgba(0,0,0,0.9);pointer-events:none;">${count}</span>
      <div class="geo-tip"><b>${esc(name)}</b> — ${count} article${count>1?'s':''}<br><span style="font-size:0.6rem;color:#94a3b8;">${esc(catList)}</span></div>
    </div>`;
  });

  box.innerHTML = html;

  // Legend with colored dots
  legend.innerHTML = sorted.map(([code, count]) => {
    const name = GEO_NAMES[code] || code;
    const cats = countryCats[code] || {};
    const domCat = Object.entries(cats).sort((a,b) => b[1] - a[1])[0];
    const color = domCat ? catColor(domCat[0]) : '#38bdf8';
    return `<span class="geo-legend-item" style="cursor:pointer;" onclick="document.getElementById('searchBox').value='pays:${code}';document.getElementById('filterCat').value='';renderArticles();" title="Filtrer par ${name}"><span class="geo-legend-dot" style="background:${color};"></span>${name} (${count})</span>`;
  }).join('');
}

// --- Journal bars ---
function renderJournals() {
  const jMap = {};
  const jIF = {};
  DATA.forEach(a => {
    jMap[a.journal] = (jMap[a.journal] || 0) + 1;
    if (a.if_val > 0) jIF[a.journal] = Math.max(jIF[a.journal] || 0, a.if_val);
  });
  const sorted = Object.entries(jMap).sort((a,b) => b[1] - a[1] || (jIF[b[0]] || 0) - (jIF[a[0]] || 0));

  // Séparer journaux fréquents (≥2 articles) et rares (1 article)
  const main = sorted.filter(([,n]) => n >= 2);
  const rare = sorted.filter(([,n]) => n === 1);
  const maxN = main.length > 0 ? main[0][1] : 1;

  let html = main.map(([j, n]) => {
    const pct = (n / maxN * 100).toFixed(0);
    const ifVal = jIF[j] || 0;
    const color = ifVal >= 30 ? '#7c3aed' : ifVal >= 10 ? '#3b82f6' : ifVal >= 5 ? '#06b6d4' : '#475569';
    const ifParts = ifVal > 0 ? ifVal.toFixed(1).split('.') : null;
    const ifStr = ifParts ? `<span class="if-int">${ifParts[0]}</span><span class="if-dot">.</span><span class="if-dec">${ifParts[1]}</span><span class="if-label">IF</span>` : '';
    return `<div class="journal-row" onclick="document.getElementById('searchBox').value='${esc(j)}';renderArticles();" title="Filtrer par ${esc(j)}">
      <div class="journal-name">${esc(j)}</div>
      <div class="journal-bar-wrap"><div class="journal-bar-fill" style="width:${pct}%;background:${color};">${n}</div></div>
      <div class="journal-if">${ifStr}</div>
    </div>`;
  }).join('');

  // Groupe "Autres" pour les journaux à 1 article
  if (rare.length > 0) {
    const avgIF = rare.reduce((s,[j]) => s + (jIF[j] || 0), 0) / rare.length;
    const rareNames = rare.map(([j]) => {
      const ifVal = jIF[j] || 0;
      return `<span style="cursor:pointer;transition:color 0.15s;" onmouseenter="this.style.color='#93c5fd'" onmouseleave="this.style.color='#94a3b8'" onclick="document.getElementById('searchBox').value='${esc(j)}';renderArticles();" title="IF ${ifVal.toFixed(1)}">${esc(j)}</span>`;
    }).join(' · ');
    const pct = (rare.length / maxN * 100).toFixed(0);
    html += `<div class="journal-row" style="margin-top:8px;border-top:1px solid #1e293b;padding-top:8px;">
      <div class="journal-name" style="color:#64748b;">Autres (1 article)</div>
      <div class="journal-bar-wrap"><div class="journal-bar-fill" style="width:${pct}%;background:#475569;">${rare.length}</div></div>
      <div class="journal-if"><span class="if-int">${avgIF.toFixed(1).split('.')[0]}</span><span class="if-dot">.</span><span class="if-dec">${avgIF.toFixed(1).split('.')[1]}</span><span class="if-label">IF</span></div>
    </div>
    <div style="font-size:0.65rem;color:#94a3b8;line-height:1.8;padding:6px 0 0 0;">${rareNames}</div>`;
  }

  document.getElementById('journalList').innerHTML = html;
}

// --- Tag cloud ---
// Consistent tag color mapping (used in tag cloud AND trends)
const TAG_COLORS = {};
const TAG_BG = {};
const TAG_PALETTE_BG = ['#172554','#1e1b4b','#14532d','#422006','#450a0a','#134e4a','#312e81','#1c1917','#162231','#27183b'];
const TAG_PALETTE_FG = ['#93c5fd','#c4b5fd','#86efac','#fcd34d','#fca5a5','#5eead4','#a5b4fc','#d6d3d1','#7dd3fc','#e9d5ff'];
let TAG_COLOR_INDEX = 0;
function tagColor(tag) {
  if (!TAG_COLORS[tag]) {
    const i = TAG_COLOR_INDEX % TAG_PALETTE_BG.length;
    TAG_BG[tag] = TAG_PALETTE_BG[i];
    TAG_COLORS[tag] = TAG_PALETTE_FG[i];
    TAG_COLOR_INDEX++;
  }
  return {bg: TAG_BG[tag], fg: TAG_COLORS[tag]};
}

function renderTagCloud() {
  const tags = {};
  DATA.forEach(a => {
    if (a.tags) a.tags.split(',').forEach(t => {
      const tag = t.trim();
      if (tag) tags[tag] = (tags[tag] || 0) + 1;
    });
  });
  const sorted = Object.entries(tags).sort((a,b) => b[1] - a[1]).slice(0, 25);
  const maxCount = sorted.length > 0 ? sorted[0][1] : 1;

  // Assign colors in order of frequency
  sorted.forEach(([tag]) => tagColor(tag));

  // Word cloud: size from 0.7rem (min) to 2.2rem (max), logarithmic scale
  const minSize = 0.7, maxSize = 2.2;
  const minCount = sorted.length > 0 ? sorted[sorted.length - 1][1] : 1;
  const logMax = Math.log(maxCount + 1), logMin = Math.log(minCount);
  const range = logMax - logMin || 1;

  // Shuffle for visual variety (but keep deterministic with seed)
  const shuffled = [...sorted].sort((a, b) => {
    const ha = Array.from(a[0]).reduce((s, c) => s + c.charCodeAt(0), 0);
    const hb = Array.from(b[0]).reduce((s, c) => s + c.charCodeAt(0), 0);
    return (ha % 7) - (hb % 7);
  });

  document.getElementById('tagCloud').innerHTML = shuffled.map(([tag, count]) => {
    const size = minSize + ((Math.log(count + 1) - logMin) / range) * (maxSize - minSize);
    const c = tagColor(tag);
    return `<span class="tag-word" style="font-size:${size.toFixed(2)}rem;color:${c.fg};"
      title="${count} articles"
      onclick="document.getElementById('searchBox').value='tag:${esc(tag)}';renderArticles();">${esc(tag)}</span>`;
  }).join('');
}

// --- Trends ---
function renderTrends() {
  if (DATA.length === 0) return;
  document.getElementById('trendsSection').style.display = 'block';

  const catColors = {
    'ctDNA — Lymphomes': '#3b82f6', 'Immuno + ctDNA/Lymphome': '#8b5cf6',
    'ctDNA — Méthodo': '#06b6d4', 'Lymphomes': '#22c55e',
    'IA + Hémato': '#f59e0b', 'Hémato générale': '#6b7280', 'Preprint': '#94a3b8',
  };
  const allCats = Object.keys(catColors);

  // Aggregate by week — ONLY weekly periods (YYYY-SNN format)
  const weeks = {};
  DATA.forEach(a => {
    const sem = a.semaine;
    // Ne garder QUE les semaines ISO (2026-S13, etc.)
    if (!/^\d{4}-S\d{1,2}$/.test(sem)) return;
    if (!weeks[sem]) weeks[sem] = { count: 0, scoreSum: 0, cats: {} };
    const w = weeks[sem];
    w.count++;
    w.scoreSum += a.score;
    w.cats[a.categorie] = (w.cats[a.categorie] || 0) + 1;
  });
  const allSorted = Object.entries(weeks)
    .sort((a,b) => a[0].localeCompare(b[0]));

  // Limiter aux 12 dernières semaines significatives
  const sorted = allSorted.slice(-12);
  const maxCount = Math.max(...sorted.map(s => s[1].count), 1);

  // --- Signaux clés (en haut, sous forme de pills) --- Privilégier les % aux valeurs brutes
  const total = DATA.length;
  const highScore = DATA.filter(a => a.score >= 8).length;
  const highScorePct = total > 0 ? Math.round(highScore / total * 100) : 0;
  const ctdnaCount = DATA.filter(a => (a.categorie || '').toLowerCase().includes('ctdna')).length;
  const ctdnaPct = total > 0 ? Math.round(ctdnaCount / total * 100) : 0;
  const frCount = DATA.filter(a => a.affFR === 'Oui').length;
  const frPct = total > 0 ? Math.round(frCount / total * 100) : 0;
  const preprintCount = DATA.filter(a => (a.preprint || '').toLowerCase().includes('preprint')).length;
  const preprintPct = total > 0 ? Math.round(preprintCount / total * 100) : 0;
  const lymphomeCount = DATA.filter(a => (a.categorie || '').toLowerCase().includes('lymphome')).length;
  const lymphomePct = total > 0 ? Math.round(lymphomeCount / total * 100) : 0;

  const pills = [];
  if (highScorePct > 0) pills.push(`<span class="signal-pill" style="border-color:#22c55e;"><b>${highScorePct}%</b> score ≥ 8</span>`);
  if (ctdnaPct > 0) pills.push(`<span class="signal-pill" style="border-color:#06b6d4;"><b>${ctdnaPct}%</b> ctDNA</span>`);
  if (lymphomePct > 0) pills.push(`<span class="signal-pill" style="border-color:#3b82f6;"><b>${lymphomePct}%</b> lymphomes</span>`);
  if (frPct > 0) pills.push(`<span class="signal-pill" style="border-color:#f59e0b;"><b>${frPct}%</b> affil. FR</span>`);
  if (preprintPct > 0) pills.push(`<span class="signal-pill" style="border-color:#94a3b8;"><b>${preprintPct}%</b> preprints</span>`);

  document.getElementById('trendSignals').innerHTML = `<div style="display:flex;gap:8px;flex-wrap:wrap;">${pills.join('')}</div>`;

  // --- Stacked bar chart (volume + catégories) ---
  const stackedDiv = document.getElementById('trendStacked');
  stackedDiv.innerHTML = sorted.map(([sem, d]) => {
    const segments = allCats.map(cat => {
      const n = d.cats[cat] || 0;
      if (n === 0) return '';
      const pct = (n / maxCount * 100).toFixed(1);
      return `<div style="width:${pct}%;background:${catColors[cat]};height:100%;display:inline-flex;align-items:center;justify-content:center;font-size:0.6rem;color:#fff;font-weight:600;" title="${cat}: ${n}">${n}</div>`;
    }).join('');
    return `<div class="bar-row">
      <div class="bar-label">${esc(sem)}</div>
      <div class="bar-track" style="display:flex;overflow:hidden;border-radius:4px;height:22px;">${segments}</div>
      <div style="font-size:0.7rem;color:#64748b;min-width:24px;text-align:right;">${d.count}</div>
    </div>`;
  }).join('') + `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;">${allCats.map(c => `<span style="display:flex;align-items:center;gap:4px;font-size:0.65rem;"><span style="width:10px;height:10px;border-radius:3px;background:${catColors[c]};"></span><span style="color:#94a3b8;">${c}</span></span>`).join('')}</div>`;

  // --- Score moyen ---
  document.getElementById('trendScores').innerHTML = sorted.map(([sem, d]) => {
    const avg = (d.scoreSum / d.count).toFixed(1);
    const pct = (avg / 10 * 100).toFixed(0);
    const color = avg >= 7 ? '#22c55e' : avg >= 5 ? '#eab308' : '#ef4444';
    return `<div class="bar-row">
      <div class="bar-label">${esc(sem)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${color};"><span class="bar-val">${avg}</span></div></div>
    </div>`;
  }).join('');

}

// --- Populate dynamic filter dropdowns ---
function populateFilters() {
  const catSet = new Set(), semSet = new Set();
  DATA.forEach(a => { catSet.add(a.categorie); semSet.add(a.semaine); });

  const catSel = document.getElementById('filterCat');
  [...catSet].sort().forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o);
  });

  const semSel = document.getElementById('filterSem');
  const semArr = [...semSet].sort().reverse();

  // Classify semaines into groups
  const weekly = semArr.filter(s => /^\d{4}-S\d+$/.test(s));
  const hasRetro = semArr.includes('retro');

  // 1. Latest week shortcut
  if (weekly.length > 0) {
    const latest = weekly[0];
    const oLatest = document.createElement('option');
    oLatest.value = latest;
    oLatest.textContent = `★ ${latest} (dernière semaine)`;
    oLatest.style.fontWeight = '700';
    semSel.appendChild(oLatest);
  }

  // 2. Retro
  if (hasRetro) {
    const addSep = () => { const s = document.createElement('option'); s.disabled = true; s.textContent = '───────────'; semSel.appendChild(s); };
    addSep();
    const o = document.createElement('option'); o.value = 'retro'; o.textContent = '📚 Rétrospective (2012-2025)'; o.style.fontWeight = '600'; semSel.appendChild(o);
  }

  // 3. Weekly
  if (weekly.length > 1) {
    const addSep = () => { const s = document.createElement('option'); s.disabled = true; s.textContent = '───────────'; semSel.appendChild(s); };
    addSep();
    const oLabel = document.createElement('option'); oLabel.disabled = true; oLabel.textContent = '── Par semaine ──'; oLabel.style.color = '#64748b'; semSel.appendChild(oLabel);
    weekly.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = s; semSel.appendChild(o); });
  }
}

function resetAllFilters() {
  document.getElementById('filterCat').value = '';
  document.getElementById('filterSem').value = '';
  document.getElementById('sortBy').value = 'score';
  document.getElementById('searchBox').value = '';
  document.getElementById('filterFb').value = '';
  renderArticles();
}

// --- Articles ---
const PAGE_SIZE = 10;
let currentPage = 0;
let currentFiltered = [];

function renderArticles(resetPage) {
  if (resetPage !== false) currentPage = 0;
  const catFilter = document.getElementById('filterCat').value;
  const semFilter = document.getElementById('filterSem').value;
  const sortBy = document.getElementById('sortBy').value;
  const search = document.getElementById('searchBox').value.toLowerCase();
  const fbFilter = document.getElementById('filterFb').value;

  let filtered = DATA.filter(a => {
    if (catFilter && a.categorie !== catFilter) return false;
    if (semFilter && a.semaine !== semFilter) return false;
    if (search) {
      const paysMatch = search.match(/^pays:([a-z]{2})$/i);
      const tagMatch = search.match(/^tag:(.+)$/i);
      if (paysMatch) {
        if ((a.pays || '').toLowerCase() !== paysMatch[1].toLowerCase()) return false;
      } else if (tagMatch) {
        const needle = tagMatch[1].toLowerCase();
        const articleTags = (a.tags || '').split(',').map(t => t.trim().toLowerCase());
        if (!articleTags.includes(needle)) return false;
      } else {
        // Recherche full-text multi-token (AND) sur tous les champs textuels
        const hay = [
          a.titre, a.auteur, a.senior, a.tags, a.journal, a.resume,
          a.critique, a.categorie, a.doi, a.pmid, a.pays, a.date_pub
        ].filter(Boolean).join(' ').toLowerCase();
        // Tokens entre guillemets : recherche exacte ; sinon split par espace, tous doivent matcher
        const quoted = [...search.matchAll(/"([^"]+)"/g)].map(m => m[1]);
        const rest = search.replace(/"[^"]+"/g, ' ').split(/\s+/).filter(Boolean);
        const tokens = [...quoted, ...rest];
        if (!tokens.every(t => hay.includes(t))) return false;
      }
    }
    if (fbFilter) {
      const fb = feedback[a.doi] || 'none';
      if (fb !== fbFilter) return false;
    }
    return true;
  });

  if (sortBy === 'score') filtered.sort((a, b) => b.score - a.score || b.if_val - a.if_val);
  else if (sortBy === 'if') filtered.sort((a, b) => b.if_val - a.if_val);
  else if (sortBy === 'date') filtered.sort((a, b) => (b.date_pub || '').localeCompare(a.date_pub || '') || b.score - a.score);
  else if (sortBy === 'cat') filtered.sort((a, b) => a.categorie.localeCompare(b.categorie));
  else if (sortBy === 'journal') filtered.sort((a, b) => a.journal.localeCompare(b.journal));

  currentFiltered = filtered;
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (currentPage >= totalPages) currentPage = Math.max(0, totalPages - 1);
  const start = currentPage * PAGE_SIZE;
  const pageData = filtered.slice(start, start + PAGE_SIZE);

  document.getElementById('countBar').textContent = `${filtered.length} article${filtered.length > 1 ? 's' : ''} sur ${DATA.length} — Page ${currentPage + 1}/${totalPages || 1}`;

  const container = document.getElementById('articlesList');
  if (filtered.length === 0) {
    container.innerHTML = '<div class="no-results">Aucun article ne correspond aux filtres.</div>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  container.innerHTML = pageData.map((a, i) => {
    const idx = start + i;
    const fb = feedback[a.doi] || '';
    const ka = isKeyAuthor(a);
    const badges = [];
    if (a.categorie) badges.push(`<span class="badge badge-cat" style="border-left:3px solid ${catColor(a.categorie)};">${esc(a.categorie)}</span>`);
    if (a.tags) {
      a.tags.split(',').slice(0, 4).forEach(t => {
        const tag = t.trim();
        if (tag) badges.push(`<span class="badge badge-tag">${esc(tag)}</span>`);
      });
    }
    if (a.preprint && a.preprint !== 'Publié') badges.push(`<span class="badge badge-preprint">${esc(a.preprint)}</span>`);
    if (a.affFR === 'Oui') badges.push(`<span class="badge badge-fr">FR</span>`);
    if (a.pays) badges.push(`<span class="badge" style="background:#172554;color:#7dd3fc;">${esc(a.pays)}</span>`);

    // Score decomposition (estimate from available data if score_detail not present)
    const sd = a.score_detail || estimateScoreDetail(a);

    const cardId = 'resume-' + idx;
    return `<div class="card" data-doi="${esc(a.doi)}">
      <div class="card-header">
        <div class="card-title">
          <a href="${esc(a.doi_url)}" target="_blank" rel="noopener">${esc(a.titre)}</a>
          <div class="card-meta">
            ${esc(a.auteur)}${a.senior ? ' / ' + esc(a.senior) : ''} —
            <span class="journal">${esc(a.journal)}</span>
            ${a.if_val > 0 ? `<span class="if-badge">IF ${a.if_val.toFixed(1)}</span>` : ''}
            <span class="score-badge">Score ${a.score}/10</span>
            <span style="font-size:0.65rem;color:#475569;margin-left:4px;">${esc(a.semaine)}</span>
            ${a.date_pub ? `<span style="font-size:0.65rem;color:#64748b;margin-left:4px;">Pub. ${esc(a.date_pub)}</span>` : ''}
            ${a.pmid ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${esc(a.pmid)}/" target="_blank" style="font-size:0.65rem;color:#475569;margin-left:4px;text-decoration:none;">PMID:${esc(a.pmid)}</a>` : ''}
            ${a.citations > 0 ? `<span style="font-size:0.65rem;color:#64748b;margin-left:4px;" title="Citations (mise à jour mensuelle)">📚 ${a.citations} cit.</span>` : ''}
          </div>
          <div class="card-badges">${badges.join('')}</div>
          <div class="score-detail">
            <div class="sd-item"><span class="sd-label" title="Pertinence thématique (0-4)">Th</span><div class="sd-track"><div class="sd-fill" style="width:${sd.theme/4*100}%;background:#3b82f6;"></div></div></div>
            <div class="sd-item"><span class="sd-label" title="Impact Factor (0-3)">IF</span><div class="sd-track"><div class="sd-fill" style="width:${sd.impact/3*100}%;background:#a855f7;"></div></div></div>
            <div class="sd-item"><span class="sd-label" title="Nouveauté (0-2)">Nv</span><div class="sd-track"><div class="sd-fill" style="width:${sd.novelty/2*100}%;background:#22c55e;"></div></div></div>
            <div class="sd-item"><span class="sd-label" title="Applicabilité clinique (0-1)">Cl</span><div class="sd-track"><div class="sd-fill" style="width:${sd.clinical*100}%;background:#f59e0b;"></div></div></div>
          </div>
        </div>
      </div>
      ${a.resume || a.critique ? `
        <div class="card-resume-toggle" onclick="toggleResume('${cardId}', this)">▸ Voir le résumé</div>
        <div class="card-resume" id="${cardId}">
          ${a.resume ? esc(a.resume) : ''}
          ${a.critique ? '<div class="card-critique open" style="max-height:500px;margin-top:8px;">💬 ' + esc(a.critique) + '</div>' : ''}
        </div>
      ` : ''}
      <div class="feedback">
        <button class="fb-btn ${fb === 'utile' ? 'active-utile' : ''}" onclick="setFb('${esc(a.doi)}','utile')">👍 Utile</button>
        <button class="fb-btn ${fb === 'bof' ? 'active-bof' : ''}" onclick="setFb('${esc(a.doi)}','bof')">😐 Bof</button>
        <button class="fb-btn ${fb === 'ignore' ? 'active-ignore' : ''}" onclick="setFb('${esc(a.doi)}','ignore')">👎 Ignoré</button>
        ${a.pmid ? `<a class="fb-btn related-btn" href="https://pubmed.ncbi.nlm.nih.gov/?linkname=pubmed_pubmed&from_uid=${esc(a.pmid)}" target="_blank" title="Articles similaires sur PubMed">🔗 Liés</a>` : ''}
      </div>
    </div>`;
  }).join('');

  // Pagination controls
  const pagDiv = document.getElementById('pagination');
  if (totalPages <= 1) { pagDiv.innerHTML = ''; return; }
  let pagHtml = '<div style="display:flex;justify-content:center;align-items:center;gap:6px;margin-top:16px;flex-wrap:wrap;">';
  // Prev
  pagHtml += `<button class="pag-btn" ${currentPage === 0 ? 'disabled' : ''} onclick="goPage(${currentPage - 1})">◂ Préc.</button>`;
  // Page numbers
  for (let p = 0; p < totalPages; p++) {
    if (totalPages > 10 && Math.abs(p - currentPage) > 2 && p !== 0 && p !== totalPages - 1) {
      if (p === 1 && currentPage > 3) { pagHtml += '<span style="color:#475569;">…</span>'; }
      else if (p === totalPages - 2 && currentPage < totalPages - 4) { pagHtml += '<span style="color:#475569;">…</span>'; }
      continue;
    }
    pagHtml += `<button class="pag-btn ${p === currentPage ? 'pag-active' : ''}" onclick="goPage(${p})">${p + 1}</button>`;
  }
  // Next
  pagHtml += `<button class="pag-btn" ${currentPage >= totalPages - 1 ? 'disabled' : ''} onclick="goPage(${currentPage + 1})">Suiv. ▸</button>`;
  pagHtml += '</div>';
  pagDiv.innerHTML = pagHtml;
}

function goPage(p) {
  currentPage = p;
  renderArticles(false);
  document.getElementById('articlesList').scrollIntoView({behavior:'smooth', block:'start'});
}

function toggleResume(id, toggleEl) {
  const el = document.getElementById(id);
  el.classList.toggle('open');
  toggleEl.textContent = el.classList.contains('open') ? '▾ Masquer le résumé' : '▸ Voir le résumé';
}

function setFb(doi, val) {
  if (feedback[doi] === val) delete feedback[doi];
  else feedback[doi] = val;
  saveFb();
  renderArticles();
}

function exportFeedback() {
  const entries = DATA.map(a => ({
    doi: a.doi, titre: a.titre, categorie: a.categorie,
    journal: a.journal, tags: a.tags, score: a.score, if_val: a.if_val,
    feedback: feedback[a.doi] || 'non noté'
  }));
  const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = `feedback_%%SEMAINE_SAFE%%.json`;
  link.click(); URL.revokeObjectURL(url);
}


function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
function safeId(s) {
  return (s || '').replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 50);
}
function scrollToCard(selector) {
  const c = document.querySelector(selector);
  if (c) { c.scrollIntoView({behavior:'smooth',block:'center'}); c.style.outline='2px solid #60a5fa'; setTimeout(()=>c.style.outline='',2000); }
}
function scrollToId(id) {
  const el = document.getElementById(id);
  if (el) { el.scrollIntoView({behavior:'smooth',block:'center'}); el.style.outline='2px solid #34d399'; setTimeout(()=>el.style.outline='',2000); }
}

// --- Hors champ ---
function renderHorsChamp() {
  if (!HORS_CHAMP || HORS_CHAMP.length === 0) return;
  document.getElementById('hcSection').style.display = 'block';
  // Afficher les 3 hors champ (triés par pertinence décroissante)
  const sorted = [...HORS_CHAMP].sort((a, b) => (b.pertinence || 0) - (a.pertinence || 0)).slice(0, 3);
  document.getElementById('hcList').innerHTML = sorted.map(h => {
    const rawDoi = (h.doi && !h.doi.includes('XXX')) ? h.doi : '';
    const doiUrl = rawDoi
      ? (rawDoi.startsWith('http') ? rawDoi : 'https://doi.org/' + rawDoi)
      : '';
    const hcKey = 'hc_' + (rawDoi || h.titre || '').substring(0, 40);
    const hcSafeKey = safeId(hcKey);
    const fb = feedback[hcKey] || '';
    const pertBadge = h.pertinence ? `<span style="background:#065f46;color:#6ee7b7;padding:1px 6px;border-radius:8px;font-size:0.65rem;font-weight:700;margin-left:6px;">Pertinence ${h.pertinence}/5</span>` : '';
    return `<div class="hc-card" id="hc-${hcSafeKey}">
      <div class="hc-field">${esc(h.domaine || 'Autre discipline')}${pertBadge}</div>
      <div class="hc-title">${doiUrl ? `<a href="${esc(doiUrl)}" target="_blank">${esc(h.titre)}</a>` : esc(h.titre)}</div>
      <div class="hc-meta">
        ${esc(h.auteur || '')} — <span class="journal">${esc(h.journal || '')}</span>
        ${h.if_value ? ' — IF ' + h.if_value : ''}
      </div>
      <div class="hc-bridge">${esc(h.pont_methodologique || h.pont || '')}</div>
      <div class="hc-ref-hm">${h.reference_henri_mondor ? '🏥 ' + esc(h.reference_henri_mondor) : ''}</div>
      <div class="feedback" style="display:flex;gap:6px;justify-content:flex-end;">
        <button class="fb-btn ${fb === 'utile' ? 'active-utile' : ''}" onclick="setFb('${esc(hcKey)}','utile')">👍 Utile</button>
        <button class="fb-btn ${fb === 'bof' ? 'active-bof' : ''}" onclick="setFb('${esc(hcKey)}','bof')">😐 Bof</button>
        <button class="fb-btn ${fb === 'ignore' ? 'active-ignore' : ''}" onclick="setFb('${esc(hcKey)}','ignore')">👎 Ignoré</button>
      </div>
    </div>`;
  }).join('');
}

// --- Directions de recherche ---
function renderDirections() {
  if (!DIRECTIONS || DIRECTIONS.length === 0) return;
  document.getElementById('dirSection').style.display = 'block';
  // Afficher les 3 pistes (max)
  document.getElementById('dirList').innerHTML = DIRECTIONS.slice(0, 3).map((d, i) => {
    const dirKey = 'dir_' + (d.titre || '').substring(0, 40);
    const fb = feedback[dirKey] || '';
    // Build each ref type separately
    const artRefs = d.articles_support || [];
    let artHtml = '';
    if (artRefs.length > 0) {
      const artLinks = artRefs.map(doi => {
        const art = DATA.find(a => a.doi === doi);
        const label = art ? (art.premier_auteur || art.auteur || '').split(' ')[0] + ' et al.' : doi;
        return `<a href="https://doi.org/${esc(doi)}" target="_blank" style="color:#60a5fa;" onclick="event.preventDefault();scrollToCard('[data-doi=&quot;${esc(doi)}&quot;]')">${esc(label)}</a>`;
      }).join(', ');
      artHtml = `📄 Articles : ${artLinks}`;
    }
    const hcRefs = d.hors_champ_refs || [];
    let hcHtml = '';
    if (hcRefs.length > 0) {
      const hcLinks = hcRefs.map(titre => {
        const hc = HORS_CHAMP.find(h => h.titre === titre);
        const shortTitle = titre.length > 60 ? titre.substring(0, 57) + '...' : titre;
        const hcKey2 = safeId('hc_' + ((hc && hc.doi && hc.doi.startsWith('10.') ? hc.doi : titre) || '').substring(0, 40));
        return `<a href="#hc-${hcKey2}" style="color:#34d399;" onclick="event.preventDefault();scrollToId('hc-${hcKey2}')">${esc(shortTitle)}</a>`;
      }).join(', ');
      hcHtml = `💡 Hors champ : ${hcLinks}`;
    }
    const trialRefs = d.trials_refs || [];
    let trialsHtml = '';
    if (trialRefs.length > 0) {
      const trialLinks = trialRefs.map(nct => {
        const trial = CLINICAL_TRIALS.find(t => t.nct_id === nct);
        const label = trial ? (trial.titre || '').split(' – ')[0] : nct;
        return `<a href="https://clinicaltrials.gov/study/${esc(nct)}" target="_blank" style="color:#fbbf24;">${esc(label)}</a>`;
      }).join(', ');
      trialsHtml = `🧪 Essais : ${trialLinks}`;
    }
    const prioColor = d.priorite === 'haute' ? '#ef4444' : d.priorite === 'moyenne' ? '#f59e0b' : '#6b7280';
    return `<div class="dir-card">
      <div class="dir-label">Piste ${i + 1} <span style="color:${prioColor};font-size:0.7rem;margin-left:6px;">● ${esc(d.priorite || '')}</span></div>
      <div class="dir-title">${esc(d.titre)}</div>
      <div class="dir-body">${esc(d.description)}</div>
      <div class="dir-refs">${artHtml}</div>
      <div class="dir-refs">${trialsHtml}</div>
      <div class="dir-refs">${hcHtml}</div>
      <div class="feedback">
        <button class="fb-btn ${fb === 'bonne_piste' ? 'active-utile' : ''}" onclick="setFb('${esc(dirKey)}','bonne_piste')">🎯 Bonne piste</button>
        <button class="fb-btn ${fb === 'deja_explore' ? 'active-bof' : ''}" onclick="setFb('${esc(dirKey)}','deja_explore')">🔄 Déjà exploré</button>
        <button class="fb-btn ${fb === 'pas_faisable' ? 'active-ignore' : ''}" onclick="setFb('${esc(dirKey)}','pas_faisable')">✕ Pas faisable</button>
      </div>
    </div>`;
  }).join('');
}
function alignDirCards() {
  const cards = Array.from(document.querySelectorAll('.dir-card'));
  if (cards.length < 2) return;
  // 1. Reset ALL forced heights so we measure natural sizes
  cards.forEach(c => Array.from(c.children).forEach(ch => {
    ch.style.minHeight = '';
    ch.style.height = '';
  }));
  // 2. Force layout reflow before measuring
  void document.body.offsetHeight;
  // 3. Measure natural height of each child at each index
  const numRows = Math.max(...cards.map(c => c.children.length));
  const maxHeights = [];
  for (let i = 0; i < numRows; i++) {
    let maxH = 0;
    cards.forEach(c => {
      if (c.children[i]) maxH = Math.max(maxH, c.children[i].getBoundingClientRect().height);
    });
    maxHeights.push(maxH);
  }
  // 4. Apply equalized heights
  for (let i = 0; i < numRows; i++) {
    cards.forEach(c => {
      if (c.children[i]) c.children[i].style.minHeight = maxHeights[i] + 'px';
    });
  }
}
window.addEventListener('resize', () => { clearTimeout(window._dirAlign); window._dirAlign = setTimeout(alignDirCards, 200); });

// --- Clinical trials ---
let trialsFilters = new Set(); // multi-select filters
function toggleTrialFilter(f) {
  if (f === 'all') { trialsFilters.clear(); }
  else if (trialsFilters.has(f)) { trialsFilters.delete(f); }
  else { trialsFilters.add(f); }
  renderTrials();
}
function renderTrials() {
  if (!CLINICAL_TRIALS || CLINICAL_TRIALS.length === 0) return;
  document.getElementById('trialsSection').style.display = 'block';
  const tbody = document.getElementById('trialsBody');
  const filtersDiv = document.getElementById('trialsFilters');
  const summaryDiv = document.getElementById('trialsSummary');

  // Compute subtypes for filters
  const subtypes = [...new Set(CLINICAL_TRIALS.map(t => t.sous_type || 'Autre'))].sort();
  const allFilters = ['all', 'ctdna', 'lysa', ...subtypes];
  const filterLabels = {'all': 'Tous', 'ctdna': 'ctDNA/MRD', 'lysa': 'LYSA/LYSARC'};

  filtersDiv.innerHTML = allFilters.map(f => {
    const label = filterLabels[f] || f;
    const isActive = (f === 'all' && trialsFilters.size === 0) || trialsFilters.has(f);
    const cls = isActive ? 'trials-filter-btn active' : 'trials-filter-btn';
    return `<button class="${cls}" onclick="toggleTrialFilter('${esc(f)}')">${esc(label)}</button>`;
  }).join('');

  // Apply ALL active filters (intersection)
  let filtered = CLINICAL_TRIALS;
  if (trialsFilters.size > 0) {
    filtered = filtered.filter(t => {
      let pass = true;
      if (trialsFilters.has('ctdna')) pass = pass && t.has_ctdna;
      if (trialsFilters.has('lysa')) pass = pass && t.centres_fr && t.centres_fr.toLowerCase().includes('lysa');
      // Subtype filters: match any selected subtype
      const selectedSubtypes = [...trialsFilters].filter(f => f !== 'ctdna' && f !== 'lysa');
      if (selectedSubtypes.length > 0) pass = pass && selectedSubtypes.includes(t.sous_type);
      return pass;
    });
  }

  // Summary
  const ctdnaCount = CLINICAL_TRIALS.filter(t => t.has_ctdna).length;
  const lysaCount = CLINICAL_TRIALS.filter(t => t.centres_fr && t.centres_fr.toLowerCase().includes('lysa')).length;
  const activeLabels = trialsFilters.size > 0 ? [...trialsFilters].map(f => filterLabels[f] || f).join(' + ') : 'aucun';
  summaryDiv.innerHTML = `${CLINICAL_TRIALS.length} essais | ${ctdnaCount} ctDNA/MRD | ${lysaCount} LYSA/LYSARC | <b>${filtered.length} affichés</b>${trialsFilters.size > 0 ? ' (filtres: ' + activeLabels + ')' : ''}`;

  tbody.innerHTML = filtered.map(t => {
    const nctUrl = `https://clinicaltrials.gov/study/${t.nct_id}`;
    const ctdnaBadge = t.has_ctdna ? '<span class="ctdna-badge">Oui</span>' : '<span style="color:#475569;">Non</span>';
    const frText = (t.centres_fr || '').toLowerCase();
    const frOui = frText === 'oui' || frText.includes('lysa');
    const frBadge = frOui ? `<span class="fr-badge">Oui</span>` :
      frText.includes('confirmer') ? `<span style="color:#94a3b8;font-size:0.7rem;">À confirmer</span>` :
      `<span style="color:#475569;">Non</span>`;
    const lysaMatch = (t.sponsor || '').toLowerCase().includes('lysa');
    const lysaBadge = lysaMatch ? '<span style="background:#7c3aed;color:#e9d5ff;font-size:0.65rem;padding:2px 6px;border-radius:4px;font-weight:600;">LYSA</span>' : '<span style="color:#475569;">—</span>';
    const resumeHtml = t.resume ? `<div class="trial-resume" style="cursor:pointer;" onclick="this.style.maxHeight=this.style.maxHeight==='none'?'2.8em':'none';this.style.overflow=this.style.maxHeight==='none'?'visible':'hidden';" title="Cliquer pour développer">${esc(t.resume)}</div>` : '';
    const timelineHtml = (t.date_debut && t.date_fin_est) ? (() => {
      const start = new Date(t.date_debut + '-01');
      const end = new Date(t.date_fin_est + '-01');
      const now = new Date();
      const total = end - start;
      if (total <= 0) return '';
      const elapsed = Math.max(0, Math.min(1, (now - start) / total));
      const pct = Math.round(elapsed * 100);
      const color = pct >= 90 ? '#ef4444' : pct >= 50 ? '#f59e0b' : '#22c55e';
      return `<div style="margin-top:4px;background:#1e293b;border-radius:3px;height:4px;width:100%;max-width:200px;"><div style="width:${pct}%;background:${color};height:4px;border-radius:3px;"></div></div>`;
    })() : '';
    // Extract study nickname (before " – " or " — " in title)
    let nickname = t.nom_etude || '';
    if (!nickname && t.titre) {
      const m = t.titre.match(/^([A-Z][A-Za-z0-9\-\/\.]+(?:[\- ][A-Z0-9\-\/\.]+)*?)(?:\s*[\–\—\-]\s| :)/);
      if (m && !/^(Phase|Study|Trial|Essai|A |An |The |Étude)/i.test(m[1])) nickname = m[1];
    }
    if (!nickname) nickname = '—';
    // Dates
    const dateInfo = (t.date_debut || '') + (t.date_fin_est ? ' → ' + t.date_fin_est : '');
    // Remarques
    const remarques = t.remarques || '';
    return `<tr>
      <td><a href="${nctUrl}" target="_blank" style="color:#60a5fa;">${esc(t.nct_id)}</a></td>
      <td style="font-weight:700;color:#fbbf24;white-space:nowrap;">${esc(nickname)}</td>
      <td>${esc(t.phase || '—')}</td>
      <td>${esc(t.sous_type || '—')}</td>
      <td class="trial-title">${esc(t.titre || '—')}${resumeHtml}${timelineHtml}${remarques ? '<div style="color:#f59e0b;font-size:0.7rem;margin-top:2px;">⚠ ' + esc(remarques) + '</div>' : ''}</td>
      <td>${esc(t.sponsor || '—')}</td>
      <td>${esc(t.n_patients || '—')}</td>
      <td style="font-size:0.7rem;color:#94a3b8;white-space:nowrap;">${esc(dateInfo)}</td>
      <td>${frBadge}</td>
      <td>${lysaBadge}</td>
      <td>${ctdnaBadge}</td>
    </tr>`;
  }).join('');
}

// --- Conferences ---
function renderConferences() {
  if (!CONFERENCES || CONFERENCES.length === 0) return;
  document.getElementById('confSection').style.display = 'block';
  const now = new Date();
  const list = document.getElementById('confList');

  // Sort by date_debut
  const sorted = [...CONFERENCES].sort((a,b) => a.date_debut.localeCompare(b.date_debut));

  // Only show upcoming or recently past (< 30 days ago)
  const recent = sorted.filter(c => {
    const end = new Date(c.date_fin || c.date_debut);
    return (end - now) > -30 * 86400000;
  });

  list.innerHTML = recent.map(c => {
    const deadlineDate = c.deadline_abstract ? new Date(c.deadline_abstract) : null;
    const startDate = new Date(c.date_debut);
    let deadlineClass = 'conf-deadline-ok';
    let deadlineText = '';
    if (deadlineDate) {
      const diff = (deadlineDate - now) / 86400000;
      if (diff < 0) { deadlineClass = 'conf-deadline-past'; deadlineText = 'Deadline passée'; }
      else if (diff < 30) { deadlineClass = 'conf-deadline-soon'; deadlineText = `Deadline dans ${Math.ceil(diff)}j`; }
      else { deadlineText = `Deadline: ${c.deadline_abstract}`; }
    } else {
      deadlineClass = 'conf-deadline-unknown';
      deadlineText = 'Deadline non connue';
    }
    const dateStr = c.date_debut ? `${c.date_debut.slice(5)} → ${(c.date_fin||'').slice(5)}` : '';
    return `<div class="conf-card">
      <div class="conf-info">
        <div class="conf-name"><a href="${esc(c.url||'#')}" target="_blank">${esc(c.nom)}</a></div>
        <div class="conf-detail">${esc(c.lieu||'')} — ${dateStr}</div>
      </div>
      <span class="conf-deadline ${deadlineClass}">${deadlineText}</span>
    </div>`;
  }).join('');
}

// --- Conference deadline alert banner ---
function renderDeadlineAlert() {
  if (!CONFERENCES || CONFERENCES.length === 0) return;
  const now = new Date();
  const upcoming = CONFERENCES.filter(c => {
    if (!c.deadline_abstract) return false;
    const deadline = new Date(c.deadline_abstract);
    const daysUntil = (deadline - now) / 86400000;
    return daysUntil > 0 && daysUntil <= 14;
  });
  if (upcoming.length === 0) {
    document.getElementById('deadlineBanner').style.display = 'none';
    return;
  }
  const c = upcoming[0];
  const deadline = new Date(c.deadline_abstract);
  const daysUntil = Math.ceil((deadline - now) / 86400000);
  const dateStr = c.deadline_abstract.slice(5);
  const banner = document.getElementById('deadlineBanner');
  banner.innerHTML = `⏰ Deadline abstract ${esc(c.nom)} dans ${daysUntil} jour${daysUntil>1?'s':''} (${dateStr})`;
  banner.style.display = 'block';
}

// --- Estimate score decomposition from available data ---
function estimateScoreDetail(a) {
  // Theme (0-4): based on category relevance
  const themeMap = {
    'ctDNA — Lymphomes': 4, 'Immuno + ctDNA/Lymphome': 4,
    'ctDNA — Méthodo': 3, 'Lymphomes': 3,
    'IA + Hémato': 2, 'Hémato générale': 2, 'Preprint': 2,
  };
  const theme = themeMap[a.categorie] || 2;

  // Impact (0-3): from IF value
  let impact = 0;
  if (a.if_val >= 50) impact = 3;
  else if (a.if_val >= 20) impact = 2.5;
  else if (a.if_val >= 10) impact = 2;
  else if (a.if_val >= 5) impact = 1;

  // Distribute remaining score across novelty (0-2) and clinical (0-1)
  const remaining = Math.max(0, a.score - theme - Math.round(impact));
  const novelty = Math.min(2, remaining);
  const clinical = Math.min(1, Math.max(0, remaining - novelty));

  return { theme, impact, novelty, clinical };
}

// Init
populateFilters();
document.getElementById('filterCat').addEventListener('change', renderArticles);
document.getElementById('filterSem').addEventListener('change', renderArticles);
document.getElementById('sortBy').addEventListener('change', renderArticles);
document.getElementById('searchBox').addEventListener('input', renderArticles);
document.getElementById('filterFb').addEventListener('change', renderArticles);
document.getElementById('filterCat').addEventListener('change', () => {
  // Re-render concept selection when category filter changes
  const currentCat = document.getElementById('filterCat').value;
  const concepts = [
    {keys:['phased','phasedseq','phased-seq','variants phasés'],
     titre:'Les variants phasés (PhasED-Seq)',
     texte:"Les variants phasés sont des mutations co-localisées sur le même fragment d'ADN (même molécule). La technologie PhasED-Seq (Phased Variant Enrichment and Detection Sequencing), développée par l'équipe de Ash Alizadeh à Stanford, exploite ces co-occurrences pour atteindre une sensibilité de détection du ctDNA de l'ordre de 1 molécule mutante sur 1 million — soit 100 à 1000× plus sensible que le séquençage classique. Cette approche est particulièrement puissante pour la MRD dans les lymphomes, où la charge tumorale résiduelle peut être extrêmement faible après traitement."},
    {keys:['fragmentom','cfDNA fragment','fragment size','nucleosome','fragmentomic'],
     titre:'La fragmentomique du cfDNA',
     texte:"La fragmentomique analyse les profils de fragmentation de l'ADN circulant libre (cfDNA) : taille des fragments, motifs de clivage, couverture selon la position des nucléosomes. Contrairement au génotypage qui cherche des mutations spécifiques, la fragmentomique exploite l'empreinte épigénétique du tissu d'origine. Un fragment de ~167 pb correspond à un mono-nucléosome, tandis que des fragments plus courts (~120-140 pb) sont enrichis dans le ctDNA tumoral. Cette différence de profil permet de détecter et quantifier la tumeur sans connaître a priori ses mutations — un avantage majeur pour les cancers sans driver connu."},
    {keys:['glofitamab','columvi'],
     titre:'Le glofitamab (Columvi®)',
     texte:"Le glofitamab est un anticorps bispecifique anti-CD20×CD3 avec une architecture 2:1 unique : il possède deux sites de liaison au CD20 (cellule tumorale) pour un seul site anti-CD3 (lymphocyte T). Cette bivalence pour le CD20 lui confère une affinité supérieure pour les cellules B tumorales. Approuvé pour le DLBCL en rechute/réfractaire (≥2 lignes), il s'administre en durée fixe (8-12 cycles), contrairement aux CAR-T qui nécessitent un traitement unique mais une fabrication personnalisée. Le risque principal est le syndrome de relargage cytokinique (CRS), atténué par un pré-traitement d'obinutuzumab."},
    {keys:['epcoritamab','epkinly','subcutaneous bispecific'],
     titre:'L\'epcoritamab (Epkinly®)',
     texte:"L'epcoritamab est un anticorps bispecifique anti-CD20×CD3 administré par voie sous-cutanée — une différence majeure par rapport au glofitamab (IV). Sa formulation SC simplifie l'administration et permet un traitement ambulatoire. Le schéma posologique comporte des doses croissantes (step-up dosing) pour minimiser le CRS. Dans l'essai EPCORE NHL-1, le taux de réponse complète atteint ~40% dans le DLBCL R/R, avec des réponses durables. L'administration SC ouvre la voie à des combinaisons en ambulatoire, un avantage logistique considérable par rapport aux CAR-T."},
    {keys:['car-t','car t','chimeric antigen','axicabtagene','tisagenlecleucel','lisocabtagene','brexu','axi-cel','tisa-cel','liso-cel'],
     titre:'Les CAR-T cells en lymphome B',
     texte:"Les cellules CAR-T (Chimeric Antigen Receptor T-cells) sont des lymphocytes T du patient modifiés génétiquement pour exprimer un récepteur artificiel ciblant le CD19 tumoral. Trois produits sont approuvés dans le DLBCL : axicabtagene ciloleucel (Yescarta®, ciblant CD19 via domaine scFv + costimulation CD28), tisagenlecleucel (Kymriah®, costimulation 4-1BB), et lisocabtagene maraleucel (Breyanzi®, costimulation 4-1BB, rapport CD4:CD8 défini). Depuis 2022, ZUMA-7 et TRANSFORM ont démontré la supériorité des CAR-T vs autogreffe en 2e ligne, changeant le standard de traitement."},
    {keys:['mrd','minimal residual','maladie résiduelle'],
     titre:'La MRD (Maladie Résiduelle Mesurable)',
     texte:"La MRD désigne la persistance de cellules tumorales indétectables par l'imagerie conventionnelle (TEP-TDM) mais identifiables par des techniques moléculaires ultrasensibles. Dans les lymphomes, la MRD par ctDNA surpasse la TEP en valeur pronostique : un patient MRD+ en fin de traitement a un risque de rechute 10-30× supérieur à un patient MRD-. Le terme « mesurable » a remplacé « minimale » pour souligner qu'on quantifie réellement la maladie résiduelle, pas seulement sa présence/absence. La MRD pourrait à terme guider la désescalade ou l'intensification thérapeutique."},
    {keys:['capp-seq','capp seq','hybrid capture'],
     titre:'CAPP-Seq (Cancer Personalized Profiling by deep Sequencing)',
     texte:"CAPP-Seq est une méthode de capture hybride ciblée développée par Maximilian Diehn et Ash Alizadeh (Stanford, Nature Medicine 2014). Elle capture simultanément des centaines de régions génomiques récurrentes dans un type tumoral donné, permettant de détecter le ctDNA sans nécessiter de biopsie tissulaire préalable. Dans les lymphomes, un panel CAPP-Seq typique cible les régions VDJ réarrangées et les mutations récurrentes (EZH2, MYD88, CREBBP, etc.). Sa sensibilité atteint ~1 molécule mutante sur 10 000, suffisante pour le suivi post-traitement mais inférieure à PhasED-Seq pour la MRD profonde."},
    {keys:['polarix','pola-r-chp','polatuzumab'],
     titre:'L\'essai POLARIX et le polatuzumab vedotin',
     texte:"POLARIX est un essai randomisé de phase 3 (Tilly et al., NEJM 2022) comparant pola-R-CHP vs R-CHOP en 1re ligne du DLBCL. Le polatuzumab vedotin est un anticorps-médicament conjugué (ADC) anti-CD79b couplé à la MMAE (antimitotique). POLARIX a montré une amélioration significative de la PFS à 2 ans (76,7% vs 70,2%), faisant du pola-R-CHP le nouveau standard. C'est le premier changement de 1re ligne du DLBCL depuis l'introduction du rituximab en 2002 — une avancée majeure après 20 ans de R-CHOP."},
    {keys:['chapuy','schmitz','classification moléculaire','genetic subtypes','cluster','lmb-'],
     titre:'La classification moléculaire du DLBCL',
     texte:"En 2018, deux études parallèles (Chapuy, Nature Medicine ; Schmitz, NEJM) ont identifié des sous-types génétiques du DLBCL au-delà de la dichotomie classique GCB/ABC. Chapuy a décrit 5 clusters (C1-C5) basés sur les altérations génétiques récurrentes, tandis que Schmitz a défini 4 sous-types (MCD, BN2, N1, EZB). Ces classifications expliquent l'hétérogénéité des réponses au R-CHOP et ouvrent la voie à des thérapies ciblées par sous-type. Wright (Cancer Cell 2020) a ensuite développé LymphGen, un classifieur probabiliste applicable en routine clinique."},
    {keys:['swgs','shallow','whole genome','low-pass','ichorCNA','genome-wide'],
     titre:'Le sWGS (shallow Whole-Genome Sequencing)',
     texte:"Le sWGS est un séquençage génomique à faible profondeur (~0.1-1×) du cfDNA plasmatique. Plutôt que de cibler des mutations spécifiques, il détecte des anomalies du nombre de copies (CNA) à l'échelle du génome entier — gains, pertes, amplifications. Avec des outils comme ichorCNA, on peut estimer la fraction tumorale dans le plasma à partir du profil de CNA. C'est une approche agnostique (pas besoin de connaître les mutations de la tumeur), peu coûteuse (~50-100€/échantillon), et qui donne un aperçu global de l'instabilité génomique. Particulièrement utile en screening ou quand la biopsie tissulaire n'est pas disponible."},
    {keys:['bispecif','t-cell engager','bite','cd3','cd20xcd3','cd19xcd3'],
     titre:'Les anticorps bispecifiques en hémato-oncologie',
     texte:"Les anticorps bispecifiques sont des protéines recombinantes capables de lier simultanément deux cibles : typiquement un antigène tumoral (CD20 ou CD19) et le CD3 des lymphocytes T. En rapprochant physiquement les cellules T du patient et les cellules tumorales, ils induisent une lyse ciblée sans nécessiter de modification génétique des lymphocytes T (contrairement aux CAR-T). Avantages : produit « off-the-shelf » (pas de fabrication personnalisée), administration immédiate, coût potentiellement inférieur. Inconvénients : traitement continu (vs one-shot pour les CAR-T), CRS fréquent, toxicité neurologique (ICANS). Trois sont approuvés dans les lymphomes : mosunetuzumab, glofitamab, epcoritamab."},
    {keys:['dpcr','digital pcr','ddpcr','droplet'],
     titre:'La PCR digitale (dPCR / ddPCR)',
     texte:"La PCR digitale partitionne l'échantillon en milliers de gouttelettes (ddPCR = droplet digital PCR) contenant chacune 0 ou 1 molécule cible. En comptant les gouttelettes positives vs négatives (loi de Poisson), on obtient une quantification absolue sans courbe standard. Sensibilité : ~0,01-0,1% de fraction allélique mutante. Dans les lymphomes, la ddPCR est utilisée pour le suivi de mutations spécifiques (ex: MYD88 L265P dans le Waldenström, EZH2 Y641 dans le folliculaire) et la quantification du ctDNA. Moins multiplexée que le NGS (1-4 cibles) mais plus rapide, moins chère, et facilement standardisable — idéale pour le suivi longitudinal d'un marqueur connu."},
    {keys:['checkpoint','pd-1','pd-l1','nivolumab','pembrolizumab','immune checkpoint'],
     titre:'Les inhibiteurs de checkpoints en lymphome',
     texte:"Les inhibiteurs de checkpoints immunitaires bloquent les récepteurs inhibiteurs (PD-1, CTLA-4) qui freinent la réponse anti-tumorale des lymphocytes T. Dans le lymphome de Hodgkin, l'amplification 9p24.1 (contenant PD-L1/PD-L2) fait de cette maladie un candidat idéal : le nivolumab (anti-PD-1) obtient des taux de réponse de ~65-70% en rechute post-brentuximab. En revanche, dans les lymphomes B agressifs (DLBCL), les checkpoints seuls sont peu efficaces — le microenvironnement immunosuppresseur est différent. Des combinaisons (checkpoint + bispecifique, checkpoint + CAR-T) sont en cours d'évaluation."},
    {keys:['lymphome t','t-cell lymphoma','aitl','alcl','ptcl','angioimmunoblast'],
     titre:'La mutation RHOA G17V dans les lymphomes T angioimmunoblastiques (AITL)',
     texte:"La mutation RHOA G17V est présente dans ~70% des lymphomes T angioimmunoblastiques (AITL) et constitue un marqueur diagnostique quasi-pathognomonique. RHOA est une GTPase qui régule le cytosquelette et la signalisation T-cell receptor (TCR). La mutation G17V est « dominant-négative » : elle bloque la signalisation normale et active la voie PI3K/AKT, favorisant la prolifération des cellules T folliculaires helper (TFH). En pratique, cette mutation est détectable dans le sang par dPCR et pourrait servir de biomarqueur ctDNA pour le suivi des AITL — un domaine encore peu exploré mais prometteur. Combinée aux mutations TET2 (présentes dans l'hématopoïèse clonale pré-tumorale) et IDH2, elle définit un profil génétique unique qui ouvre la voie à des thérapies ciblées épigénétiques."},
    {keys:['hodgkin','reed-sternberg','brentuximab','hl classique'],
     titre:'Le lymphome de Hodgkin classique',
     texte:"Le lymphome de Hodgkin classique (cHL) est caractérisé par les cellules de Reed-Sternberg (< 1% de la masse tumorale) dans un microenvironnement inflammatoire riche. Quatre sous-types : scléro-nodulaire (70%), cellularité mixte, riche en lymphocytes, déplétion lymphocytaire. Le traitement standard (ABVD ± radiothérapie) guérit ~80% des patients. Avancées majeures : brentuximab vedotin + AVD (ECHELON-1, remplaçant le BEACOPP), nivolumab/pembrolizumab en rechute, et TEP-TDM intérimaire pour la désescalade. Le ctDNA dans le cHL est un défi car les cellules RS sont rares — des approches par capture de réarrangements Ig et par fragmentomique sont en développement."},
    {keys:['who 2022','icc 2022','classification','5th edition'],
     titre:'Les nouvelles classifications WHO 2022 / ICC 2022',
     texte:"En 2022, deux classifications concurrentes des néoplasies hématopoïétiques ont été publiées simultanément : la WHO 5e édition et la ICC (International Consensus Classification). Les deux introduisent des sous-types moléculaires pour le DLBCL (GCB vs ABC intégrés formellement), reconnaissent le « lymphome B de haut grade avec réarrangements MYC et BCL2 » (anciennement « double-hit »), et affinent les catégories de lymphomes T. La coexistence de deux classifications crée une confusion mais reflète la transition vers une nosologie moléculaire. En pratique, les différences sont mineures et convergent vers l'intégration de la génomique dans le diagnostic."},
    {keys:['machine learning','deep learning','ia ','intelligence artificielle','neural network','random forest','transformer'],
     titre:'L\'IA en hématologie',
     texte:"L'intelligence artificielle en hémato-oncologie couvre plusieurs axes : (1) histopathologie digitale — des CNN (réseaux convolutifs) classent les sous-types de lymphome à partir de lames HES avec des performances proches de l'expert ; (2) prédiction pronostique — des modèles intégrant données cliniques, biologiques et génomiques (random forests, XGBoost) surpassent les scores classiques (IPI) ; (3) analyse du cfDNA — le ML détecte des signatures fragmentomiques ou mutationnelles discriminantes ; (4) NLP — l'extraction automatisée de données à partir des comptes rendus et de la littérature. La validation clinique reste le maillon faible : peu de modèles ont été testés en prospectif."},
    {keys:['venetoclax','bcl-2','bcl2','abl-'],
     titre:'Le venetoclax (anti-BCL2)',
     texte:"Le venetoclax est un inhibiteur sélectif de BCL-2, protéine anti-apoptotique surexprimée dans de nombreuses hémopathies. Approuvé dans la LLC (en combinaison avec obinutuzumab ou rituximab) et la LAM (avec azacitidine), il a transformé le pronostic de ces maladies. Dans les lymphomes, BCL2 est transloqué dans ~85% des lymphomes folliculaires (t(14;18)) et ~30% des DLBCL-GCB. Des essais en cours évaluent le venetoclax dans les lymphomes en rechute, souvent en combinaison avec R-CHOP ou des bispecifiques. Le suivi du ctDNA pourrait identifier précocement les patients répondeurs au venetoclax."},
    {keys:['lysarc','lysa','french lymphoma','groupe d\'étude'],
     titre:'Le LYSARC et le réseau lymphome français',
     texte:"Le LYSARC (Lymphoma Academic Research Organisation) est le groupe coopérateur français dédié aux lymphomes, issu du GELA (Groupe d'Étude des Lymphomes de l'Adulte). Basé à Lyon (Centre Léon Bérard), il coordonne des essais multicentriques nationaux et internationaux. Le réseau français a contribué à des essais majeurs : POLARIX (Tilly), REMARC, GAINED, et des études translationelles sur le ctDNA. Pour un chercheur à Henri Mondor, le LYSARC est le principal vecteur d'accès aux essais lymphome et aux cohortes biologiques associées."},
    {keys:['nanopore','oxford nanopore','long read','minion','ont'],
     titre:'Le séquençage Nanopore pour le ctDNA',
     texte:"La technologie Oxford Nanopore (ONT) séquence des molécules d'ADN individuelles en temps réel en les faisant passer à travers un nanopore protéique. Contrairement au NGS classique (lectures courtes de 150-300 pb), le Nanopore produit des lectures longues (>10 kb) et détecte directement les modifications épigénétiques (méthylation 5mC) sans bisulfite. Pour le ctDNA, les applications émergentes incluent : profil de méthylation du cfDNA pour identifier le tissu d'origine, détection de variants structuraux, et séquençage rapide point-of-care (MinION). La sensibilité reste inférieure au NGS ciblé pour les faibles fractions tumorales, mais progresse rapidement."}
  ];
  let corpus = '';
  if (currentCat) {
    const filteredByCategory = DATA.filter(a => a.categorie === currentCat);
    corpus = filteredByCategory.map(a => [a.titre, a.tags, a.resume, a.categorie, a.critique || ''].join(' ').toLowerCase()).join(' ');
  } else {
    corpus = DATA.map(a => [a.titre, a.tags, a.resume, a.categorie, a.critique || ''].join(' ').toLowerCase()).join(' ');
  }
  const matched = concepts.filter(c => c.keys.some(k => corpus.includes(k.toLowerCase())));
  const pool = matched.length > 0 ? matched : concepts;
  const now = new Date();
  const jan4 = new Date(now.getFullYear(), 0, 4);
  const weekNum = Math.ceil(((now - jan4) / 86400000 + jan4.getDay() + 1) / 7);
  const c = pool[weekNum % pool.length];
  const container = document.getElementById('didYouKnow');
  if (container) {
    const matchCount = matched.length;
    container.innerHTML = `<div style="display:flex;align-items:flex-start;gap:14px;">
      <span style="font-size:2.2rem;">🎓</span>
      <div>
        <div style="font-weight:700;font-size:1.05rem;color:#e2e8f0;margin-bottom:8px;">${c.titre}</div>
        <div style="font-size:0.85rem;color:#cbd5e1;line-height:1.7;">${c.texte}</div>
        <div style="font-size:0.7rem;color:#475569;margin-top:10px;font-style:italic;">Concept lié à ${matchCount} article${matchCount>1?'s':''} de votre veille${currentCat?' — filtre: '+currentCat:''} · Change chaque semaine</div>
      </div>
    </div>`;
  }
});

// --- Top auteurs (replaces old key author alert) ---
(function renderTopAuthors() {
  // Count publications per author (premier + senior), aggregate stats
  const authorStats = {};
  DATA.forEach(a => {
    [a.auteur, a.senior].filter(Boolean).forEach(name => {
      if (!authorStats[name]) authorStats[name] = { count: 0, scoreSum: 0, ifMax: 0, journals: new Set(), articles: [] };
      const s = authorStats[name];
      s.count++;
      s.scoreSum += a.score;
      if (a.if_val > s.ifMax) s.ifMax = a.if_val;
      s.journals.add(a.journal);
      s.articles.push(a);
    });
  });

  const sorted = Object.entries(authorStats)
    .sort((a,b) => b[1].count - a[1].count || b[1].scoreSum - a[1].scoreSum)
    .slice(0, 3);

  if (sorted.length === 0) return;
  const el = document.getElementById('kaAlert');
  el.style.display = 'block';

  el.innerHTML = `<div class="ka-alert">
    <div class="ka-alert-title">Top 3 auteurs de la base</div>
    ${sorted.map(([name, s], i) => {
      const medal = ['🥇','🥈','🥉'][i] || '';
      const avgScore = (s.scoreSum / s.count).toFixed(1);
      const ka = KEY_AUTHORS.some(k => name.toLowerCase().includes(k.toLowerCase()));
      return `<div class="ka-alert-item" style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #1e293b;cursor:pointer;transition:background 0.15s;border-radius:4px;padding:6px 8px;" onclick="document.getElementById('searchBox').value='${esc(name)}';renderArticles();this.style.background='#172554';" onmouseenter="this.style.background='#1e293b'" onmouseleave="this.style.background='transparent'" title="Cliquer pour filtrer les articles de ${esc(name)}">
        <span style="font-size:1.1rem;">${medal}</span>
        <span style="min-width:80px;"><b>${esc(name)}</b></span>
        <span style="font-size:0.72rem;color:#94a3b8;">${s.count} pub${s.count>1?'s':''} · Score moy. ${avgScore} · IF max ${s.ifMax.toFixed(1)} · ${s.journals.size} journal${s.journals.size>1?'x':''}</span>
        <span style="font-size:0.72rem;margin-left:auto;">${[...new Set(s.articles.map(a => a.journal))].map(j => {
          const art = s.articles.find(a => a.journal === j);
          return `<a href="${esc(art.doi_url)}" target="_blank" style="color:#93c5fd;text-decoration:none;margin-left:6px;" title="${esc(j)}" onclick="event.stopPropagation();">${esc(j)}</a>`;
        }).join('')}</span>
      </div>`;
    }).join('')}
  </div>`;
})();

renderKPI();
renderTop3();
renderCatChart();
renderGeoMap();
renderJournals();
renderTagCloud();
renderTrends();
renderDeadlineAlert();
renderConferences();
renderTrials();
renderHorsChamp();
renderDirections();
renderArticles();

// Align pistes cards AFTER all renders + double rAF to ensure full layout
requestAnimationFrame(() => { requestAnimationFrame(alignDirCards); });
// Also re-align after fonts are fully loaded
if (document.fonts) document.fonts.ready.then(alignDirCards);

// --- Le saviez-vous ? ---
(function renderDidYouKnow() {
  const concepts = [
    {keys:['phased','phasedseq','phased-seq','variants phasés'],
     titre:'Les variants phasés (PhasED-Seq)',
     texte:"Les variants phasés sont des mutations co-localisées sur le même fragment d'ADN (même molécule). La technologie PhasED-Seq (Phased Variant Enrichment and Detection Sequencing), développée par l'équipe de Ash Alizadeh à Stanford, exploite ces co-occurrences pour atteindre une sensibilité de détection du ctDNA de l'ordre de 1 molécule mutante sur 1 million — soit 100 à 1000× plus sensible que le séquençage classique. Cette approche est particulièrement puissante pour la MRD dans les lymphomes, où la charge tumorale résiduelle peut être extrêmement faible après traitement."},
    {keys:['fragmentom','cfDNA fragment','fragment size','nucleosome','fragmentomic'],
     titre:'La fragmentomique du cfDNA',
     texte:"La fragmentomique analyse les profils de fragmentation de l'ADN circulant libre (cfDNA) : taille des fragments, motifs de clivage, couverture selon la position des nucléosomes. Contrairement au génotypage qui cherche des mutations spécifiques, la fragmentomique exploite l'empreinte épigénétique du tissu d'origine. Un fragment de ~167 pb correspond à un mono-nucléosome, tandis que des fragments plus courts (~120-140 pb) sont enrichis dans le ctDNA tumoral. Cette différence de profil permet de détecter et quantifier la tumeur sans connaître a priori ses mutations — un avantage majeur pour les cancers sans driver connu."},
    {keys:['glofitamab','columvi'],
     titre:'Le glofitamab (Columvi®)',
     texte:"Le glofitamab est un anticorps bispecifique anti-CD20×CD3 avec une architecture 2:1 unique : il possède deux sites de liaison au CD20 (cellule tumorale) pour un seul site anti-CD3 (lymphocyte T). Cette bivalence pour le CD20 lui confère une affinité supérieure pour les cellules B tumorales. Approuvé pour le DLBCL en rechute/réfractaire (≥2 lignes), il s'administre en durée fixe (8-12 cycles), contrairement aux CAR-T qui nécessitent un traitement unique mais une fabrication personnalisée. Le risque principal est le syndrome de relargage cytokinique (CRS), atténué par un pré-traitement d'obinutuzumab."},
    {keys:['epcoritamab','epkinly','subcutaneous bispecific'],
     titre:'L\'epcoritamab (Epkinly®)',
     texte:"L'epcoritamab est un anticorps bispecifique anti-CD20×CD3 administré par voie sous-cutanée — une différence majeure par rapport au glofitamab (IV). Sa formulation SC simplifie l'administration et permet un traitement ambulatoire. Le schéma posologique comporte des doses croissantes (step-up dosing) pour minimiser le CRS. Dans l'essai EPCORE NHL-1, le taux de réponse complète atteint ~40% dans le DLBCL R/R, avec des réponses durables. L'administration SC ouvre la voie à des combinaisons en ambulatoire, un avantage logistique considérable par rapport aux CAR-T."},
    {keys:['car-t','car t','chimeric antigen','axicabtagene','tisagenlecleucel','lisocabtagene','brexu','axi-cel','tisa-cel','liso-cel'],
     titre:'Les CAR-T cells en lymphome B',
     texte:"Les cellules CAR-T (Chimeric Antigen Receptor T-cells) sont des lymphocytes T du patient modifiés génétiquement pour exprimer un récepteur artificiel ciblant le CD19 tumoral. Trois produits sont approuvés dans le DLBCL : axicabtagene ciloleucel (Yescarta®, ciblant CD19 via domaine scFv + costimulation CD28), tisagenlecleucel (Kymriah®, costimulation 4-1BB), et lisocabtagene maraleucel (Breyanzi®, costimulation 4-1BB, rapport CD4:CD8 défini). Depuis 2022, ZUMA-7 et TRANSFORM ont démontré la supériorité des CAR-T vs autogreffe en 2e ligne, changeant le standard de traitement."},
    {keys:['mrd','minimal residual','maladie résiduelle'],
     titre:'La MRD (Maladie Résiduelle Mesurable)',
     texte:"La MRD désigne la persistance de cellules tumorales indétectables par l'imagerie conventionnelle (TEP-TDM) mais identifiables par des techniques moléculaires ultrasensibles. Dans les lymphomes, la MRD par ctDNA surpasse la TEP en valeur pronostique : un patient MRD+ en fin de traitement a un risque de rechute 10-30× supérieur à un patient MRD-. Le terme « mesurable » a remplacé « minimale » pour souligner qu'on quantifie réellement la maladie résiduelle, pas seulement sa présence/absence. La MRD pourrait à terme guider la désescalade ou l'intensification thérapeutique."},
    {keys:['capp-seq','capp seq','hybrid capture'],
     titre:'CAPP-Seq (Cancer Personalized Profiling by deep Sequencing)',
     texte:"CAPP-Seq est une méthode de capture hybride ciblée développée par Maximilian Diehn et Ash Alizadeh (Stanford, Nature Medicine 2014). Elle capture simultanément des centaines de régions génomiques récurrentes dans un type tumoral donné, permettant de détecter le ctDNA sans nécessiter de biopsie tissulaire préalable. Dans les lymphomes, un panel CAPP-Seq typique cible les régions VDJ réarrangées et les mutations récurrentes (EZH2, MYD88, CREBBP, etc.). Sa sensibilité atteint ~1 molécule mutante sur 10 000, suffisante pour le suivi post-traitement mais inférieure à PhasED-Seq pour la MRD profonde."},
    {keys:['polarix','pola-r-chp','polatuzumab'],
     titre:'L\'essai POLARIX et le polatuzumab vedotin',
     texte:"POLARIX est un essai randomisé de phase 3 (Tilly et al., NEJM 2022) comparant pola-R-CHP vs R-CHOP en 1re ligne du DLBCL. Le polatuzumab vedotin est un anticorps-médicament conjugué (ADC) anti-CD79b couplé à la MMAE (antimitotique). POLARIX a montré une amélioration significative de la PFS à 2 ans (76,7% vs 70,2%), faisant du pola-R-CHP le nouveau standard. C'est le premier changement de 1re ligne du DLBCL depuis l'introduction du rituximab en 2002 — une avancée majeure après 20 ans de R-CHOP."},
    {keys:['chapuy','schmitz','classification moléculaire','genetic subtypes','cluster','lmb-'],
     titre:'La classification moléculaire du DLBCL',
     texte:"En 2018, deux études parallèles (Chapuy, Nature Medicine ; Schmitz, NEJM) ont identifié des sous-types génétiques du DLBCL au-delà de la dichotomie classique GCB/ABC. Chapuy a décrit 5 clusters (C1-C5) basés sur les altérations génétiques récurrentes, tandis que Schmitz a défini 4 sous-types (MCD, BN2, N1, EZB). Ces classifications expliquent l'hétérogénéité des réponses au R-CHOP et ouvrent la voie à des thérapies ciblées par sous-type. Wright (Cancer Cell 2020) a ensuite développé LymphGen, un classifieur probabiliste applicable en routine clinique."},
    {keys:['swgs','shallow','whole genome','low-pass','ichorCNA','genome-wide'],
     titre:'Le sWGS (shallow Whole-Genome Sequencing)',
     texte:"Le sWGS est un séquençage génomique à faible profondeur (~0.1-1×) du cfDNA plasmatique. Plutôt que de cibler des mutations spécifiques, il détecte des anomalies du nombre de copies (CNA) à l'échelle du génome entier — gains, pertes, amplifications. Avec des outils comme ichorCNA, on peut estimer la fraction tumorale dans le plasma à partir du profil de CNA. C'est une approche agnostique (pas besoin de connaître les mutations de la tumeur), peu coûteuse (~50-100€/échantillon), et qui donne un aperçu global de l'instabilité génomique. Particulièrement utile en screening ou quand la biopsie tissulaire n'est pas disponible."},
    {keys:['bispecif','t-cell engager','bite','cd3','cd20xcd3','cd19xcd3'],
     titre:'Les anticorps bispecifiques en hémato-oncologie',
     texte:"Les anticorps bispecifiques sont des protéines recombinantes capables de lier simultanément deux cibles : typiquement un antigène tumoral (CD20 ou CD19) et le CD3 des lymphocytes T. En rapprochant physiquement les cellules T du patient et les cellules tumorales, ils induisent une lyse ciblée sans nécessiter de modification génétique des lymphocytes T (contrairement aux CAR-T). Avantages : produit « off-the-shelf » (pas de fabrication personnalisée), administration immédiate, coût potentiellement inférieur. Inconvénients : traitement continu (vs one-shot pour les CAR-T), CRS fréquent, toxicité neurologique (ICANS). Trois sont approuvés dans les lymphomes : mosunetuzumab, glofitamab, epcoritamab."},
    {keys:['dpcr','digital pcr','ddpcr','droplet'],
     titre:'La PCR digitale (dPCR / ddPCR)',
     texte:"La PCR digitale partitionne l'échantillon en milliers de gouttelettes (ddPCR = droplet digital PCR) contenant chacune 0 ou 1 molécule cible. En comptant les gouttelettes positives vs négatives (loi de Poisson), on obtient une quantification absolue sans courbe standard. Sensibilité : ~0,01-0,1% de fraction allélique mutante. Dans les lymphomes, la ddPCR est utilisée pour le suivi de mutations spécifiques (ex: MYD88 L265P dans le Waldenström, EZH2 Y641 dans le folliculaire) et la quantification du ctDNA. Moins multiplexée que le NGS (1-4 cibles) mais plus rapide, moins chère, et facilement standardisable — idéale pour le suivi longitudinal d'un marqueur connu."},
    {keys:['checkpoint','pd-1','pd-l1','nivolumab','pembrolizumab','immune checkpoint'],
     titre:'Les inhibiteurs de checkpoints en lymphome',
     texte:"Les inhibiteurs de checkpoints immunitaires bloquent les récepteurs inhibiteurs (PD-1, CTLA-4) qui freinent la réponse anti-tumorale des lymphocytes T. Dans le lymphome de Hodgkin, l'amplification 9p24.1 (contenant PD-L1/PD-L2) fait de cette maladie un candidat idéal : le nivolumab (anti-PD-1) obtient des taux de réponse de ~65-70% en rechute post-brentuximab. En revanche, dans les lymphomes B agressifs (DLBCL), les checkpoints seuls sont peu efficaces — le microenvironnement immunosuppresseur est différent. Des combinaisons (checkpoint + bispecifique, checkpoint + CAR-T) sont en cours d'évaluation."},
    {keys:['lymphome t','t-cell lymphoma','aitl','alcl','ptcl','angioimmunoblast'],
     titre:'La mutation RHOA G17V dans les lymphomes T angioimmunoblastiques (AITL)',
     texte:"La mutation RHOA G17V est présente dans ~70% des lymphomes T angioimmunoblastiques (AITL) et constitue un marqueur diagnostique quasi-pathognomonique. RHOA est une GTPase qui régule le cytosquelette et la signalisation T-cell receptor (TCR). La mutation G17V est « dominant-négative » : elle bloque la signalisation normale et active la voie PI3K/AKT, favorisant la prolifération des cellules T folliculaires helper (TFH). En pratique, cette mutation est détectable dans le sang par dPCR et pourrait servir de biomarqueur ctDNA pour le suivi des AITL — un domaine encore peu exploré mais prometteur. Combinée aux mutations TET2 (présentes dans l'hématopoïèse clonale pré-tumorale) et IDH2, elle définit un profil génétique unique qui ouvre la voie à des thérapies ciblées épigénétiques."},
    {keys:['hodgkin','reed-sternberg','brentuximab','hl classique'],
     titre:'Le lymphome de Hodgkin classique',
     texte:"Le lymphome de Hodgkin classique (cHL) est caractérisé par les cellules de Reed-Sternberg (< 1% de la masse tumorale) dans un microenvironnement inflammatoire riche. Quatre sous-types : scléro-nodulaire (70%), cellularité mixte, riche en lymphocytes, déplétion lymphocytaire. Le traitement standard (ABVD ± radiothérapie) guérit ~80% des patients. Avancées majeures : brentuximab vedotin + AVD (ECHELON-1, remplaçant le BEACOPP), nivolumab/pembrolizumab en rechute, et TEP-TDM intérimaire pour la désescalade. Le ctDNA dans le cHL est un défi car les cellules RS sont rares — des approches par capture de réarrangements Ig et par fragmentomique sont en développement."},
    {keys:['who 2022','icc 2022','classification','5th edition'],
     titre:'Les nouvelles classifications WHO 2022 / ICC 2022',
     texte:"En 2022, deux classifications concurrentes des néoplasies hématopoïétiques ont été publiées simultanément : la WHO 5e édition et la ICC (International Consensus Classification). Les deux introduisent des sous-types moléculaires pour le DLBCL (GCB vs ABC intégrés formellement), reconnaissent le « lymphome B de haut grade avec réarrangements MYC et BCL2 » (anciennement « double-hit »), et affinent les catégories de lymphomes T. La coexistence de deux classifications crée une confusion mais reflète la transition vers une nosologie moléculaire. En pratique, les différences sont mineures et convergent vers l'intégration de la génomique dans le diagnostic."},
    {keys:['machine learning','deep learning','ia ','intelligence artificielle','neural network','random forest','transformer'],
     titre:'L\'IA en hématologie',
     texte:"L'intelligence artificielle en hémato-oncologie couvre plusieurs axes : (1) histopathologie digitale — des CNN (réseaux convolutifs) classent les sous-types de lymphome à partir de lames HES avec des performances proches de l'expert ; (2) prédiction pronostique — des modèles intégrant données cliniques, biologiques et génomiques (random forests, XGBoost) surpassent les scores classiques (IPI) ; (3) analyse du cfDNA — le ML détecte des signatures fragmentomiques ou mutationnelles discriminantes ; (4) NLP — l'extraction automatisée de données à partir des comptes rendus et de la littérature. La validation clinique reste le maillon faible : peu de modèles ont été testés en prospectif."},
    {keys:['venetoclax','bcl-2','bcl2','abl-'],
     titre:'Le venetoclax (anti-BCL2)',
     texte:"Le venetoclax est un inhibiteur sélectif de BCL-2, protéine anti-apoptotique surexprimée dans de nombreuses hémopathies. Approuvé dans la LLC (en combinaison avec obinutuzumab ou rituximab) et la LAM (avec azacitidine), il a transformé le pronostic de ces maladies. Dans les lymphomes, BCL2 est transloqué dans ~85% des lymphomes folliculaires (t(14;18)) et ~30% des DLBCL-GCB. Des essais en cours évaluent le venetoclax dans les lymphomes en rechute, souvent en combinaison avec R-CHOP ou des bispecifiques. Le suivi du ctDNA pourrait identifier précocement les patients répondeurs au venetoclax."},
    {keys:['lysarc','lysa','french lymphoma','groupe d\'étude'],
     titre:'Le LYSARC et le réseau lymphome français',
     texte:"Le LYSARC (Lymphoma Academic Research Organisation) est le groupe coopérateur français dédié aux lymphomes, issu du GELA (Groupe d'Étude des Lymphomes de l'Adulte). Basé à Lyon (Centre Léon Bérard), il coordonne des essais multicentriques nationaux et internationaux. Le réseau français a contribué à des essais majeurs : POLARIX (Tilly), REMARC, GAINED, et des études translationelles sur le ctDNA. Pour un chercheur à Henri Mondor, le LYSARC est le principal vecteur d'accès aux essais lymphome et aux cohortes biologiques associées."},
    {keys:['nanopore','oxford nanopore','long read','minion','ont'],
     titre:'Le séquençage Nanopore pour le ctDNA',
     texte:"La technologie Oxford Nanopore (ONT) séquence des molécules d'ADN individuelles en temps réel en les faisant passer à travers un nanopore protéique. Contrairement au NGS classique (lectures courtes de 150-300 pb), le Nanopore produit des lectures longues (>10 kb) et détecte directement les modifications épigénétiques (méthylation 5mC) sans bisulfite. Pour le ctDNA, les applications émergentes incluent : profil de méthylation du cfDNA pour identifier le tissu d'origine, détection de variants structuraux, et séquençage rapide point-of-care (MinION). La sensibilité reste inférieure au NGS ciblé pour les faibles fractions tumorales, mais progresse rapidement."}
  ];

  // Construire le corpus textuel de la semaine (tous les tags, titres, résumés)
  const corpus = DATA.map(a => [a.titre, a.tags, a.resume, a.categorie, a.critique || ''].join(' ').toLowerCase()).join(' ');

  // Trouver les concepts qui matchent la biblio
  const matched = concepts.filter(c => c.keys.some(k => corpus.includes(k.toLowerCase())));
  const pool = matched.length > 0 ? matched : concepts; // fallback: tout montrer si rien ne matche

  // Rotation hebdo parmi les concepts matchés
  const now = new Date();
  const jan4 = new Date(now.getFullYear(), 0, 4);
  const weekNum = Math.ceil(((now - jan4) / 86400000 + jan4.getDay() + 1) / 7);
  const c = pool[weekNum % pool.length];

  const container = document.getElementById('didYouKnow');
  if (container) {
    const matchCount = matched.length;
    container.innerHTML = `<div style="display:flex;align-items:flex-start;gap:14px;">
      <span style="font-size:2.2rem;">🎓</span>
      <div>
        <div style="font-weight:700;font-size:1.05rem;color:#e2e8f0;margin-bottom:8px;">${c.titre}</div>
        <div style="font-size:0.85rem;color:#cbd5e1;line-height:1.7;">${c.texte}</div>
        <div style="font-size:0.7rem;color:#475569;margin-top:10px;font-style:italic;">Concept lié à ${matchCount} article${matchCount>1?'s':''} de votre veille cette semaine · Change chaque semaine</div>
      </div>
    </div>`;
  }
})();

// --- Suggestion de la semaine ---
(function renderWeeklySuggestion() {
  const suggestions = [
    {icon:'📊', titre:'Exporter le feedback régulièrement', texte:"Pensez à cliquer sur « Exporter feedback » après avoir noté vos articles. Le système apprend de vos préférences : plus vous notez, plus le scoring s'affine. Les bonus/malus sont recalculés automatiquement par régression OLS à chaque import."},
    {icon:'🔗', titre:'Explorer les articles liés', texte:"Pour chaque article intéressant, demandez « articles liés » dans Cowork en donnant le PMID. Le système interroge PubMed pour trouver les 5 meilleurs articles connexes (IF ≥ 5), une façon efficace d'élargir votre veille sans bruit."},
    {icon:'🏷️', titre:'Utiliser les filtres combinés', texte:"Combinez catégorie + recherche textuelle pour un ciblage précis. Par exemple, filtrez « ctDNA — Lymphomes » puis tapez « MRD » dans la barre de recherche. Le filtre pays (cliquez sur la carte ou tapez « pays:FR ») est aussi très puissant."},
    {icon:'📈', titre:'Suivre les tendances temporelles', texte:"Le graphique de tendance montre l'évolution du volume d'articles par catégorie. Un pic dans une catégorie peut signaler un congrès récent (ASH, ASCO, EHA) ou une vague de publications post-essai clinique. Surveillez les inflexions."},
    {icon:'🧪', titre:'Croiser essais cliniques et articles', texte:"Les essais cliniques listés dans le dashboard sont mis à jour mensuellement. Quand un article mentionne un essai (ex: POLARIX, ZUMA-7), vérifiez dans la section essais si de nouveaux résultats sont attendus — c'est souvent là que naissent les meilleures idées."},
    {icon:'🗺️', titre:'Exploiter la carte géographique', texte:"Cliquez sur un pays dans la carte pour filtrer ses publications. Utile pour identifier des collaborateurs potentiels ou suivre l'activité de recherche d'une région. Les pays avec le plus de points sont souvent ceux avec les essais les plus actifs."},
    {icon:'🔬', titre:'Surveiller les preprints', texte:"Les preprints (bioRxiv/medRxiv) apparaissent souvent 3-6 mois avant la publication. Les repérer tôt donne un avantage stratégique, surtout pour les méthodologies ctDNA émergentes. Filtrez par catégorie « Preprint » ou cherchez « preprint » dans la barre."},
    {icon:'👥', titre:'Identifier les auteurs clés émergents', texte:"Le classement des auteurs les plus publiants (en haut) se met à jour chaque semaine. Un auteur qui apparaît soudainement avec plusieurs publications peut signaler un nouveau groupe de recherche à suivre. Cliquez sur un nom pour voir ses articles."},
    {icon:'🎯', titre:'Affiner le scoring avec le feedback', texte:"Les articles notés « Utile » augmentent le score des articles similaires (même catégorie, mêmes tags, même journal). À l'inverse, « Bof » diminue le score de ces patterns. Après quelques semaines, le digest sera calibré sur vos centres d'intérêt."},
    {icon:'💡', titre:'Exploiter les articles hors champ', texte:"La section « Hors champ » propose des articles d'autres domaines avec un pont méthodologique vers la biopsie liquide. Ces transferts de technologie (physique statistique → fragmentomics, IA → déconvolution) sont souvent les plus innovants pour un projet de recherche."},
    {icon:'🔄', titre:'Rétrospective vs hebdo', texte:"Utilisez le filtre « Rétrospective » pour parcourir les articles historiques (2014-2025) importés en masse, et le filtre par semaine pour la veille courante. Les deux se complètent : la rétro donne le contexte, l'hebdo donne l'actualité."},
    {icon:'📝', titre:'Pistes de recherche trial-aware', texte:"Les pistes de recherche suggérées sont croisées avec les essais cliniques en cours. Si un champ « Essais existants » apparaît, c'est que l'idée est partiellement couverte — le delta restant est souvent la niche la plus pertinente pour un nouveau projet."},
    {icon:'🛠️', titre:'Idée d\'amélioration : alertes auteur clé', texte:"Vous pourriez demander à Cowork d'ajouter de nouveaux auteurs à surveiller dans outils/auteurs_cles.txt. Dès qu'un de ces auteurs publie, l'article sera mis en évidence avec un badge doré dans le dashboard. Pensez à y ajouter les auteurs que vous croisez en congrès."},
    {icon:'🛠️', titre:'Idée d\'amélioration : résumés en français', texte:"Le digest génère actuellement des résumés et critiques en français. Si vous préférez un format différent (plus court, plus clinique, plus méthodologique), dites-le à Cowork — le prompt du digest s'adaptera via la boucle de feedback pour coller à vos préférences."},
    {icon:'🛠️', titre:'Idée d\'amélioration : veille congrès', texte:"La tâche hemato-clinical-trials récupère déjà les conférences à venir. Vous pourriez demander une alerte spécifique 2 semaines avant chaque congrès majeur (ASH, EHA, ASCO, ICML) avec les sessions à ne pas manquer et les abstracts pertinents."},
    {icon:'🛠️', titre:'Idée d\'amélioration : export bibliographique', texte:"Vous pouvez demander à Cowork d'exporter votre sélection d'articles au format RIS, BibTeX ou EndNote pour les importer directement dans Zotero ou Mendeley. Filtrez d'abord par catégorie ou score, puis demandez l'export."},
    {icon:'🛠️', titre:'Idée d\'amélioration : dashboard par projet', texte:"Si vous travaillez sur plusieurs projets (ex: ctDNA MRD dans les DLBCL, fragmentomique SNC), vous pourriez demander des vues filtrées dédiées. Cowork peut générer un mini-dashboard par projet avec uniquement les articles pertinents."}
  ];
  // Rotation basée sur le numéro de semaine ISO
  const now = new Date();
  const jan4 = new Date(now.getFullYear(), 0, 4);
  const weekNum = Math.ceil(((now - jan4) / 86400000 + jan4.getDay() + 1) / 7);
  const s = suggestions[weekNum % suggestions.length];
  const container = document.getElementById('weeklySuggestion');
  if (container) {
    container.innerHTML = `<div style="display:flex;align-items:flex-start;gap:14px;">
      <span style="font-size:2rem;">${s.icon}</span>
      <div><div style="font-weight:700;font-size:1rem;color:#e2e8f0;margin-bottom:6px;">${s.titre}</div>
      <div style="font-size:0.85rem;color:#94a3b8;line-height:1.6;">${s.texte}</div></div>
    </div>`;
  }
})();

window.addEventListener('resize', () => { renderGeoMap(); });
