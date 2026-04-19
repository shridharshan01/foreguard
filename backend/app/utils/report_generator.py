from datetime import datetime


class ReportGenerator:

    @staticmethod
    def generate_html_report(report_data: dict, heatmap_path: str = None) -> str:
        raw_conf = report_data.get('overall_confidence', 0)
        conf_pct = raw_conf if raw_conf > 1 else raw_conf * 100
        conf_pct = max(0.0, min(100.0, float(conf_pct)))
        conf_pct_str = f"{conf_pct:.1f}"

        verdict = report_data.get('overall_verdict', 'UNKNOWN')
        risk = report_data.get('overall_risk', '')
        verdict_label = report_data.get('verdict', verdict)
        doc_name = report_data.get('document_name', 'Unknown')
        proc_time = report_data.get('processing_time_seconds', 0)
        is_forged = verdict == 'FORGED'
        verdict_bg = '#fde8e8' if is_forged else '#e8f5e9'
        verdict_border = '#e53e3e' if is_forged else '#38a169'

        detectors = report_data.get('detectors', report_data.get('detection_results', []))

        rows = ''
        for d in detectors:
            name = d.get('detector_name', d.get('name', ''))
            d_conf = d.get('confidence', 0)
            d_conf_pct = d_conf if d_conf > 1 else d_conf * 100
            status = '⚠️ Suspicious' if d.get('is_forged') else '✅ Clear'
            plain = d.get('plain_english', '')
            rows += f"""
            <tr>
              <td><strong>{name}</strong><br>
                <small style="color:#555">{plain}</small></td>
              <td style="text-align:center">{status}</td>
              <td>
                <div style="background:#e0e0e0;border-radius:4px;overflow:hidden;height:18px;width:140px">
                  <div style="width:{min(d_conf_pct,100):.1f}%;height:100%;
                       background:{'#e53e3e' if d.get('is_forged') else '#38a169'};"></div>
                </div>
                <small>{d_conf_pct:.1f}%</small>
              </td>
            </tr>"""

        region_rows = ''
        for d in detectors:
            d_name = d.get('detector_name', d.get('name', ''))
            for r in d.get('suspicious_regions', []):
                sev = float(r.get('severity', 0)) * 100
                rtype = r.get('type', 'unknown')
                bbox = r.get('bbox', [])
                det = r.get('details', '')
                colour = '#e53e3e' if sev >= 70 else ('#f6ad55' if sev >= 40 else '#68d391')
                region_rows += f"""
                <tr>
                  <td>{d_name}</td>
                  <td>{rtype}</td>
                  <td style="color:{colour};font-weight:600">{sev:.0f}%</td>
                  <td style="font-size:0.8em">{bbox}</td>
                  <td style="font-size:0.8em">{det}</td>
                </tr>"""

        if not region_rows:
            region_rows = '<tr><td colspan="5" style="text-align:center;color:#38a169">No suspicious regions detected</td></tr>'

        extracted = report_data.get('extracted_text', '')[:800]
        langs = ', '.join(report_data.get('languages_detected', []))

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ForeGuard Report — {doc_name}</title>
  <style>
    body{{font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:24px;background:#f7f8fa;color:#1a202c}}
    .container{{max-width:960px;margin:0 auto;background:#fff;border-radius:12px;
                box-shadow:0 2px 16px rgba(0,0,0,.10);padding:32px}}
    h1{{color:#2d3748;margin-top:0}}
    .badge{{display:inline-block;padding:4px 12px;border-radius:20px;
            font-size:.85rem;font-weight:600;margin-left:8px}}
    .verdict-box{{background:{verdict_bg};border-left:5px solid {verdict_border};
                  padding:16px 20px;border-radius:8px;margin:20px 0}}
    .conf-bar{{background:#e0e0e0;border-radius:6px;overflow:hidden;height:24px;width:100%;margin:8px 0}}
    .conf-fill{{height:100%;background:linear-gradient(90deg,{verdict_border},{verdict_border}aa);
                width:{conf_pct_str}%}}
    table{{width:100%;border-collapse:collapse;margin:12px 0}}
    th{{background:#2d3748;color:#fff;padding:10px;text-align:left;font-size:.9rem}}
    td{{padding:9px 10px;border-bottom:1px solid #e2e8f0;font-size:.88rem;vertical-align:top}}
    tr:hover td{{background:#f7fafc}}
    .section{{margin:24px 0}}
    .section h3{{color:#2d3748;border-bottom:2px solid #e2e8f0;padding-bottom:6px}}
    .extracted{{background:#f7f8fa;padding:12px;border-radius:6px;
                font-size:.82rem;white-space:pre-wrap;max-height:200px;overflow-y:auto}}
    footer{{margin-top:32px;font-size:.8rem;color:#a0aec0;text-align:center}}
  </style>
</head>
<body>
<div class="container">
  <h1>🛡️ ForeGuard Forgery Detection Report</h1>
  <p><strong>Document:</strong> {doc_name} &nbsp;
     <strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;
     <strong>Processing:</strong> {proc_time}s</p>
  <div class="verdict-box">
    <h2 style="margin:0 0 8px 0">
      Verdict: {verdict}
      <span class="badge" style="background:{verdict_border};color:#fff">{risk}</span>
    </h2>
    <p style="margin:0 0 4px 0">{verdict_label}</p>
    <div class="conf-bar"><div class="conf-fill"></div></div>
    <small>Overall forgery confidence: <strong>{conf_pct_str}%</strong></small>
  </div>
  <div class="section">
    <h3>🔬 Detector Results</h3>
    <table>
      <tr><th>Detector / Explanation</th><th>Status</th><th>Confidence</th></tr>
      {rows}
    </table>
  </div>
  <div class="section">
    <h3>⚠️ Suspicious Regions</h3>
    <table>
      <tr><th>Detector</th><th>Type</th><th>Severity</th><th>Location</th><th>Details</th></tr>
      {region_rows}
    </table>
  </div>
  {"<div class='section'><h3>📝 Extracted Text</h3><p><small>Languages: " + langs + "</small></p><div class='extracted'>" + extracted + "</div></div>" if extracted else ""}
  <footer>Generated by ForeGuard AI Forgery Detection System &bull; {datetime.now().year}</footer>
</div>
</body>
</html>"""