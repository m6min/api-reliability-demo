'use strict';

const DATASETS = { 'verification': '2 products', 'products-500': '500 products' };
const TARGET_RPS = 500;
const COLORS = { off: '#f2a541', on: '#3ecfb2', w1: '#7c8cff', w2: '#c084fc' };
const RUN_SHADES = { off: ['#f2a541', '#e07b39', '#f5c97a'], on: ['#3ecfb2', '#2a9d8f', '#8ce8d4'] };
const PCT_KEYS = ['50%', '66%', '75%', '80%', '90%', '95%', '98%', '99%', '99.9%', '100%'];
const WORKERS = { 1: { rps: 498.38, avg: 9, p95: 14, p99: 32 }, 2: { rps: 491.06, avg: 22, p95: 49, p99: 120 } };
const NF = [0, 1].map(d => new Intl.NumberFormat('en-US', { maximumFractionDigits: d, minimumFractionDigits: 0 }));

const state = { dataset: 'products-500', results: {}, detail: {}, hidden: new Set(), pctHidden: new Set() };
const $ = s => document.querySelector(s);
const median = v => { const a = [...v].sort((x, y) => x - y), m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
const fmt = (v, d = 0) => (NF[d] || NF[1]).format(Number(v));
const fmtMs = v => (v < 10 ? fmt(v, 1) : fmt(v)) + ' ms';
const pct = (a, b) => (b - a) / a * 100;
const runNo = id => id.slice(0, 2);
const isLatency = m => m !== 'rps';

const dom = {
  datasetBtns: [...document.querySelectorAll('[data-dataset]')],
  download: $('#download'),
  status: $('#status'),
  kpis: $('#kpis'),
  tlMetric: $('#tl-metric'),
  tlLegend: $('#tl-legend'),
  tlChart: $('#tl-chart'),
  tlNote: $('#tl-note'),
  takeaways: $('#takeaway-list'),
  pctLog: $('#pct-log'),
  pctLegend: $('#pct-legend'),
  pctChart: $('#pct-chart'),
  pctNote: $('#pct-note'),
  runMetric: $('#run-metric'),
  runChart: $('#run-chart'),
  runNote: $('#run-note'),
  dsMetric: $('#ds-metric'),
  dsChart: $('#ds-chart'),
  dsNote: $('#ds-note'),
  wkChart: $('#wk-chart'),
  runsSub: $('#runs-sub'),
  rows: $('#rows'),
  tip: $('#tooltip')
};

function parseCSV(text) {
  const lines = text.trim().split(/\r*\n/);
  if (lines.length < 2) return [];
  const keys = lines[0].trim().split(',');
  const out = new Array(lines.length - 1);
  let count = 0;
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const cols = line.split(',');
    const row = {};
    for (let j = 0; j < keys.length; j++) row[keys[j]] = cols[j];
    out[count++] = row;
  }
  out.length = count;
  return out;
}
async function getJSON(p) { const r = await fetch(p); if (!r.ok) throw Error(p); return r.json(); }
async function getText(p) { const r = await fetch(p); if (!r.ok) throw Error(p); return r.text(); }

async function loadDetail(ds) {
  if (state.detail[ds]) return state.detail[ds];
  const runs = state.results[ds];
  const out = {};
  await Promise.all(runs.map(async r => {
    const [hist, stats] = await Promise.all([
      getText(`data/${ds}/${r.id}_stats_history.csv`).then(parseCSV).catch(() => []),
      getText(`data/${ds}/${r.id}_stats.csv`).then(parseCSV).catch(() => [])
    ]);
    const agg = stats.find(s => s.Name === 'Aggregated') || {};
    const rows = hist.filter(h => h.Name === 'Aggregated' && +h['User Count'] > 0 && h['50%'] !== 'N/A');
    const t0 = rows.length ? +rows[0].Timestamp : 0;
    out[r.id] = {
      size: +agg['Average Content Size'] || 0,
      pct: PCT_KEYS.map(k => +agg[k]),
      series: rows.map(h => ({ t: +h.Timestamp - t0, rps: +h['Requests/s'], p50: +h['50%'], p95: +h['95%'] }))
    };
  }));
  return (state.detail[ds] = out);
}

const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}
function niceTicks(min, max, count = 5) {
  if (max === min) max = min + 1;
  const step0 = (max - min) / count, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
  const ticks = [];
  for (let v = Math.floor(min / step) * step; v <= max + step * 0.001; v += step) ticks.push(+v.toFixed(10));
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}
function logTicks(min, max) {
  const t = [];
  for (let e = Math.floor(Math.log10(min)); e <= Math.ceil(Math.log10(max)); e++) for (const m of [1, 2, 5]) { const v = m * 10 ** e; if (v >= min / 1.01 && v <= max * 1.01) t.push(v); }
  return t;
}
function nearestPoint(pts, xv) {
  let lo = 0, hi = pts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (pts[mid][0] < xv) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(pts[lo - 1][0] - xv) <= Math.abs(pts[lo][0] - xv)) return pts[lo - 1];
  return pts[lo];
}

let tipW = 160, tipH = 80, lastTipKey = '';
function showTip(e, title, rows, key = '') {
  if (!key || key !== lastTipKey) {
    lastTipKey = key;
    dom.tip.innerHTML = `<div class="t-title">${title}</div>` + rows.map(r => `<div class="t-row"><span><i class="sw" style="background:${r.color}"></i>${r.label}</span><b>${r.value}</b></div>`).join('');
    dom.tip.classList.add('show');
    tipW = dom.tip.offsetWidth;
    tipH = dom.tip.offsetHeight;
  } else {
    dom.tip.classList.add('show');
  }
  let x = e.clientX + 14, y = e.clientY - tipH - 10;
  if (x + tipW > innerWidth - 8) x = e.clientX - tipW - 14;
  if (y < 8) y = e.clientY + 14;
  dom.tip.style.transform = `translate3d(${x}px,${y}px,0)`;
}
const hideTip = () => { dom.tip.classList.remove('show'); lastTipKey = ''; };

function lineChart(box, { series, xFmt, yFmt, xTicks, yTitle, log = false, tipTitle }) {
  const W = box.clientWidth, H = box.clientHeight, m = { l: 52, r: 14, t: 10, b: 28 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': yTitle });
  const vis = series.filter(s => !s.hidden && s.points.length);
  if (!vis.length) { box.replaceChildren(svg); return; }
  let x0 = Infinity, x1 = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (const s of vis) {
    for (const p of s.points) {
      if (p[0] < x0) x0 = p[0];
      if (p[0] > x1) x1 = p[0];
      if (!log || p[1] > 0) {
        if (p[1] < yMin) yMin = p[1];
        if (p[1] > yMax) yMax = p[1];
      }
    }
  }
  let yt, Y;
  if (log) {
    yt = logTicks(yMin, yMax);
    const a = Math.log10(Math.min(yt[0], yMin)), b = Math.log10(Math.max(yt[yt.length - 1], yMax));
    Y = v => m.t + (H - m.t - m.b) * (1 - (Math.log10(Math.max(v, 1e-9)) - a) / (b - a || 1));
  } else {
    yt = niceTicks(0, yMax);
    Y = v => m.t + (H - m.t - m.b) * (1 - v / yt[yt.length - 1]);
  }
  const X = v => m.l + (W - m.l - m.r) * (x1 === x0 ? 0.5 : (v - x0) / (x1 - x0));
  for (const v of yt) {
    el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: 'grid-line' }, svg);
    el('text', { x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'axis-text' }, svg).textContent = yFmt(v);
  }
  for (const v of (xTicks || niceTicks(x0, x1, 6).filter(v => v >= x0 && v <= x1)))
    el('text', { x: X(v), y: H - 8, 'text-anchor': 'middle', class: 'axis-text' }, svg).textContent = xFmt(v);
  for (const s of vis) {
    const d = s.points.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
    el('path', { d, class: 'line', stroke: s.color, 'stroke-dasharray': s.dash || '' }, svg);
  }
  const cross = el('line', { y1: m.t, y2: H - m.b, class: 'crosshair', opacity: 0 }, svg);
  const dots = vis.map(s => el('circle', { r: 3.5, fill: s.color, stroke: '#151821', 'stroke-width': 2, opacity: 0 }, svg));
  const hit = el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: 'transparent' }, svg);
  let rectCache = null, raf = 0, lastEv = null;
  hit.addEventListener('mouseenter', () => { rectCache = svg.getBoundingClientRect(); });
  hit.addEventListener('mousemove', e => {
    lastEv = e;
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      const ev = lastEv;
      const r = rectCache || (rectCache = svg.getBoundingClientRect());
      const px = (ev.clientX - r.left) * (W / r.width);
      const xv = x0 + (px - m.l) / (W - m.l - m.r) * (x1 - x0);
      const rows = new Array(vis.length);
      let snap = null;
      for (let i = 0; i < vis.length; i++) {
        const s = vis[i], p = nearestPoint(s.points, xv);
        if (snap === null) snap = p[0];
        dots[i].setAttribute('cx', X(p[0]));
        dots[i].setAttribute('cy', Y(p[1]));
        dots[i].setAttribute('opacity', 1);
        rows[i] = { label: s.label, value: yFmt(p[1], true), color: s.color };
      }
      cross.setAttribute('x1', X(snap));
      cross.setAttribute('x2', X(snap));
      cross.setAttribute('opacity', 1);
      showTip(ev, tipTitle ? tipTitle(snap) : xFmt(snap), rows, `${yTitle}:${snap}`);
    });
  });
  hit.addEventListener('mouseleave', () => {
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    rectCache = null;
    hideTip();
    cross.setAttribute('opacity', 0);
    for (const d of dots) d.setAttribute('opacity', 0);
  });
  box.replaceChildren(svg);
}

function barChart(box, { groups, yFmt, refLines = [] }) {
  const W = box.clientWidth, H = box.clientHeight, m = { l: 52, r: 14, t: 22, b: 30 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  let max = 0;
  for (const g of groups) for (const b of g.bars) if (b.value > max) max = b.value;
  for (const r of refLines) if (r.value > max) max = r.value;
  const yt = niceTicks(0, max), top = yt[yt.length - 1];
  const Y = v => m.t + (H - m.t - m.b) * (1 - v / top);
  for (const v of yt) {
    el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: 'grid-line' }, svg);
    el('text', { x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'axis-text' }, svg).textContent = yFmt(v);
  }
  const gw = (W - m.l - m.r) / groups.length;
  groups.forEach((g, gi) => {
    const n = g.bars.length, bw = Math.min(46, (gw * 0.7) / n), gap = 6;
    const start = m.l + gi * gw + (gw - (n * bw + (n - 1) * gap)) / 2;
    g.bars.forEach((b, bi) => {
      const x = start + bi * (bw + gap), y = Y(b.value), h = Math.max(1, H - m.b - y);
      const rect = el('rect', { x, y, width: bw, height: h, rx: 5, fill: b.color, class: 'bar' }, svg);
      if (n <= 3) el('text', { x: x + bw / 2, y: y - 6, 'text-anchor': 'middle', class: 'bar-label' }, svg).textContent = yFmt(b.value, true);
      const tipRows = [{ label: b.label, value: yFmt(b.value, true), color: b.color }, ...(b.extra || [])];
      const tipKey = `${g.label}:${b.label}:${b.value}`;
      rect.addEventListener('mousemove', e => showTip(e, g.label, tipRows, tipKey));
      rect.addEventListener('mouseleave', hideTip);
    });
    el('text', { x: m.l + gi * gw + gw / 2, y: H - 8, 'text-anchor': 'middle', class: 'axis-text' }, svg).textContent = g.label;
  });
  for (const r of refLines) {
    el('line', { x1: m.l, x2: W - m.r, y1: Y(r.value), y2: Y(r.value), stroke: r.color, 'stroke-dasharray': '4 4', 'stroke-opacity': .8 }, svg);
    el('text', { x: W - m.r, y: Y(r.value) - 5, 'text-anchor': 'end', class: 'axis-text', fill: r.color, style: `fill:${r.color}` }, svg).textContent = r.label;
  }
  box.replaceChildren(svg);
}

function legend(box, items, hiddenSet, onChange) {
  const frag = document.createDocumentFragment();
  for (const it of items) {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-pressed', String(!hiddenSet.has(it.key)));
    b.innerHTML = `<i style="background:${it.color}"></i>${it.label}`;
    b.onclick = () => { hiddenSet.has(it.key) ? hiddenSet.delete(it.key) : hiddenSet.add(it.key); onChange(); };
    frag.appendChild(b);
  }
  box.replaceChildren(frag);
}

function split(runs) {
  const off = runs.filter(r => !r.cache), on = runs.filter(r => r.cache);
  const med = (g, k) => median(g.map(r => r[k]));
  return { off, on, med };
}
function runColor(r, runs) {
  const group = runs.filter(x => x.cache === r.cache);
  return RUN_SHADES[r.cache ? 'on' : 'off'][group.indexOf(r) % 3];
}
const runLabel = r => `Run ${runNo(r.id)} · ${r.cache ? 'ON' : 'OFF'}`;
const yMs = (v, exact) => exact ? fmtMs(v) : fmt(v);
const yRps = (v, exact) => exact ? fmt(v, 1) + ' req/s' : fmt(v);

function renderKPIs(runs, detail) {
  const { off, on, med } = split(runs);
  const card = (label, offV, onV, unit, lowerIsBetter, fmtV) => {
    const ch = pct(offV, onV), good = lowerIsBetter ? ch < 0 : ch > 0;
    const badge = Math.abs(ch) >= 100 ? `${(onV / offV).toFixed(1)}×` : `${ch > 0 ? '+' : '-'}${fmt(Math.abs(ch), 1)}%`;
    return `<article class="card kpi"><p class="label">${label}</p>
      <div class="value">${fmtV(onV)}<span class="unit">${unit}</span><span class="badge ${good ? 'good' : 'bad'}">${badge}</span></div>
      <div class="compare"><span><i class="sw off"></i>Cache OFF <b>${fmtV(offV)}</b></span><span><i class="sw on"></i>Cache ON <b>${fmtV(onV)}</b></span></div></article>`;
  };
  const f = v => v < 10 ? fmt(v, 1) : fmt(v);
  const offR = med(off, 'rps'), onR = med(on, 'rps');
  const total = runs.reduce((a, r) => a + r.requests, 0), fails = runs.reduce((a, r) => a + r.failures, 0);
  const size = Object.values(detail)[0]?.size || 0;
  dom.kpis.innerHTML =
    card('Average latency with cache', med(off, 'avg'), med(on, 'avg'), 'ms', true, f) +
    card('P95 latency with cache', med(off, 'p95'), med(on, 'p95'), 'ms', true, f) +
    `<article class="card kpi"><p class="label">Throughput vs 500 req/s target</p>
      <div class="value">${fmt(onR)}<span class="unit">req/s</span><span class="badge good">${(onR / offR).toFixed(1)}×</span></div>
      <div class="progress"><i style="width:${Math.min(100, onR / TARGET_RPS * 100)}%;background:var(--on)"></i></div>
      <div class="progress"><i style="width:${Math.min(100, offR / TARGET_RPS * 100)}%;background:var(--off)"></i></div>
      <div class="progress-meta"><span>ON ${fmt(onR / TARGET_RPS * 100)}% · OFF ${fmt(offR / TARGET_RPS * 100)}%</span><span>of target</span></div></article>` +
    `<article class="card kpi"><p class="label">Requests served</p>
      <div class="value">${fmt(total)}<span class="badge ${fails ? 'bad' : 'good'}">${fails ? fails + ' failed' : '0 failed'}</span></div>
      <div class="compare"><span>Response size <b>${size ? fmt(size / 1024, 1) + ' KB' : '—'}</b></span><span>Runs <b>${runs.length}</b></span></div></article>`;
}

function renderTimeline(runs, detail) {
  const metric = dom.tlMetric.value;
  const series = runs.map(r => ({
    key: r.id, label: runLabel(r), color: runColor(r, runs), dash: '',
    hidden: state.hidden.has(r.id),
    points: (detail[r.id]?.series || []).filter(p => metric !== 'rps' || p.rps > 0).map(p => [p.t, p[metric]])
  }));
  legend(dom.tlLegend, series, state.hidden, () => renderTimeline(runs, detail));
  lineChart(dom.tlChart, {
    series, yTitle: metric, xFmt: v => v + 's', tipTitle: v => `${v}s into the run`,
    yFmt: metric === 'rps' ? yRps : yMs
  });
  const { off, on } = split(runs);
  const tail = (g, k) => median(g.flatMap(r => (detail[r.id]?.series || []).slice(-30).map(p => p[k])).filter(Boolean));
  const o = tail(off, metric), n = tail(on, metric);
  const msg = {
    rps: `Near the end of the runs, uncached samples sit around <b>${fmt(o)} req/s</b> and cached samples around <b>${fmt(n)} req/s</b>. ${n >= TARGET_RPS * 0.95 ? 'The cached runs get close to my 500 req/s target. That tells me they handled this workload, not how much more they could handle.' : 'Neither group reaches my 500 req/s target. I would need more measurements to tell which part is holding things up.'}`,
    p50: `Near the end of the runs, sampled median latency is around <b>${fmt(o)} ms</b> without cache and <b>${fmt(n)} ms</b> with it. I use this view to see how response times change during a run; I didn't measure queue length.`,
    p95: `Near the end of the runs, sampled P95 is around <b>${fmt(o)} ms</b> (OFF) vs <b>${fmt(n)} ms</b> (ON). P95 means about 95% of requests finish within that time. I can see spikes here, but the chart alone doesn't tell me what caused them.`
  }[metric];
  dom.tlNote.innerHTML = msg;
}

function renderPercentiles(runs, detail) {
  const log = dom.pctLog.checked;
  const series = runs.map(r => ({ key: r.id, label: runLabel(r), color: runColor(r, runs), hidden: state.pctHidden.has(r.id), points: (detail[r.id]?.pct || []).map((v, i) => [i, v]) }));
  legend(dom.pctLegend, series, state.pctHidden, () => renderPercentiles(runs, detail));
  lineChart(dom.pctChart, {
    series, log, yTitle: 'latency', xTicks: PCT_KEYS.map((_, i) => i),
    xFmt: i => PCT_KEYS[i].replace('100%', 'max').replace('%', ''), tipTitle: i => `P${PCT_KEYS[i].replace('%', '')}`, yFmt: yMs
  });
  const { off, on } = split(runs);
  const at = (g, i) => median(g.map(r => detail[r.id]?.pct[i]).filter(Number.isFinite));
  const i99 = PCT_KEYS.indexOf('99%');
  dom.pctNote.innerHTML = `Median latency (P50): <b>${fmt(at(off, 0))} → ${fmt(at(on, 0))} ms</b>. P99: <b>${fmt(at(off, i99))} → ${fmt(at(on, i99))} ms</b>, OFF → ON. P99 is the time about 99% of requests finish within; roughly 1% take longer. These numbers are medians of the three runs' percentiles, not percentiles calculated from all requests together.`;
}

function renderRuns(runs) {
  const metric = dom.runMetric.value;
  const { off, on, med } = split(runs);
  const yf = isLatency(metric) ? yMs : yRps;
  barChart(dom.runChart, {
    yFmt: yf,
    groups: runs.map(r => ({ label: `#${runNo(r.id)} ${r.cache ? 'ON' : 'OFF'}`, bars: [{ label: runLabel(r), value: r[metric], color: r.cache ? COLORS.on : COLORS.off, extra: [{ label: 'Requests', value: fmt(r.requests), color: 'transparent' }] }] })),
    refLines: metric === 'rps' ? [{ value: TARGET_RPS, color: '#8b91a1', label: 'target 500' }] : []
  });
  const rng = g => `${fmt(Math.min(...g.map(r => r[metric])))}–${fmt(Math.max(...g.map(r => r[metric])))}`;
  const spread = g => (Math.max(...g.map(r => r[metric])) - Math.min(...g.map(r => r[metric]))) / med(g, metric) * 100;
  const noisier = spread(off) > spread(on) ? 'uncached' : 'cached';
  dom.runNote.innerHTML = `I mixed the OFF/ON order to reduce the effect of changes on my laptop over time. OFF ranged <b>${rng(off)}</b>, ON ranged <b>${rng(on)}</b>${isLatency(metric) ? ' ms' : ' req/s'}. The ${noisier} runs varied more relative to their median. I show all three so one unusually good run doesn't tell the whole story.`;
}

function renderDatasets() {
  const metric = dom.dsMetric.value;
  const yf = isLatency(metric) ? yMs : yRps;
  const ds = Object.keys(DATASETS).filter(k => state.results[k]);
  const groups = ds.map(k => { const { off, on, med } = split(state.results[k]); return { label: DATASETS[k], bars: [{ label: 'Cache OFF', value: med(off, metric), color: COLORS.off }, { label: 'Cache ON', value: med(on, metric), color: COLORS.on }] }; });
  barChart(dom.dsChart, { groups, yFmt: yf });
  if (groups.length < 2) { dom.dsNote.textContent = ''; return; }
  const [s, b] = groups;
  const cut = g => fmt(Math.abs(pct(g.bars[0].value, g.bars[1].value)));
  dom.dsNote.innerHTML = isLatency(metric)
    ? `Going from 2 to 500 products made uncached requests <b>${(b.bars[0].value / s.bars[0].value).toFixed(1)}×</b> slower and cached ones <b>${(b.bars[1].value / s.bars[1].value).toFixed(0)}×</b> slower. The cache still cuts ${cut(b)}%, down from ${cut(s)}%. My read: Redis saves the database trip, but a 70 KB list still has to be serialized and sent every time, and that part doesn't get cached away.`
    : `With 2 products the cached API gets close to my 500 req/s target. With 500 products I measured around <b>${fmt(b.bars[1].value)} req/s</b> with cache and <b>${fmt(b.bars[0].value)}</b> without it. These are results for this workload, not maximum capacity figures.`;
}

function renderWorkers() {
  barChart(dom.wkChart, {
    yFmt: yMs,
    groups: [['avg', 'Average'], ['p95', 'P95'], ['p99', 'P99']].map(([k, l]) => ({ label: l, bars: [{ label: '1 worker', value: WORKERS[1][k], color: COLORS.w1 }, { label: '2 workers', value: WORKERS[2][k], color: COLORS.w2 }] }))
  });
}

function renderTable(runs) {
  dom.runsSub.textContent = `${DATASETS[state.dataset]} · ${runs.length} runs · numbers from Locust CSV summaries`;
  dom.rows.innerHTML = runs.map(r => {
    const ok = !r.failures && !r.cpu_warning && !r.exit_code;
    return `<tr><td class="mono">${r.id}</td><td><span class="tag ${r.cache ? 'on' : 'off'}">${r.cache ? 'ON' : 'OFF'}</span></td>
      <td class="num">${fmt(r.requests)}</td><td class="num">${fmt(r.avg, 1)}</td><td class="num">${fmt(r.p95)}</td><td class="num">${fmt(r.p99)}</td>
      <td class="num">${fmt(r.rps, 1)}</td><td class="num">${r.failures}</td>
      <td><span class="check ${ok ? '' : 'warn'}">${ok ? 'Clean' : r.cpu_warning ? 'CPU warning' : 'Check exit code'}</span></td></tr>`;
  }).join('');
}

function renderTakeaways(runs, detail) {
  const { off, on, med } = split(runs);
  const a0 = med(off, 'avg'), a1 = med(on, 'avg'), r0 = med(off, 'rps'), r1 = med(on, 'rps');
  const total = runs.reduce((s, r) => s + r.requests, 0), fails = runs.reduce((s, r) => s + r.failures, 0);
  const size = Object.values(detail)[0]?.size || 0;
  const items = [
    `In these runs, turning Redis on dropped average response time from <mark>${fmt(a0)} ms down to ${fmt(a1)} ms</mark> (${fmt(Math.abs(pct(a0, a1)))}% lower latency).`,
    r1 >= TARGET_RPS * 0.95
      ? `With cache ON, the API got close to my <mark>500 req/s target</mark>. Without cache, I measured around ${fmt(r0)} req/s in this workload.`
      : `Cache boosted throughput from <mark>${fmt(r0)} to ${fmt(r1)} req/s</mark> (${(r1 / r0).toFixed(1)}×), though it still fell short of the 500 req/s target.`
  ];
  if (size > 10000) items.push(`Each response sends about <mark>${fmt(size / 1024)} KB of JSON</mark>. Even with cache, the API still has to prepare and send the whole list. <mark>Pagination could help</mark>, but I haven't measured how much time each step takes.`);
  const worst = on.reduce((a, b) => b.p95 > a.p95 ? b : a);
  if (worst.p95 > 2 * median(on.map(r => r.p95))) items.push(`Run ${runNo(worst.id)} had a higher P95 (<mark>${fmt(worst.p95)} ms</mark>). I kept it in the results; I don't know what caused that spike.`);
  items.push(`Across the recorded <mark>${fmt(total)} requests</mark> I saw <mark>${fails} failures</mark>. I also saved a response fingerprint before each run to check that the starting data stayed the same.`);
  dom.takeaways.innerHTML = items.map(t => `<li>${t}</li>`).join('');
}

let version = 0;
async function render() {
  const v = ++version, ds = state.dataset, runs = state.results[ds];
  for (const b of dom.datasetBtns) b.setAttribute('aria-pressed', String(b.dataset.dataset === ds));
  dom.download.href = `data/${ds}/results.json`;
  if (!runs?.length) { dom.status.textContent = 'No recorded runs for this dataset.'; return; }
  const detail = await loadDetail(ds);
  if (v !== version) return;
  const clean = runs.every(r => !r.failures && !r.cpu_warning && !r.exit_code);
  dom.status.textContent = `${runs[0].product_count} products in the database · ${runs.length} runs · ${clean ? 'no failures, no CPU warnings' : 'some runs are flagged, check the table'}`;
  renderKPIs(runs, detail);
  renderTimeline(runs, detail);
  renderTakeaways(runs, detail);
  renderPercentiles(runs, detail);
  renderRuns(runs);
  renderDatasets();
  renderWorkers();
  renderTable(runs);
}

function redrawCharts() {
  const ds = state.dataset, runs = state.results[ds], detail = state.detail[ds];
  if (!runs?.length || !detail) return;
  renderTimeline(runs, detail);
  renderPercentiles(runs, detail);
  renderRuns(runs);
  renderDatasets();
  renderWorkers();
}

async function init() {
  await Promise.all(Object.keys(DATASETS).map(async k => { try { state.results[k] = await getJSON(`data/${k}/results.json`); } catch { } }));
  if (!Object.keys(state.results).length) {
    dom.status.textContent = 'Couldn\'t load results. Serve the docs folder over HTTP (see README).';
    return;
  }
  if (!state.results[state.dataset]) state.dataset = Object.keys(state.results)[0];
  render();
}

for (const b of dom.datasetBtns) b.addEventListener('click', () => { state.dataset = b.dataset.dataset; state.hidden.clear(); state.pctHidden.clear(); render(); });
dom.tlMetric.addEventListener('change', () => { const r = state.results[state.dataset], d = state.detail[state.dataset]; if (r && d) renderTimeline(r, d); });
dom.pctLog.addEventListener('change', () => { const r = state.results[state.dataset], d = state.detail[state.dataset]; if (r && d) renderPercentiles(r, d); });
dom.runMetric.addEventListener('change', () => { const r = state.results[state.dataset]; if (r) renderRuns(r); });
dom.dsMetric.addEventListener('change', renderDatasets);
let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(redrawCharts, 150); }, { passive: true });

const links = [...document.querySelectorAll('nav a[href^="#"]')];
const targets = links.map(l => document.querySelector(l.getAttribute('href')));
let lockUntil = 0, activeIdx = 0, spyRaf = 0;
function setActive(i) {
  if (i === activeIdx) return;
  links[activeIdx]?.classList.remove('active');
  links[i]?.classList.add('active');
  activeIdx = i;
}
function spy() {
  spyRaf = 0;
  if (performance.now() < lockUntil) return;
  const atBottom = innerHeight + scrollY >= document.documentElement.scrollHeight - 4;
  let idx = 0;
  if (atBottom) idx = links.length - 1;
  else {
    for (let k = 1; k < targets.length; k++) {
      const t = targets[k];
      if (t && t.getBoundingClientRect().top <= 140) idx = k;
    }
  }
  setActive(idx);
}
links.forEach((l, k) => l.addEventListener('click', () => { setActive(k); lockUntil = performance.now() + 1000; }));
addEventListener('scroll', () => { if (!spyRaf) spyRaf = requestAnimationFrame(spy); }, { passive: true });

init();
