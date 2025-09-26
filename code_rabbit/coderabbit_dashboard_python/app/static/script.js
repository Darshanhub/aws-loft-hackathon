let severityChart, typesChart, trendChart;

function $(sel){ return document.querySelector(sel); }

function setDateInputs(from, to){
  $('#from').value = from;
  $('#to').value = to;
}

function fmtPct(x){ return (x*100).toFixed(0) + '%'; }

async function fetchReport(){
  const from = $('#from').value;
  const to = $('#to').value;
  const mock = $('#mock').checked ? 'true' : 'false';
  const res = await fetch(`/api/report?from_=${from}&to=${to}&mock=${mock}`);
  if(!res.ok){
    const msg = await res.text();
    throw new Error(msg || 'Request failed');
  }
  return res.json();
}

function updateKPIs(totals){
  $('#kpi-prs').textContent = totals.prsReviewed.toLocaleString();
  $('#kpi-issues').textContent = totals.issues.toLocaleString();
  $('#kpi-critical').textContent = totals.critical.toLocaleString();
  $('#kpi-merge').textContent = fmtPct(totals.mergeRate);
  $('#kpi-response').textContent = totals.medianResponseHrs.toFixed(1);
}

function renderBar(canvasId, labels, data, label){
  const ctx = document.getElementById(canvasId);
  if(ctx.chart) { ctx.chart.destroy(); }
  ctx.chart = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label, data }]},
    options: { responsive: true, maintainAspectRatio: false }
  });
  return ctx.chart;
}

function renderLine(canvasId, labels, series, label){
  const ctx = document.getElementById(canvasId);
  if(ctx.chart) { ctx.chart.destroy(); }
  ctx.chart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [{ label, data: series }]},
    options: { responsive: true, maintainAspectRatio: false, tension: 0.3 }
  });
  return ctx.chart;
}

function updateTables(devs, prs){
  const devBody = $('#devTable tbody'); devBody.innerHTML = '';
  devs.forEach(d => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${d.dev}</td><td>${d.reviews}</td><td>${d.comments}</td><td>${d.avgResponseHrs.toFixed(1)}</td>`;
    devBody.appendChild(tr);
  });
  const prBody = $('#prTable tbody'); prBody.innerHTML = '';
  prs.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${p.id}</td><td>${p.title}</td><td>${p.author}</td><td>${p.repo}</td><td>${p.openedAt}</td><td>${p.status}</td><td>${p.issues}</td><td>${p.critical}</td>`;
    prBody.appendChild(tr);
  });
}

async function refresh(){
  const json = await fetchReport();
  updateKPIs(json.totals);
  const sev = json.issuesBySeverity;
  renderBar('severityChart', sev.map(s=>s.severity), sev.map(s=>s.count), 'Count');
  const types = json.suggestionsByType;
  renderBar('typesChart', types.map(s=>s.type), types.map(s=>s.count), 'Count');
  const trend = json.trendDaily;
  renderLine('trendChart', trend.map(t=>t.date), trend.map(t=>t.issues), 'Issues');
  updateTables(json.developerActivity, json.prs);
}

document.addEventListener('DOMContentLoaded', () => {
  // default dates from server-rendered values
  const urlParams = new URLSearchParams(window.location.search);
  const from = urlParams.get('from') || document.currentScript.getAttribute('data-from') || document.querySelector('meta[name=from]')?.content;
  const to = urlParams.get('to') || document.currentScript.getAttribute('data-to') || document.querySelector('meta[name=to]')?.content;

  // if server didn't inject, set last 14 days
  const end = new Date();
  const start = new Date(end.getTime() - 14*24*60*60*1000);
  setDateInputs((from||start.toISOString().slice(0,10)), (to||end.toISOString().slice(0,10)));

  $('#refresh').addEventListener('click', () => {
    refresh().catch(e => alert(e));
  });
  refresh().catch(e => alert(e));
});
