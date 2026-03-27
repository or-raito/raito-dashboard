#!/usr/bin/env python3
"""
RAITO — Phase 4: Cloud-Ready Dashboard Server (db_dashboard.py)

Flask application that generates the unified dashboard from PostgreSQL
and serves it as a web page. Designed for Gunicorn + Cloud Run.

Usage (local):
    cd scripts && python3 db/db_dashboard.py       # Flask dev server on :8080
    gunicorn --bind :8080 scripts.db.db_dashboard:app  # Production

Usage (Docker):
    docker build -t raito .
    docker run -p 8080:8080 -e DATABASE_URL=... raito

The `app` object is defined at module level so Gunicorn can find it via:
    scripts.db.db_dashboard:app
"""

import os
import sys
import logging
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────
# Ensure scripts/ is importable whether we're run from project root or scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, Response, send_file, request, jsonify

# ── Flask app (global — Gunicorn entry point) ─────────────────────────────
app = Flask(__name__)

# Configure logging for Cloud Run (structured stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


def _generate_dashboard_html():
    """Pull data from PostgreSQL, run all dashboard generators, return HTML string.

    This is the same pipeline as the old main(), but returns HTML instead of
    writing to disk. Imports are deferred to avoid import-time DB connections.
    """
    from config import OUTPUT_DIR
    from master_data_parser import parse_master_data
    from unified_dashboard import (
        generate_unified_dashboard,
        DASHBOARD_PASSWORD,
        _js_hash,
    )
    from db.database_manager import get_consolidated_data

    # 1. Load data from PostgreSQL
    log.info("Loading consolidated data from PostgreSQL...")
    data = get_consolidated_data()
    months = data.get('months', [])
    log.info(f"  Months loaded: {months}")

    for m in months:
        md = data['monthly_data'][m]
        combined = md.get('combined', {})
        total_u = sum(v.get('units', 0) for v in combined.values())
        total_r = sum(v.get('total_value', 0) for v in combined.values())
        log.info(f"  {m}: {total_u:,} units, ₪{total_r:,.0f} revenue")

    # 2. Parse master data (still from local files inside container)
    log.info("Parsing master data...")
    master_data = parse_master_data()

    # 3. Generate the unified dashboard HTML
    log.info("Generating unified dashboard HTML...")
    html = generate_unified_dashboard(data, master_data)

    # 4. Inject password hash
    pwd_hash = _js_hash(DASHBOARD_PASSWORD)
    html = html.replace('%%PWD_HASH%%', pwd_hash)

    log.info(f"Dashboard generated: {len(html) / 1024:.1f} KB")
    return html


# ── Cache ─────────────────────────────────────────────────────────────────
# In production the dashboard data changes at most weekly (new Excel ingestion).
# We cache the generated HTML and refresh on demand via /refresh.
_cached_html = None


@app.route('/')
def index():
    """Serve the unified dashboard. Generates on first request, then cached."""
    global _cached_html
    if _cached_html is None:
        log.info("First request — generating dashboard...")
        _cached_html = _generate_dashboard_html()
    return Response(_cached_html, mimetype='text/html; charset=utf-8')


@app.route('/refresh')
def refresh():
    """Force-regenerate the dashboard from fresh PostgreSQL data."""
    global _cached_html
    log.info("Refresh requested — regenerating dashboard...")
    from db.database_manager import reset_cache
    reset_cache()
    _cached_html = _generate_dashboard_html()
    return Response(
        '<html><body><h2>Dashboard refreshed.</h2>'
        '<p><a href="/">Go to dashboard</a></p></body></html>',
        mimetype='text/html; charset=utf-8',
    )


@app.route('/health')
def health():
    """Health check for Cloud Run / load balancers."""
    return {'status': 'ok'}


# ── Upload page ───────────────────────────────────────────────────────────────

_UPLOAD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAITO — Data Upload</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f1117; color: #e2e8f0; min-height: 100vh;
    display: flex; align-items: center; justify-content: center; padding: 24px;
  }
  .card {
    background: #1a1d27; border: 1px solid #2d3148; border-radius: 16px;
    width: 100%; max-width: 560px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }
  .logo { font-size: 13px; letter-spacing: 3px; color: #6c7aaa; text-transform: uppercase; margin-bottom: 8px; }
  h1 { font-size: 26px; font-weight: 700; color: #fff; margin-bottom: 6px; }
  .subtitle { font-size: 14px; color: #6c7aaa; margin-bottom: 32px; }
  .drop-zone {
    border: 2px dashed #2d3148; border-radius: 12px; padding: 40px 24px;
    text-align: center; cursor: pointer; transition: all 0.2s;
    background: #12151f;
  }
  .drop-zone:hover, .drop-zone.drag-over {
    border-color: #5b6af0; background: #1a1e30;
  }
  .drop-icon { font-size: 36px; margin-bottom: 12px; }
  .drop-text { font-size: 15px; color: #a0aec0; }
  .drop-text span { color: #5b6af0; cursor: pointer; text-decoration: underline; }
  .file-name {
    display: none; margin-top: 12px; font-size: 13px; color: #68d391;
    background: #0d1f17; border: 1px solid #1a4731; border-radius: 8px; padding: 8px 12px;
  }
  .options { margin-top: 24px; display: flex; flex-direction: column; gap: 16px; }
  .field label { font-size: 12px; color: #6c7aaa; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 6px; display: block; }
  select {
    width: 100%; background: #12151f; border: 1px solid #2d3148; border-radius: 8px;
    color: #e2e8f0; padding: 10px 14px; font-size: 14px; outline: none;
    appearance: none;
  }
  select:focus { border-color: #5b6af0; }
  .toggle-row { display: flex; align-items: center; gap: 10px; cursor: pointer; }
  .toggle-row input[type=checkbox] { width: 16px; height: 16px; accent-color: #5b6af0; cursor: pointer; }
  .toggle-label { font-size: 14px; color: #a0aec0; }
  .toggle-label small { display: block; font-size: 12px; color: #4a5568; margin-top: 2px; }
  .btn {
    width: 100%; padding: 14px; background: #5b6af0; color: #fff; border: none;
    border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer;
    margin-top: 28px; transition: background 0.2s; letter-spacing: 0.3px;
  }
  .btn:hover { background: #4a58d8; }
  .btn:disabled { background: #2d3148; color: #4a5568; cursor: not-allowed; }
  .result {
    display: none; margin-top: 24px; border-radius: 12px; padding: 20px;
    font-size: 13px; line-height: 1.7;
  }
  .result.success { background: #0d1f17; border: 1px solid #1a4731; color: #68d391; }
  .result.error   { background: #1f0d0d; border: 1px solid #4a1a1a; color: #fc8181; }
  .result.skipped { background: #1a1a0d; border: 1px solid #4a4a1a; color: #f6e05e; }
  .result-title { font-weight: 700; font-size: 15px; margin-bottom: 8px; }
  .result table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  .result td { padding: 3px 0; }
  .result td:first-child { color: #718096; padding-right: 16px; }
  .spinner { display: none; text-align: center; margin-top: 16px; color: #6c7aaa; font-size: 14px; }
  .back-link { display: block; text-align: center; margin-top: 24px; font-size: 13px; color: #5b6af0; text-decoration: none; }
  .back-link:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">Raito</div>
  <h1>Upload Distributor File</h1>
  <p class="subtitle">Drop a sales or stock file — it loads directly into the database.</p>

  <div class="drop-zone" id="dropZone">
    <div class="drop-icon">📂</div>
    <div class="drop-text">Drag & drop file here, or <span onclick="document.getElementById('fileInput').click()">browse</span></div>
    <input type="file" id="fileInput" accept=".xlsx,.xls,.pdf" style="display:none">
    <div class="file-name" id="fileName"></div>
  </div>

  <div class="options">
    <div class="field">
      <label>Distributor</label>
      <select id="distributor">
        <option value="">Auto-detect from filename</option>
        <option value="icedream">Icedream</option>
        <option value="mayyan">Ma'ayan</option>
        <option value="biscotti">Biscotti</option>
        <option value="karfree">Karfree (warehouse stock)</option>
      </select>
    </div>
    <label class="toggle-row">
      <input type="checkbox" id="forceCheck">
      <span class="toggle-label">
        Force re-import
        <small>Overwrite existing data for this period</small>
      </span>
    </label>
  </div>

  <button class="btn" id="uploadBtn" disabled onclick="doUpload()">Upload & Ingest</button>

  <div class="spinner" id="spinner">⏳ Uploading and ingesting data...</div>
  <div class="result" id="result"></div>
  <a href="/" class="back-link">← Back to dashboard</a>
</div>

<script>
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const fileNameEl = document.getElementById('fileName');
  const uploadBtn = document.getElementById('uploadBtn');
  let selectedFile = null;

  fileInput.addEventListener('change', () => setFile(fileInput.files[0]));

  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    setFile(e.dataTransfer.files[0]);
  });

  function setFile(f) {
    if (!f) return;
    selectedFile = f;
    fileNameEl.textContent = '📄 ' + f.name + '  (' + (f.size / 1024).toFixed(0) + ' KB)';
    fileNameEl.style.display = 'block';
    uploadBtn.disabled = false;
  }

  async function doUpload() {
    if (!selectedFile) return;
    const spinner = document.getElementById('spinner');
    const result = document.getElementById('result');

    uploadBtn.disabled = true;
    spinner.style.display = 'block';
    result.style.display = 'none';

    const fd = new FormData();
    fd.append('file', selectedFile, selectedFile.name);
    fd.append('distributor', document.getElementById('distributor').value);
    fd.append('force', document.getElementById('forceCheck').checked ? 'true' : 'false');

    try {
      const resp = await fetch('/upload', { method: 'POST', body: fd });
      const data = await resp.json();

      spinner.style.display = 'none';
      result.style.display = 'block';

      if (data.error) {
        result.className = 'result error';
        result.innerHTML = '<div class="result-title">✗ Error</div>' + escHtml(data.error);
      } else if (data.batches_new === 0 && data.batches_skipped > 0) {
        result.className = 'result skipped';
        result.innerHTML = '<div class="result-title">⚠ Already ingested</div>' +
          '<table><tr><td>File</td><td>' + escHtml(data.filename) + '</td></tr>' +
          '<tr><td>Batches skipped</td><td>' + data.batches_skipped + ' (already in DB)</td></tr>' +
          '<tr><td>Tip</td><td>Enable "Force re-import" to overwrite</td></tr></table>';
      } else {
        result.className = 'result success';
        result.innerHTML = '<div class="result-title">✓ Ingestion complete</div>' +
          '<table>' +
          '<tr><td>File</td><td>' + escHtml(data.filename) + '</td></tr>' +
          '<tr><td>Distributor</td><td>' + escHtml(data.distributor) + '</td></tr>' +
          '<tr><td>Type</td><td>' + escHtml(data.type) + '</td></tr>' +
          '<tr><td>Rows ingested</td><td>' + data.rows_processed.toLocaleString() + '</td></tr>' +
          '<tr><td>New batches</td><td>' + data.batches_new + '</td></tr>' +
          (data.batches_skipped ? '<tr><td>Batches skipped</td><td>' + data.batches_skipped + '</td></tr>' : '') +
          '<tr><td>Time</td><td>' + data.elapsed_s.toFixed(1) + 's</td></tr>' +
          '</table>' +
          '<div style="margin-top:12px"><a href="/refresh" style="color:#68d391">→ Refresh dashboard</a></div>';
      }
    } catch (err) {
      spinner.style.display = 'none';
      result.style.display = 'block';
      result.className = 'result error';
      result.innerHTML = '<div class="result-title">✗ Network error</div>' + escHtml(String(err));
    }
    uploadBtn.disabled = false;
  }

  function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
</script>
</body>
</html>"""


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """File upload page — ingest a distributor file directly into Cloud SQL."""
    if request.method == 'GET':
        return Response(_UPLOAD_HTML, mimetype='text/html; charset=utf-8')

    # ── POST: handle uploaded file ────────────────────────────────────────────
    import tempfile
    import shutil
    from datetime import datetime
    from pathlib import Path

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'No file received.'}), 400

    distributor_override = request.form.get('distributor', '').strip() or None
    force = request.form.get('force') == 'true'

    # Save to a temp dir using the original filename (needed for auto-detection)
    tmp_dir = tempfile.mkdtemp(prefix='raito_upload_')
    try:
        safe_name = Path(file.filename).name
        tmp_path = Path(tmp_dir) / safe_name
        file.save(str(tmp_path))

        # Import loader functions (local import to avoid startup overhead)
        from db.raito_loader import (
            detect_distributor, load_caches,
            load_icedream_sales, load_mayyan_sales, load_biscotti_sales,
            load_inventory_snapshot, get_local_connection, STOCK_PATTERNS,
        )

        # Detect distributor
        if distributor_override:
            distributor = distributor_override
            is_stock = (distributor == 'karfree') or any(
                p in safe_name.lower() for p in STOCK_PATTERNS
            )
        else:
            distributor, is_stock = detect_distributor(tmp_path)
            if not distributor:
                return jsonify({'error': (
                    f'Could not auto-detect distributor from filename "{safe_name}". '
                    'Please select a distributor manually.'
                )}), 400

        file_type = 'inventory/stock' if is_stock else 'sales transactions'
        log.info(f"Upload: {safe_name} → {distributor} [{file_type}] force={force}")

        # Connect (DATABASE_URL is set in Cloud Run; falls back to localhost)
        conn, connector = get_local_connection()
        cur = conn.cursor()
        started_at = datetime.now()

        try:
            load_caches(cur)

            if is_stock:
                rows_processed, batches_new, batches_skipped = load_inventory_snapshot(
                    cur, tmp_path, distributor, dry_run=False, force=force, verbose=False,
                )
            elif distributor == 'icedream':
                rows_processed, batches_new, batches_skipped = load_icedream_sales(
                    cur, tmp_path, dry_run=False, force=force, verbose=False,
                )
            elif distributor == 'mayyan':
                rows_processed, batches_new, batches_skipped = load_mayyan_sales(
                    cur, tmp_path, dry_run=False, force=force, verbose=False,
                )
            elif distributor == 'biscotti':
                rows_processed, batches_new, batches_skipped = load_biscotti_sales(
                    cur, tmp_path, dry_run=False, force=force, verbose=False,
                )
            else:
                conn.rollback()
                return jsonify({'error': f'Unknown distributor: {distributor}'}), 400

            conn.commit()
            elapsed = (datetime.now() - started_at).total_seconds()

            # Invalidate dashboard cache so next visit shows fresh data
            if batches_new > 0:
                global _cached_html
                _cached_html = None

            return jsonify({
                'filename': safe_name,
                'distributor': distributor,
                'type': file_type,
                'rows_processed': rows_processed,
                'batches_new': batches_new,
                'batches_skipped': batches_skipped,
                'elapsed_s': elapsed,
            })

        except Exception as e:
            conn.rollback()
            log.error(f"Upload ingestion error: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Standalone mode (dev server) ──────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    log.info(f"Starting Flask dev server on :{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
