// ── API URL (auto-detect) ────────────────────────────────────────────────────
const API_URL = window.location.origin;

let currentResult = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
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

// ── File selection ────────────────────────────────────────────────────────────
uploadBtn.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('click', e => {
  if (e.target !== uploadBtn) fileInput.click();
});

dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});
fileInput.addEventListener('change', e => {
  if (e.target.files?.[0]) handleFile(e.target.files[0]);
});

function handleFile(file) {
  const allowed = [
    'image/png', 'image/jpeg', 'image/jpg', 'image/bmp',
    'image/tiff', 'image/webp', 'application/pdf',
  ];
  if (!allowed.includes(file.type)) {
    showToast('Unsupported file type.', 'error'); return;
  }
  if (file.size > 20 * 1024 * 1024) {
    showToast('File exceeds 20 MB limit.', 'error'); return;
  }

  selectedFile = file;
  fileInfo.textContent = `${file.name}  (${fmtSize(file.size)})`;
  analyzeBtn.disabled = false;

  // Show preview for images immediately (before analysis)
  if (file.type.startsWith('image/')) {
    const r = new FileReader();
    r.onload = e => setImg('originalPreview', e.target.result);
    r.readAsDataURL(file);
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
  ['originalPreview', 'annotatedPreview', 'heatmapPreview'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.src = ''; el.classList.remove('loaded'); }
  });
  // Reset verdict banner
  const banner = document.getElementById('verdictBanner');
  if (banner) banner.className = 'verdict-banner';
}

// ── Analyse ───────────────────────────────────────────────────────────────────
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

// ── Loading step animation ────────────────────────────────────────────────────
function animateLoadingSteps() {
  const steps = [1, 2, 3, 4, 5, 6];
  const msgs  = [
    'Uploading document…',
    'Running ELA analysis…',
    'Checking fonts & layout…',
    'Scanning EXIF metadata…',
    'OCR text analysis…',
    'Deep learning ensemble…',
  ];

  // Reset all steps
  steps.forEach(i => {
    const el = document.getElementById(`lstep${i}`);
    if (el) { el.className = 'ld-step'; el.querySelector('.step-icon').textContent = '◻'; }
  });

  let idx = 0;
  let stopped = false;

  const interval = setInterval(() => {
    if (stopped || idx >= steps.length) { clearInterval(interval); return; }

    if (idx > 0) {
      const prev = document.getElementById(`lstep${steps[idx - 1]}`);
      if (prev) { prev.className = 'ld-step done'; prev.querySelector('.step-icon').textContent = '✓'; }
    }

    const el = document.getElementById(`lstep${steps[idx]}`);
    if (el) el.className = 'ld-step active';

    const msg = document.getElementById('loadingMsg');
    if (msg) msg.textContent = msgs[idx] || 'Processing…';

    idx++;
  }, 1000);

  // Return stop function
  return () => {
    stopped = true;
    clearInterval(interval);
    // Mark remaining done
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
  const conf     = parseFloat(r.overall_confidence);   // 0–100
  const isForged = r.overall_verdict === 'FORGED';
  const risk     = r.overall_risk || 'CLEAR';

  // ── Verdict banner ──
  const banner = document.getElementById('verdictBanner');
  banner.className = `verdict-banner ${isForged ? 'forged' : ''}`;

  document.getElementById('verdictText').textContent = r.verdict || r.overall_verdict;
  document.getElementById('verdictDetail').textContent = isForged
    ? 'Document shows signs of tampering. Review suspicious regions below.'
    : 'No significant forgery indicators detected across all analysis layers.';

  // Tampering type tags
  const tagsEl = document.getElementById('tamperingTags');
  tagsEl.innerHTML = '';
  (r.tampering_types || []).forEach(t => {
    const span = document.createElement('span');
    span.className = 'tamp-tag';
    span.textContent = t.replace(/_/g, ' ');
    tagsEl.appendChild(span);
  });

  // ── Confidence ring animation ──
  const circle       = document.getElementById('confCircle');
  const circumference = 314;
  const offset       = circumference - (conf / 100) * circumference;
  circle.style.transition = 'stroke-dashoffset 1s ease';
  setTimeout(() => { circle.style.strokeDashoffset = offset; }, 100);
  circle.style.stroke = isForged ? 'var(--red)' : 'var(--cyan)';

  // Animated counter
  animateCounter('confNum', 0, Math.round(conf), 1000);

  // ── Risk badge ──
  const rb = document.getElementById('riskBadge');
  rb.textContent = risk;
  rb.className   = `risk-display risk-${risk}`;

  // ── Meta ──
  const pt = document.getElementById('processingTime');
  if (pt && r.processing_time_seconds != null)
    pt.textContent = `⏱ ${r.processing_time_seconds}s`;

  const dn = document.getElementById('docName');
  if (dn && r.document_name)
    dn.textContent = `📄 ${r.document_name}`;

  // ── Images ──
  // original_image is now sent by the backend (v2)
  if (r.original_image)  setImg('originalPreview',  r.original_image);
  if (r.annotated_image) setImg('annotatedPreview', r.annotated_image);
  if (r.heatmap_image)   setImg('heatmapPreview',   r.heatmap_image);

  // ── Detector cards ──
  const grid = document.getElementById('detectorsGrid');
  grid.innerHTML = '';
  const detectors = r.detectors || r.detection_results || [];
  detectors.forEach(d => grid.appendChild(buildDetCard(d)));

  // ── Suspicious regions ──
  const list   = document.getElementById('suspiciousRegionsList');
  list.innerHTML = '';
  const allReg = detectors.flatMap(d =>
    (d.suspicious_regions || []).map(reg => ({
      ...reg,
      _det: d.name || d.detector_name || '',
    }))
  );

  const rc = document.getElementById('regionCount');
  if (rc) rc.textContent = allReg.length ? `(${allReg.length})` : '';

  if (!allReg.length) {
    list.innerHTML = '<div class="regions-empty">✓ No suspicious regions detected</div>';
  } else {
    // Sort by severity descending
    allReg
      .sort((a, b) => parseFloat(b.severity) - parseFloat(a.severity))
      .forEach((reg, i) => list.appendChild(buildRegion(reg, i)));
  }

  // ── Summary ──
  const suspicious = detectors.filter(d => d.is_forged).length;
  const langStr    = (r.languages_detected || []).join(', ');

  document.getElementById('summaryStats').innerHTML = `
    <strong>${suspicious} of ${detectors.length}</strong> detectors flagged suspicious<br>
    <strong>${allReg.length}</strong> total suspicious region${allReg.length !== 1 ? 's' : ''}<br>
    <strong>Confidence:</strong> <em>${conf.toFixed(1)}%</em><br>
    ${langStr ? `<strong>Languages:</strong> ${langStr}<br>` : ''}
    ${r.confidence_reason ? `<strong>Reason:</strong> ${esc(r.confidence_reason)}<br>` : ''}
    <br><strong>Recommendation:</strong><br>${getRecommendation(r)}
    ${r.extracted_text
      ? `<br><br><details>
           <summary style="cursor:pointer;color:var(--cyan);font-size:.8rem">Show extracted text ▸</summary>
           <pre style="font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--text-3);
                       margin-top:.5rem;white-space:pre-wrap;max-height:200px;overflow-y:auto"
           >${esc(r.extracted_text.slice(0, 1200))}</pre>
         </details>`
      : ''}
  `;
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

  const uid = `det-${Math.random().toString(36).slice(2, 8)}`;

  div.innerHTML = `
    <div class="det-card-top">
      <div class="det-card-name">${esc(name)}</div>
      <span class="det-chip ${isOk ? 'chip-ok' : 'chip-bad'}">${isOk ? '✓ CLEAR' : '⚠ FLAGGED'}</span>
    </div>
    <div class="det-bar-wrap">
      <div class="det-bar">
        <div class="det-bar-fill" style="width:${Math.min(confRaw, 100).toFixed(1)}%;background:${fillCol}"></div>
      </div>
      <div class="det-bar-pct">${confRaw.toFixed(1)}% confidence</div>
    </div>
    ${d.plain_english ? `<div class="det-plain">${esc(d.plain_english)}</div>` : ''}
    <button class="det-detail-toggle" onclick="
      const el = document.getElementById('${uid}');
      el.classList.toggle('open');
      this.textContent = el.classList.contains('open') ? '▲ Hide details' : '▼ Show details';
    ">▼ Show details</button>
    <div class="det-detail-body" id="${uid}">${esc(JSON.stringify(d.details, null, 2))}</div>
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
  const html = buildReportHTML(currentResult);
  const blob = new Blob([html], { type: 'text/html' });
  const name = (currentResult.document_name || 'report').replace(/[^a-z0-9]/gi, '_');
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(blob),
    download: `foreguard_${name}.html`,
  });
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast('Report downloaded.', 'success');
});

modalClose?.addEventListener('click', () => (reportModal.style.display = 'none'));
window.addEventListener('click', e => {
  if (e.target === reportModal) reportModal.style.display = 'none';
});

function buildReportHTML(r) {
  const conf     = parseFloat(r.overall_confidence);
  const isForged = r.overall_verdict === 'FORGED';
  const dets     = r.detectors || r.detection_results || [];

  const rows = dets.map(d => {
    const c = typeof d.confidence === 'number'
      ? (d.confidence > 1 ? d.confidence : d.confidence * 100) : 0;
    const regCount = (d.suspicious_regions || []).length;
    return `<tr>
      <td>
        <strong>${esc(d.detector_name || d.name)}</strong><br>
        <small style="color:#94a3b8">${esc(d.plain_english || '')}</small>
      </td>
      <td style="color:${d.is_forged ? '#f56565' : '#48bb78'}">
        ${d.is_forged ? '⚠ Flagged' : '✓ Clear'}
      </td>
      <td>${c.toFixed(1)}%</td>
      <td>${regCount}</td>
    </tr>`;
  }).join('');

  // All suspicious regions
  const allReg = dets.flatMap(d =>
    (d.suspicious_regions || []).map(reg => ({
      ...reg, _det: d.detector_name || d.name || '',
    }))
  );
  const regRows = allReg.length
    ? allReg.sort((a, b) => b.severity - a.severity).map(reg => {
        const sev = (parseFloat(reg.severity || 0) * 100).toFixed(0);
        const col = sev >= 70 ? '#f56565' : sev >= 40 ? '#ed8936' : '#48bb78';
        return `<tr>
          <td>${esc(reg._det)}</td>
          <td>${esc(reg.type || '')}</td>
          <td style="color:${col};font-weight:600">${sev}%</td>
          <td style="font-size:.78em">${(reg.bbox || []).join(', ')}</td>
          <td style="font-size:.78em">${esc(String(reg.details || ''))}</td>
        </tr>`;
      }).join('')
    : `<tr><td colspan="5" style="color:#48bb78;text-align:center">No suspicious regions</td></tr>`;

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>ForeGuard Report — ${esc(r.document_name || '')}</title>
<style>
  body{background:#080c14;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:2rem;line-height:1.6;margin:0}
  .box{max-width:900px;margin:0 auto;background:#141c2e;border:1px solid rgba(0,229,255,.12);border-radius:12px;padding:2rem}
  h1{font-size:1.5rem;color:#fff;margin-bottom:.25rem}
  h2{font-size:1.05rem;color:#e2e8f0;margin:1.5rem 0 .5rem}
  .meta{font-size:.8rem;color:#64748b;margin-bottom:1.5rem}
  .verdict{padding:1rem 1.5rem;border-radius:8px;margin:1.5rem 0;
    background:${isForged ? 'rgba(245,101,101,.08)' : 'rgba(72,187,120,.08)'};
    border-left:4px solid ${isForged ? '#f56565' : '#48bb78'}}
  .verdict h2{color:${isForged ? '#f56565' : '#48bb78'};margin:0 0 .25rem;font-size:1.15rem}
  table{width:100%;border-collapse:collapse;margin:1rem 0}
  th{background:#0d1220;color:#94a3b8;padding:.75rem 1rem;text-align:left;font-size:.78rem;letter-spacing:.08em}
  td{padding:.65rem 1rem;border-bottom:1px solid rgba(255,255,255,.05);font-size:.84rem;vertical-align:top}
  pre{background:#0d1220;padding:.75rem;border-radius:6px;font-size:.72rem;white-space:pre-wrap;
      color:#64748b;max-height:160px;overflow-y:auto;margin-top:.5rem}
  .tamp{display:inline-block;background:rgba(245,101,101,.1);color:#f56565;
    border:1px solid rgba(245,101,101,.3);border-radius:4px;
    padding:.15rem .5rem;font-size:.72rem;margin:.2rem}
  footer{color:#334155;font-size:.72rem;text-align:center;margin-top:2rem}
</style></head>
<body><div class="box">
  <h1>🛡️ ForeGuard Forensic Report</h1>
  <div class="meta">
    Document: <strong>${esc(r.document_name || '')}</strong> &nbsp;·&nbsp;
    ${new Date().toLocaleString()} &nbsp;·&nbsp;
    ${r.processing_time_seconds || 0}s processing
  </div>
  <div class="verdict">
    <h2>${esc(r.verdict || r.overall_verdict)}</h2>
    <div>
      Confidence: <strong>${conf.toFixed(1)}%</strong> &nbsp;|&nbsp;
      Risk: <strong>${r.overall_risk}</strong>
    </div>
    ${(r.tampering_types || []).length
      ? `<div style="margin-top:.5rem">${r.tampering_types.map(t => `<span class="tamp">${t.replace(/_/g, ' ')}</span>`).join('')}</div>`
      : ''}
  </div>
  <h2>Detector Results</h2>
  <table>
    <tr><th>DETECTOR / EXPLANATION</th><th>STATUS</th><th>CONFIDENCE</th><th>REGIONS</th></tr>
    ${rows}
  </table>
  <h2>Suspicious Regions</h2>
  <table>
    <tr><th>DETECTOR</th><th>TYPE</th><th>SEVERITY</th><th>LOCATION</th><th>DETAILS</th></tr>
    ${regRows}
  </table>
  ${r.extracted_text
    ? `<h2>Extracted Text</h2>
       ${r.languages_detected?.length ? `<p style="font-size:.78rem;color:#64748b">Languages: ${r.languages_detected.join(', ')}</p>` : ''}
       <pre>${esc(r.extracted_text.slice(0, 2000))}</pre>`
    : ''}
  <footer>Generated by ForeGuard AI Forensics System &bull; ${new Date().getFullYear()}</footer>
</div></body></html>`;
}

// ── Recommendation text ───────────────────────────────────────────────────────
function getRecommendation(r) {
  const risk = r.overall_risk;
  if (risk === 'HIGH')
    return '🚨 <strong style="color:var(--red)">HIGH RISK</strong> — Reject document and investigate immediately.';
  if (risk === 'MEDIUM')
    return '⚠️ <strong style="color:var(--orange)">MEDIUM RISK</strong> — Manual verification strongly recommended.';
  if (risk === 'LOW')
    return '🔎 <strong style="color:var(--yellow)">LOW RISK</strong> — Minor anomalies; verify critical fields manually.';
  return '✅ <strong style="color:var(--green)">CLEAR</strong> — Document appears genuine. No action required.';
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function setImg(id, src) {
  const el = document.getElementById(id);
  if (!el || !src) return;
  el.src = src;
  el.classList.add('loaded');
  // Hide the "Awaiting" placeholder text inside the same frame
  const frame = el.closest('.vis-frame');
  if (frame) {
    const empty = frame.querySelector('.vis-empty');
    if (empty) empty.style.display = 'none';
  }
}

function animateCounter(id, from, to, duration) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = performance.now();
  const tick = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    el.textContent = Math.round(from + (to - from) * easeOut(progress));
    if (progress < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

function fmtSize(b) {
  if (b === 0) return '0 B';
  const k = 1024, s = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(b) / Math.log(k));
  return `${(b / k ** i).toFixed(1)} ${s[i]}`;
}

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showToast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4500);
}