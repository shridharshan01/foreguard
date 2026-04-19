// ── API URL ───────────────────────────────────────────────────────────────────
const API_URL = window.location.origin;
let currentResult = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const fileInput      = document.getElementById('fileInput');
const uploadBtn      = document.getElementById('uploadBtn');
const dropZone       = document.getElementById('dropZone');
const analyzeBtn     = document.getElementById('analyzeBtn');
const resetBtn       = document.getElementById('resetBtn');
const fileInfo       = document.getElementById('fileInfo');
const loadingOverlay = document.getElementById('loadingOverlay');
const resultsSection = document.getElementById('resultsSection');
const viewReportBtn  = document.getElementById('viewReportBtn');
const downloadBtn    = document.getElementById('downloadReportBtn');
const reportModal    = document.getElementById('reportModal');
const modalBody      = document.getElementById('modalBody');
const modalClose     = document.getElementById('modalClose');
const langSelect     = document.getElementById('langSelect');

let selectedFile = null;

// ── File handling ─────────────────────────────────────────────────────────────
uploadBtn.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('click', e => { if (e.target !== uploadBtn) fileInput.click(); });
dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', e => { if (e.target.files?.[0]) handleFile(e.target.files[0]); });

function handleFile(file) {
  const allowed = ['image/png','image/jpeg','image/jpg','image/bmp',
                   'image/tiff','image/webp','application/pdf'];
  if (!allowed.includes(file.type)) { showToast('Unsupported file type.', 'error'); return; }
  if (file.size > 20 * 1024 * 1024) { showToast('File exceeds 20 MB limit.', 'error'); return; }

  selectedFile = file;
  fileInfo.textContent = `${file.name}  (${fmtSize(file.size)})`;
  analyzeBtn.disabled = false;

  if (file.type.startsWith('image/')) {
    const r = new FileReader();
    r.onload = e => setImg('originalPreview', e.target.result);
    r.readAsDataURL(file);
  } else if (file.type === 'application/pdf') {
    // Show a PDF placeholder
    const el = document.getElementById('originalPreview');
    if (el) { el.src = ''; el.classList.remove('loaded'); }
    const frame = document.getElementById('origFrame');
    const empty = frame?.querySelector('.vis-empty');
    if (empty) { empty.style.display = ''; empty.textContent = '📄 PDF — preview after analysis'; }
  }
}

resetBtn.addEventListener('click', reset);
function reset() {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.textContent = 'No file selected';
  analyzeBtn.disabled = true;
  resultsSection.style.display = 'none';
  currentResult = null;
  ['originalPreview','annotatedPreview','heatmapPreview'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.src = ''; el.classList.remove('loaded'); }
  });
  document.getElementById('verdictBanner').className = 'verdict-banner';
}

// ── Analysis ──────────────────────────────────────────────────────────────────
analyzeBtn.addEventListener('click', runAnalysis);

async function runAnalysis() {
  if (!selectedFile) return;
  loadingOverlay.style.display = 'flex';
  const stopAnim = animateLoadingSteps();

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('languages', langSelect?.value || 'en');

  try {
    const res = await fetch(`${API_URL}/detect`, { method: 'POST', body: fd });
    if (!res.ok) {
      const e = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(e.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    currentResult = data;
    stopAnim();
    loadingOverlay.style.display = 'none';
    displayResults(data);
    resultsSection.style.display = 'block';
    setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth' }), 80);
  } catch (err) {
    stopAnim();
    loadingOverlay.style.display = 'none';
    showToast(`Analysis failed: ${err.message}`, 'error');
  }
}

function animateLoadingSteps() {
  const steps = [1,2,3,4,5,6];
  const msgs  = ['Uploading document…','Running ELA analysis…','Checking fonts & layout…',
                 'Scanning EXIF metadata…','OCR text analysis…','Deep learning ensemble…'];
  steps.forEach(i => {
    const el = document.getElementById(`lstep${i}`);
    if (el) { el.className = 'ld-step'; el.querySelector('.step-icon').textContent = '◻'; }
  });
  let idx = 0, stopped = false;
  const iv = setInterval(() => {
    if (stopped || idx >= steps.length) { clearInterval(iv); return; }
    if (idx > 0) {
      const p = document.getElementById(`lstep${steps[idx-1]}`);
      if (p) { p.className = 'ld-step done'; p.querySelector('.step-icon').textContent = '✓'; }
    }
    const el = document.getElementById(`lstep${steps[idx]}`);
    if (el) el.className = 'ld-step active';
    const msg = document.getElementById('loadingMsg');
    if (msg) msg.textContent = msgs[idx] || 'Processing…';
    idx++;
  }, 1000);
  return () => {
    stopped = true; clearInterval(iv);
    steps.forEach(i => {
      const el = document.getElementById(`lstep${i}`);
      if (el && !el.classList.contains('done')) {
        el.className = 'ld-step done';
        el.querySelector('.step-icon').textContent = '✓';
      }
    });
  };
}

// ── Display results ───────────────────────────────────────────────────────────
function displayResults(r) {
  const conf     = parseFloat(r.overall_confidence);
  const isForged = r.overall_verdict === 'FORGED';
  const risk     = r.overall_risk || 'CLEAR';
  const pages    = r.total_pages || 1;

  // Verdict banner
  const banner = document.getElementById('verdictBanner');
  banner.className = `verdict-banner ${isForged ? 'forged' : ''}`;
  document.getElementById('verdictText').textContent = r.verdict || r.overall_verdict;
  document.getElementById('verdictDetail').textContent = isForged
    ? `Document shows signs of tampering across ${pages} page${pages>1?'s':''}. Review suspicious regions below.`
    : `No significant forgery indicators detected across ${pages} page${pages>1?'s':''}.`;

  // Tampering tags
  const tagsEl = document.getElementById('tamperingTags');
  tagsEl.innerHTML = '';
  (r.tampering_types || []).forEach(t => {
    const s = document.createElement('span');
    s.className = 'tamp-tag';
    s.textContent = t.replace(/_/g,' ');
    tagsEl.appendChild(s);
  });

  // Confidence ring
  const circle = document.getElementById('confCircle');
  const offset = 314 - (conf / 100) * 314;
  circle.style.transition = 'stroke-dashoffset 1s ease';
  setTimeout(() => { circle.style.strokeDashoffset = offset; }, 100);
  circle.style.stroke = isForged ? 'var(--red)' : 'var(--cyan)';
  animateCounter('confNum', 0, Math.round(conf), 1000);

  // Risk + meta
  const rb = document.getElementById('riskBadge');
  rb.textContent = risk; rb.className = `risk-display risk-${risk}`;
  const pt = document.getElementById('processingTime');
  if (pt) pt.textContent = `⏱ ${r.processing_time_seconds}s`;
  const dn = document.getElementById('docName');
  if (dn) dn.textContent = `📄 ${r.document_name}`;

  // ── Multi-page strip ──────────────────────────────────────────────────────
  renderPageStrip(r);

  // Images (composite across all pages)
  if (r.original_image)  setImg('originalPreview',  r.original_image);
  if (r.annotated_image) setImg('annotatedPreview', r.annotated_image);
  if (r.heatmap_image)   setImg('heatmapPreview',   r.heatmap_image);

  // Detectors
  const grid = document.getElementById('detectorsGrid');
  grid.innerHTML = '';
  (r.detectors || []).forEach(d => grid.appendChild(buildDetCard(d)));

  // Suspicious regions (sorted by severity)
  const list   = document.getElementById('suspiciousRegionsList');
  list.innerHTML = '';
  const allReg = (r.detectors || []).flatMap(d =>
    (d.suspicious_regions || []).map(reg => ({...reg, _det: d.name || d.detector_name || ''}))
  );
  const rc = document.getElementById('regionCount');
  if (rc) rc.textContent = allReg.length ? `(${allReg.length})` : '';
  if (!allReg.length) {
    list.innerHTML = '<div class="regions-empty">✓ No suspicious regions detected</div>';
  } else {
    allReg.sort((a,b) => parseFloat(b.severity) - parseFloat(a.severity))
          .forEach((reg,i) => list.appendChild(buildRegion(reg,i)));
  }

  // Summary
  const suspicious = (r.detectors || []).filter(d => d.is_forged).length;
  const langStr    = (r.languages_detected || []).join(', ');
  document.getElementById('summaryStats').innerHTML = `
    <strong>${suspicious} of ${(r.detectors||[]).length}</strong> detectors flagged suspicious<br>
    <strong>${allReg.length}</strong> suspicious region${allReg.length!==1?'s':''} found<br>
    <strong>${pages}</strong> PDF page${pages>1?'s':''} analysed<br>
    <strong>Confidence:</strong> <em>${conf.toFixed(1)}%</em><br>
    ${langStr ? `<strong>Languages:</strong> ${langStr}<br>` : ''}
    ${r.confidence_reason ? `<strong>Reason:</strong> ${esc(r.confidence_reason)}<br>` : ''}
    <br><strong>Recommendation:</strong><br>${getRecommendation(r)}
    ${r.extracted_text
      ? `<br><br><details>
           <summary style="cursor:pointer;color:var(--cyan);font-size:.8rem">Show extracted text ▸</summary>
           <pre style="font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--text-3);
                       margin-top:.5rem;white-space:pre-wrap;max-height:200px;overflow-y:auto"
           >${esc(r.extracted_text.slice(0,1200))}</pre></details>`
      : ''}
  `;
}

// ── Multi-page strip ──────────────────────────────────────────────────────────
function renderPageStrip(r) {
  const strip = document.getElementById('pageStrip');
  if (!strip) return;
  const pages = r.total_pages || 1;

  if (pages <= 1) {
    strip.style.display = 'none';
    return;
  }
  strip.style.display = 'block';

  const summaries = r.page_summaries || [];
  const previews  = r.page_previews  || [];

  strip.innerHTML = `
    <div class="page-strip-title mono">PDF PAGES (${pages} total)</div>
    <div class="page-strip-row" id="pageStripRow"></div>
  `;
  const row = document.getElementById('pageStripRow');

  summaries.forEach(ps => {
    const preview = previews.find(p => p.page === ps.page);
    const card = document.createElement('div');
    card.className = `page-card ${ps.is_forged ? 'page-card-bad' : 'page-card-ok'}`;
    card.innerHTML = `
      <div class="page-card-thumb">
        ${preview ? `<img src="${preview.original}" alt="Page ${ps.page}">` : '<div class="page-thumb-empty">PDF</div>'}
      </div>
      <div class="page-card-label mono">PG ${ps.page}</div>
      <div class="page-card-conf ${ps.is_forged ? 'conf-bad' : 'conf-ok'}">${ps.confidence}%</div>
      <div class="page-card-status">${ps.is_forged ? '⚠' : '✓'} ${ps.region_count} region${ps.region_count!==1?'s':''}</div>
    `;
    // Click to swap the main "original" preview to this page
    card.addEventListener('click', () => {
      if (preview) setImg('originalPreview', preview.original);
      document.querySelectorAll('.page-card').forEach(c => c.classList.remove('page-card-active'));
      card.classList.add('page-card-active');
    });
    row.appendChild(card);
  });
}

// ── Card builders ─────────────────────────────────────────────────────────────
function buildDetCard(d) {
  const div    = document.createElement('div');
  const isOk   = !d.is_forged;
  const confRaw = typeof d.confidence === 'number'
    ? (d.confidence > 1 ? d.confidence : d.confidence * 100) : 0;
  const fillCol = isOk ? 'var(--green)' : 'var(--red)';
  const name    = d.detector_name || d.name || '';
  div.className = `det-card ${isOk ? 'det-ok' : 'det-bad'}`;
  const uid = `det-${Math.random().toString(36).slice(2,8)}`;

  div.innerHTML = `
    <div class="det-card-top">
      <div class="det-card-name">${esc(name)}</div>
      <span class="det-chip ${isOk ? 'chip-ok' : 'chip-bad'}">${isOk ? '✓ CLEAR' : '⚠ FLAGGED'}</span>
    </div>
    <div class="det-bar-wrap">
      <div class="det-bar">
        <div class="det-bar-fill" style="width:${Math.min(confRaw,100).toFixed(1)}%;background:${fillCol}"></div>
      </div>
      <div class="det-bar-pct">${confRaw.toFixed(1)}% confidence</div>
    </div>
    ${d.plain_english ? `<div class="det-plain">${esc(d.plain_english)}</div>` : ''}
    <button class="det-detail-toggle" onclick="
      const el=document.getElementById('${uid}');
      el.classList.toggle('open');
      this.textContent=el.classList.contains('open')?'▲ Hide details':'▼ Show details';
    ">▼ Show details</button>
    <div class="det-detail-body" id="${uid}">${esc(JSON.stringify(d.details,null,2))}</div>
  `;
  return div;
}

function buildRegion(r, idx) {
  const div = document.createElement('div');
  const sev = parseFloat(r.severity || 0) * 100;
  const cls = sev >= 70 ? 'reg-high' : sev >= 40 ? 'reg-medium' : 'reg-low';
  div.className = `region-item ${cls}`;
  div.innerHTML = `
    <div class="reg-type">${esc(r.type || 'unknown')}</div>
    <div class="reg-meta">
      <span>Severity ${sev.toFixed(0)}%</span>
      <span>${esc(r._det || '')}</span>
      ${r.page ? `<span>Page ${r.page}</span>` : ''}
      ${r.bbox ? `<span>bbox [${r.bbox.join(', ')}]</span>` : ''}
    </div>
    ${r.details ? `<div class="reg-detail">${esc(String(r.details))}</div>` : ''}
  `;
  return div;
}

// ── Report modal ──────────────────────────────────────────────────────────────
viewReportBtn?.addEventListener('click', () => {
  if (!currentResult) return;
  modalBody.innerHTML = buildReportHTML(currentResult);
  reportModal.style.display = 'flex';
});
downloadBtn?.addEventListener('click', () => {
  if (!currentResult) return;
  const blob = new Blob([buildReportHTML(currentResult)], { type: 'text/html' });
  const name = (currentResult.document_name || 'report').replace(/[^a-z0-9]/gi,'_');
  const a = Object.assign(document.createElement('a'),
    { href: URL.createObjectURL(blob), download: `foreguard_${name}.html` });
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  showToast('Report downloaded.', 'success');
});
modalClose?.addEventListener('click', () => (reportModal.style.display='none'));
window.addEventListener('click', e => { if (e.target===reportModal) reportModal.style.display='none'; });

function buildReportHTML(r) {
  const conf     = parseFloat(r.overall_confidence);
  const isForged = r.overall_verdict === 'FORGED';
  const dets     = r.detectors || [];
  const pages    = r.total_pages || 1;

  const rows = dets.map(d => {
    const c = typeof d.confidence === 'number' ? (d.confidence > 1 ? d.confidence : d.confidence*100) : 0;
    return `<tr>
      <td><strong>${esc(d.detector_name||d.name)}</strong><br>
          <small style="color:#94a3b8">${esc(d.plain_english||'')}</small></td>
      <td style="color:${d.is_forged?'#f56565':'#48bb78'}">${d.is_forged?'⚠ Flagged':'✓ Clear'}</td>
      <td>${c.toFixed(1)}%</td>
      <td>${(d.suspicious_regions||[]).length}</td></tr>`;
  }).join('');

  const allReg = dets.flatMap(d =>
    (d.suspicious_regions||[]).map(reg => ({...reg, _det: d.detector_name||d.name||''}))
  ).sort((a,b) => b.severity - a.severity);

  const regRows = allReg.length
    ? allReg.map(reg => {
        const sev = (parseFloat(reg.severity||0)*100).toFixed(0);
        const col = sev>=70?'#f56565':sev>=40?'#ed8936':'#48bb78';
        return `<tr>
          <td>${esc(reg._det)}</td>
          <td>${esc(reg.type||'')}</td>
          <td style="color:${col};font-weight:600">${sev}%</td>
          <td>${reg.page?`Pg ${reg.page}`:''}</td>
          <td style="font-size:.78em">${(reg.bbox||[]).join(', ')}</td>
          <td style="font-size:.78em">${esc(String(reg.details||''))}</td></tr>`;
      }).join('')
    : `<tr><td colspan="6" style="color:#48bb78;text-align:center">No suspicious regions</td></tr>`;

  const pageRows = (r.page_summaries||[]).map(ps =>
    `<tr>
      <td>Page ${ps.page}</td>
      <td style="color:${ps.is_forged?'#f56565':'#48bb78'}">${ps.is_forged?'⚠ Suspicious':'✓ Clear'}</td>
      <td>${ps.confidence}%</td>
      <td>${ps.region_count} region${ps.region_count!==1?'s':''}</td>
    </tr>`
  ).join('');

  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>ForeGuard v3 Report — ${esc(r.document_name||'')}</title>
<style>
  body{background:#080c14;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:2rem;line-height:1.6;margin:0}
  .box{max-width:960px;margin:0 auto;background:#141c2e;border:1px solid rgba(0,229,255,.12);border-radius:12px;padding:2rem}
  h1{font-size:1.5rem;color:#fff;margin-bottom:.25rem} h2{font-size:1.05rem;color:#e2e8f0;margin:1.5rem 0 .5rem}
  .meta{font-size:.8rem;color:#64748b;margin-bottom:1.5rem}
  .verdict{padding:1rem 1.5rem;border-radius:8px;margin:1.5rem 0;
    background:${isForged?'rgba(245,101,101,.08)':'rgba(72,187,120,.08)'};
    border-left:4px solid ${isForged?'#f56565':'#48bb78'}}
  .verdict h2{color:${isForged?'#f56565':'#48bb78'};margin:0 0 .25rem;font-size:1.15rem}
  table{width:100%;border-collapse:collapse;margin:1rem 0}
  th{background:#0d1220;color:#94a3b8;padding:.75rem 1rem;text-align:left;font-size:.78rem;letter-spacing:.08em}
  td{padding:.65rem 1rem;border-bottom:1px solid rgba(255,255,255,.05);font-size:.84rem;vertical-align:top}
  pre{background:#0d1220;padding:.75rem;border-radius:6px;font-size:.72rem;white-space:pre-wrap;
      color:#64748b;max-height:200px;overflow-y:auto;margin-top:.5rem}
  .tamp{display:inline-block;background:rgba(245,101,101,.1);color:#f56565;
    border:1px solid rgba(245,101,101,.3);border-radius:4px;padding:.15rem .5rem;font-size:.72rem;margin:.2rem}
  footer{color:#334155;font-size:.72rem;text-align:center;margin-top:2rem}
</style></head><body><div class="box">
  <h1>🛡️ ForeGuard v3 Forensic Report</h1>
  <div class="meta">Document: <strong>${esc(r.document_name||'')}</strong> &nbsp;·&nbsp;
    ${new Date().toLocaleString()} &nbsp;·&nbsp; ${r.processing_time_seconds||0}s &nbsp;·&nbsp;
    ${pages} page${pages>1?'s':''} analysed</div>
  <div class="verdict">
    <h2>${esc(r.verdict||r.overall_verdict)}</h2>
    <div>Confidence: <strong>${conf.toFixed(1)}%</strong> &nbsp;|&nbsp; Risk: <strong>${r.overall_risk}</strong></div>
    ${(r.tampering_types||[]).length?`<div style="margin-top:.5rem">${r.tampering_types.map(t=>`<span class="tamp">${t.replace(/_/g,' ')}</span>`).join('')}</div>`:''}
  </div>
  ${pages>1?`<h2>Per-Page Summary</h2>
  <table><tr><th>PAGE</th><th>STATUS</th><th>CONFIDENCE</th><th>REGIONS</th></tr>${pageRows}</table>`:''}
  <h2>Detector Results</h2>
  <table><tr><th>DETECTOR / EXPLANATION</th><th>STATUS</th><th>CONFIDENCE</th><th>REGIONS</th></tr>${rows}</table>
  <h2>Suspicious Regions</h2>
  <table><tr><th>DETECTOR</th><th>TYPE</th><th>SEVERITY</th><th>PAGE</th><th>LOCATION</th><th>DETAILS</th></tr>${regRows}</table>
  ${r.extracted_text?`<h2>Extracted Text</h2>
    ${(r.languages_detected||[]).length?`<p style="font-size:.78rem;color:#64748b">Languages: ${r.languages_detected.join(', ')}</p>`:''}
    <pre>${esc(r.extracted_text.slice(0,3000))}</pre>`:''}
  <footer>Generated by ForeGuard AI Forensics System v3 &bull; ${new Date().getFullYear()}</footer>
</div></body></html>`;
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function getRecommendation(r) {
  const risk = r.overall_risk;
  if (risk==='HIGH')   return '🚨 <strong style="color:var(--red)">HIGH RISK</strong> — Reject and investigate immediately.';
  if (risk==='MEDIUM') return '⚠️ <strong style="color:var(--orange)">MEDIUM RISK</strong> — Manual verification strongly recommended.';
  if (risk==='LOW')    return '🔎 <strong style="color:var(--yellow)">LOW RISK</strong> — Minor anomalies; verify critical fields.';
  return '✅ <strong style="color:var(--green)">CLEAR</strong> — Document appears genuine.';
}

function setImg(id, src) {
  const el = document.getElementById(id);
  if (!el || !src) return;
  el.src = src; el.classList.add('loaded');
  const empty = el.closest('.vis-frame')?.querySelector('.vis-empty');
  if (empty) empty.style.display = 'none';
}

function animateCounter(id, from, to, duration) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = performance.now();
  const tick = now => {
    const p = Math.min((now - start) / duration, 1);
    el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1-p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function fmtSize(b) {
  if (!b) return '0 B';
  const k=1024, s=['B','KB','MB','GB'], i=Math.floor(Math.log(b)/Math.log(k));
  return `${(b/k**i).toFixed(1)} ${s[i]}`;
}

function esc(str) {
  return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showToast(msg, type='info') {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`; t.textContent = msg;
  c.appendChild(t); setTimeout(() => t.remove(), 4500);
}