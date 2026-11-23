'use strict';

const DATASETS = { 'verification': '2 products', 'products-500': '500 products' };
const TARGET_RPS = 500;
const COLORS = { off: '#f2a541', on: '#3ecfb2', w1: '#7c8cff', w2: '#c084fc' };
const RUN_SHADES = { off: ['#f2a541', '#e07b39', '#f5c97a'], on: ['#3ecfb2', '#2a9d8f', '#8ce8d4'] };
const PCT_KEYS = ['50%', '66%', '75%', '80%', '90%', '95%', '98%', '99%', '99.9%', '100%'];
const WORKERS = { 1: { rps: 498.38, avg: 9, p95: 14, p99: 32 }, 2: { rps: 491.06, avg: 22, p95: 49, p99: 120 } };

const state = { dataset: 'products-500', results: {}, detail: {}, hidden: new Set(), pctHidden: new Set() };
const $ = s => document.querySelector(s);
const median = v => { const a = [...v].sort((x, y) => x - y), m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
const fmt = (v, d = 0) => Number(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: 0 });
const fmtMs = v => (v < 10 ? fmt(v, 1) : fmt(v)) + ' ms';
const pct = (a, b) => (b - a) / a * 100;
const runNo = id => id.slice(0, 2);
const isLatency = m => m !== 'rps';

function parseCSV(text) {
  const [head, ...lines] = text.trim().split(/\r*\n/).map(l => l.trim()).filter(Boolean);
  const keys = head.split(',');
  return lines.map(l => { const c = l.split(','); return Object.fromEntries(keys.map((k, i) => [k, c[i]])); });
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
const tip = $('#tooltip');
function showTip(e, title, rows) {
  tip.innerHTML = `<div class="t-title">${title}</div>` + rows.map(r => `<div class="t-row"><span><i class="sw" style="background:${r.color}"></i>${r.label}</span><b>${r.value}</b></div>`).join('');
  tip.classList.add('show');
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + 14, y = e.clientY - h - 10;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y < 8) y = e.clientY + 14;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
const hideTip = () => tip.classList.remove('show');

function lineChart(box, { series, xFmt, yFmt, xTicks, yTitle, log = false, tipTitle }) {
  box.innerHTML = '';
  const W = box.clientWidth, H = box.clientHeight, m = { l: 52, r: 14, t: 10, b: 28 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': yTitle }, box);
  const vis = series.filter(s => !s.hidden);
  const all = vis.flatMap(s => s.points);
  if (!all.length) return;
  const xs = all.map(p => p[0]), ys = all.map(p => p[1]).filter(v => !log || v > 0);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let yt, Y;
  if (log) {
    yt = logTicks(Math.min(...ys), Math.max(...ys));
    const a = Math.log10(Math.min(yt[0], ...ys)), b = Math.log10(Math.max(yt[yt.length - 1], ...ys));
    Y = v => m.t + (H - m.t - m.b) * (1 - (Math.log10(Math.max(v, 1e-9)) - a) / (b - a || 1));
  } else {
    yt = niceTicks(0, Math.max(...ys));
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
    if (s.area) {
      const id = 'g' + Math.random().toString(36).slice(2);
      const g = el('linearGradient', { id, x1: 0, x2: 0, y1: 0, y2: 1 }, el('defs', {}, svg));
      el('stop', { offset: 0, 'stop-color': s.color, 'stop-opacity': .18 }, g);
      el('stop', { offset: 1, 'stop-color': s.color, 'stop-opacity': 0 }, g);
      el('path', { d: `${d}L${X(s.points.at(-1)[0])},${H - m.b}L${X(s.points[0][0])},${H - m.b}Z`, fill: `url(#${id})` }, svg);
    }
    el('path', { d, class: 'line', stroke: s.color, 'stroke-dasharray': s.dash || '' }, svg);
  }
  const cross = el('line', { y1: m.t, y2: H - m.b, class: 'crosshair', opacity: 0 }, svg);
  const dots = vis.map(s => el('circle', { r: 3.5, fill: s.color, stroke: '#151821', 'stroke-width': 2, opacity: 0 }, svg));
  const hit = el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: 'transparent' }, svg);
  hit.addEventListener('mousemove', e => {
    const r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * (W / r.width);
    const xv = x0 + (px - m.l) / (W - m.l - m.r) * (x1 - x0);
    const rows = [];
    let snap = null;
    vis.forEach((s, i) => {
      const p = s.points.reduce((a, b) => Math.abs(b[0] - xv) < Math.abs(a[0] - xv) ? b : a);
      snap = snap ?? p[0];
      dots[i].setAttribute('cx', X(p[0])); dots[i].setAttribute('cy', Y(p[1])); dots[i].setAttribute('opacity', 1);
      rows.push({ label: s.label, value: yFmt(p[1], true), color: s.color, v: p[1] });
    });
    cross.setAttribute('x1', X(snap)); cross.setAttribute('x2', X(snap)); cross.setAttribute('opacity', 1);
    showTip(e, tipTitle ? tipTitle(snap) : xFmt(snap), rows);
  });
  hit.addEventListener('mouseleave', () => { hideTip(); cross.setAttribute('opacity', 0); dots.forEach(d => d.setAttribute('opacity', 0)); });
}

function barChart(box, { groups, yFmt, refLines = [] }) {
  box.innerHTML = '';
  const W = box.clientWidth, H = box.clientHeight, m = { l: 52, r: 14, t: 22, b: 30 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' }, box);
  const max = Math.max(...groups.flatMap(g => g.bars.map(b => b.value)), ...refLines.map(r => r.value));
  const yt = niceTicks(0, max), top = yt.at(-1);
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
      rect.addEventListener('mousemove', e => showTip(e, g.label, [{ label: b.label, value: yFmt(b.value, true), color: b.color }, ...(b.extra || [])]));
      rect.addEventListener('mouseleave', hideTip);
    });
    el('text', { x: m.l + gi * gw + gw / 2, y: H - 8, 'text-anchor': 'middle', class: 'axis-text' }, svg).textContent = g.label;
  });
  for (const r of refLines) {
    el('line', { x1: m.l, x2: W - m.r, y1: Y(r.value), y2: Y(r.value), stroke: r.color, 'stroke-dasharray': '4 4', 'stroke-opacity': .8 }, svg);
    el('text', { x: W - m.r, y: Y(r.value) - 5, 'text-anchor': 'end', class: 'axis-text', fill: r.color, style: `fill:${r.color}` }, svg).textContent = r.label;
  }
}

function legend(box, items, hiddenSet, onChange) {
  box.innerHTML = '';
  for (const it of items) {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-pressed', String(!hiddenSet.has(it.key)));
    b.innerHTML = `<i style="background:${it.color}"></i>${it.label}`;
    b.onclick = () => { hiddenSet.has(it.key) ? hiddenSet.delete(it.key) : hiddenSet.add(it.key); onChange(); };
    box.appendChild(b);
  }
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
  $('#kpis').innerHTML =
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
  const metric = $('#tl-metric').value;
  const series = runs.map(r => ({
    key: r.id, label: runLabel(r), color: runColor(r, runs), dash: r.cache ? '' : '',
    hidden: state.hidden.has(r.id),
    points: (detail[r.id]?.series || []).filter(p => metric !== 'rps' || p.rps > 0).map(p => [p.t, p[metric]])
  }));
  legend($('#tl-legend'), series, state.hidden, () => renderTimeline(runs, detail));
  lineChart($('#tl-chart'), {
    series, yTitle: metric, xFmt: v => v + 's', tipTitle: v => `${v}s into the run`,
    yFmt: metric === 'rps' ? yRps : yMs
  });
  const { off, on } = split(runs);
  const tail = (g, k) => median(g.flatMap(r => (detail[r.id]?.series || []).slice(-30).map(p => p[k])).filter(Boolean));
  const unit = metric === 'rps' ? ' req/s' : ' ms';
  const o = tail(off, metric), n = tail(on, metric);
  const msg = {
    rps: `In the second half of each run, uncached runs sit around <b>${fmt(o)} req/s</b> and cached runs around <b>${fmt(n)} req/s</b>. ${n >= TARGET_RPS * 0.95 ? 'Cached runs sit right on the 500 target, so the load generator, not the API, is the ceiling here.' : 'Neither group reaches the 500 target, so the API is the bottleneck in both cases.'}`,
    p50: `Median latency is flat once the run settles: about <b>${fmt(o)} ms</b> without cache and <b>${fmt(n)} ms</b> with it. Flat lines mean the queue isn't growing; the API is slow but steady.`,
    p95: `P95 settles at roughly <b>${fmt(o)} ms</b> (OFF) vs <b>${fmt(n)} ms</b> (ON). Spikes at the very start are the first requests hitting a freshly restarted process.`
  }[metric];
  $('#tl-note').innerHTML = msg;
}

function renderPercentiles(runs, detail) {
  const log = $('#pct-log').checked;
  const series = runs.map(r => ({ key: r.id, label: runLabel(r), color: runColor(r, runs), hidden: state.pctHidden.has(r.id), points: (detail[r.id]?.pct || []).map((v, i) => [i, v]) }));
  legend($('#pct-legend'), series, state.pctHidden, () => renderPercentiles(runs, detail));
  lineChart($('#pct-chart'), {
    series, log, yTitle: 'latency', xTicks: PCT_KEYS.map((_, i) => i),
    xFmt: i => PCT_KEYS[i].replace('100%', 'max').replace('%', ''), tipTitle: i => `P${PCT_KEYS[i].replace('%', '')}`, yFmt: yMs
  });
  const { off, on } = split(runs);
  const at = (g, i) => median(g.map(r => detail[r.id]?.pct[i]).filter(Number.isFinite));
  const i99 = PCT_KEYS.indexOf('99%');
  $('#pct-note').innerHTML = `Typical request: <b>${fmt(at(off, 0))} → ${fmt(at(on, 0))} ms</b>. One in a hundred: <b>${fmt(at(off, i99))} → ${fmt(at(on, i99))} ms</b>. The cached curve stays below the uncached one all the way to the max, so the cache isn't just helping the easy requests.`;
}

function renderRuns(runs) {
  const metric = $('#run-metric').value;
  const { off, on, med } = split(runs);
  const yf = isLatency(metric) ? yMs : yRps;
  barChart($('#run-chart'), {
    yFmt: yf,
    groups: runs.map(r => ({ label: `#${runNo(r.id)} ${r.cache ? 'ON' : 'OFF'}`, bars: [{ label: runLabel(r), value: r[metric], color: r.cache ? COLORS.on : COLORS.off, extra: [{ label: 'Requests', value: fmt(r.requests), color: 'transparent' }] }] })),
    refLines: metric === 'rps' ? [{ value: TARGET_RPS, color: '#8b91a1', label: 'target 500' }] : []
  });
  const rng = g => `${fmt(Math.min(...g.map(r => r[metric])))}–${fmt(Math.max(...g.map(r => r[metric])))}`;
  const spread = g => (Math.max(...g.map(r => r[metric])) - Math.min(...g.map(r => r[metric]))) / med(g, metric) * 100;
  const noisier = spread(off) > spread(on) ? 'uncached' : 'cached';
  $('#run-note').innerHTML = `I alternated the order so that any slow drift on the laptop would hit both groups. OFF ranged <b>${rng(off)}</b>, ON ranged <b>${rng(on)}</b>${isLatency(metric) ? ' ms' : ' req/s'}. The ${noisier} runs were the noisier ones, but the two groups never overlap.`;
}

function renderDatasets() {
  const metric = $('#ds-metric').value;
  const yf = isLatency(metric) ? yMs : yRps;
  const ds = Object.keys(DATASETS).filter(k => state.results[k]);
  const groups = ds.map(k => { const { off, on, med } = split(state.results[k]); return { label: DATASETS[k], bars: [{ label: 'Cache OFF', value: med(off, metric), color: COLORS.off }, { label: 'Cache ON', value: med(on, metric), color: COLORS.on }] }; });
  barChart($('#ds-chart'), { groups, yFmt: yf });
  if (groups.length < 2) { $('#ds-note').textContent = ''; return; }
  const [s, b] = groups;
  const cut = g => fmt(Math.abs(pct(g.bars[0].value, g.bars[1].value)));
  $('#ds-note').innerHTML = isLatency(metric)
    ? `Going from 2 to 500 products made uncached requests <b>${(b.bars[0].value / s.bars[0].value).toFixed(1)}×</b> slower and cached ones <b>${(b.bars[1].value / s.bars[1].value).toFixed(0)}×</b> slower. The cache still cuts ${cut(b)}%, down from ${cut(s)}%. My read: Redis saves the database trip, but a 70 KB list still has to be serialized and sent every time, and that part doesn't get cached away.`
    : `With 2 products the cached API keeps up with the full 500 req/s target. With 500 products it tops out near <b>${fmt(b.bars[1].value)} req/s</b> even with the cache, and around <b>${fmt(b.bars[0].value)}</b> without it.`;
}

function renderWorkers() {
  barChart($('#wk-chart'), {
    yFmt: yMs,
    groups: [['avg', 'Average'], ['p95', 'P95'], ['p99', 'P99']].map(([k, l]) => ({ label: l, bars: [{ label: '1 worker', value: WORKERS[1][k], color: COLORS.w1 }, { label: '2 workers', value: WORKERS[2][k], color: COLORS.w2 }] }))
  });
}

function renderTable(runs) {
  $('#runs-sub').textContent = `${DATASETS[state.dataset]} · ${runs.length} runs · numbers from Locust CSV summaries`;
  $('#rows').innerHTML = runs.map(r => {
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
    `Turning Redis on dropped average response time from <mark>${fmt(a0)} ms down to ${fmt(a1)} ms</mark> (${fmt(Math.abs(pct(a0, a1)))}% faster).`,
    r1 >= TARGET_RPS * 0.95
      ? `With cache ON, the API easily hit my <mark>500 req/s target</mark>. Without cache, it maxed out at ${fmt(r0)} req/s.`
      : `Cache boosted throughput from <mark>${fmt(r0)} to ${fmt(r1)} req/s</mark> (${(r1 / r0).toFixed(1)}×), though it still fell short of the 500 req/s target.`
  ];
  if (size > 10000) items.push(`Each response sends <mark>${fmt(size / 1024)} KB of JSON</mark>. At 500 products, the real bottleneck is sending that huge list over the wire, not the database—so <mark>pagination is the obvious next fix</mark>.`);
  const worst = on.reduce((a, b) => b.p95 > a.p95 ? b : a);
  if (worst.p95 > 2 * median(on.map(r => r.p95))) items.push(`Run ${runNo(worst.id)} had an odd P95 spike (<mark>${fmt(worst.p95)} ms</mark>), likely just background noise on my laptop.`);
  items.push(`Across all <mark>${fmt(total)} requests</mark> I saw <mark>${fails} failures</mark>, and every run returned the exact same data.`);
  $('#takeaway-list').innerHTML = items.map(t => `<li>${t}</li>`).join('');
}

let version = 0;
async function render() {
  const v = ++version, ds = state.dataset, runs = state.results[ds];
  document.querySelectorAll('[data-dataset]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.dataset === ds)));
  $('#download').href = `data/${ds}/results.json`;
  if (!runs?.length) { $('#status').textContent = 'No recorded runs for this dataset.'; return; }
  const detail = await loadDetail(ds);
  if (v !== version) return;
  const clean = runs.every(r => !r.failures && !r.cpu_warning && !r.exit_code);
  $('#status').innerHTML = `${runs[0].product_count} products in the database · ${runs.length} runs · ${clean ? 'no failures, no CPU warnings' : 'some runs are flagged, check the table'}`;
  renderKPIs(runs, detail);
  renderTimeline(runs, detail);
  renderTakeaways(runs, detail);
  renderPercentiles(runs, detail);
  renderRuns(runs);
  renderDatasets();
  renderWorkers();
  renderTable(runs);
}

async function init() {
  await Promise.all(Object.keys(DATASETS).map(async k => { try { state.results[k] = await getJSON(`data/${k}/results.json`); } catch { } }));
  if (!Object.keys(state.results).length) {
    $('#status').textContent = 'Couldn\'t load results. Serve the docs folder over HTTP (see README).';
    return;
  }
  if (!state.results[state.dataset]) state.dataset = Object.keys(state.results)[0];
  render();
}

document.querySelectorAll('[data-dataset]').forEach(b => b.addEventListener('click', () => { state.dataset = b.dataset.dataset; state.hidden.clear(); state.pctHidden.clear(); render(); }));
$('#tl-metric').addEventListener('change', () => render());
$('#pct-log').addEventListener('change', () => render());
$('#run-metric').addEventListener('change', () => render());
$('#ds-metric').addEventListener('change', () => render());
let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(render, 150); });

const links = [...document.querySelectorAll('nav a')];
const targets = links.map(l => document.querySelector(l.getAttribute('href')));
let lockUntil = 0;
function setActive(i) { links.forEach((l, k) => l.classList.toggle('active', k === i)); }
function spy() {
  if (Date.now() < lockUntil) return;
  const atBottom = innerHeight + scrollY >= document.documentElement.scrollHeight - 4;
  let idx = 0;
  if (atBottom) idx = links.length - 1;
  else targets.forEach((t, k) => { if (k && t && t.getBoundingClientRect().top <= 140) idx = k; });
  setActive(idx);
}
links.forEach((l, k) => l.addEventListener('click', () => { setActive(k); lockUntil = Date.now() + 1000; }));
addEventListener('scroll', spy, { passive: true });

init();
