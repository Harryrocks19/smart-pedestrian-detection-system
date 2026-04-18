"""
api_server.py  —  SmartCity Vision SaaS REST API
Run: python api_server.py

Authentication: Pass header  X-API-Key: <your_tenant_api_key>

Endpoints:
  GET  /status        — live stats
  GET  /alerts        — last 20 alerts
  GET  /signal        — last 20 signal changes
  GET  /heatmap       — latest heatmap image
  GET  /snapshots     — list of snapshot filenames
  GET  /snapshot/<f>  — serve a snapshot image
  GET  /incidents     — list of incident clips
  GET  /report        — AI pattern report as JSON
  GET  /tenant        — tenant info (name, plan, cameras)
"""

import os
import csv
import glob
import json
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, send_file, abort, request

app = Flask(__name__)

LOG_FILE     = "logs/detection_log.csv"
ALERT_LOG    = "logs/alert_log.csv"
SIGNAL_LOG   = "logs/signal_log.csv"
HEATMAP_FILE = "logs/final_heatmap.jpg"
SNAPSHOT_DIR = "logs/snapshots"
INCIDENT_DIR = "logs/incidents"

# ── SaaS tenant auth ──────────────────────────────────────────────────────────
try:
    from saas_config import validate_api_key, get_tenant, get_plan
    SAAS_ENABLED = True
except Exception:
    SAAS_ENABLED = False
    def validate_api_key(_): return "default"
    def get_tenant(_):       return {"name": "Default", "plan": "basic"}
    def get_plan(_):         return {"max_cameras": 1, "pdf_reports": True, "cloud_push": False}


def require_api_key(f):
    """Decorator: validates X-API-Key header and injects tenant_id into kwargs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key   = request.headers.get("X-API-Key", "")
        tenant_id = validate_api_key(api_key)
        if tenant_id is None:
            return jsonify({"error": "Invalid or missing API key"}), 401
        kwargs["tenant_id"] = tenant_id
        return f(*args, **kwargs)
    return decorated


def read_csv_tail(path, n=20):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-n:]


# ── /tenant ───────────────────────────────────────────────────────────────────
@app.route("/tenant")
@require_api_key
def tenant_info(tenant_id):
    info = get_tenant(tenant_id)
    plan = get_plan(tenant_id)
    return jsonify({
        "tenant_id":   tenant_id,
        "name":        info.get("name", tenant_id),
        "plan":        info.get("plan", "basic"),
        "max_cameras": plan["max_cameras"],
        "cameras":     list(info.get("cameras", {}).keys()),
        "pdf_reports": plan["pdf_reports"],
        "cloud_push":  plan["cloud_push"],
    })


# ── /status ───────────────────────────────────────────────────────────────────
@app.route("/status")
@require_api_key
def status(tenant_id):
    rows       = read_csv_tail(LOG_FILE, 1)
    sig_rows   = read_csv_tail(SIGNAL_LOG, 1)
    alert_rows = read_csv_tail(ALERT_LOG, 1)

    last       = rows[0]       if rows       else {}
    sig        = sig_rows[0].get("Signal", "UNKNOWN")   if sig_rows   else "UNKNOWN"
    last_alert = alert_rows[0].get("Type", "NONE")      if alert_rows else "NONE"

    return jsonify({
        "tenant":      get_tenant(tenant_id).get("name", tenant_id),
        "timestamp":   last.get("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "people":      int(float(last.get("People Count", 0))),
        "violations":  int(float(last.get("Violations", 0))),
        "vehicles":    int(float(last.get("Vehicles", 0))),
        "risk":        int(float(last.get("Risk", 0))),
        "alert":       last.get("Alert", "NO"),
        "alert_type":  last_alert,
        "signal":      sig,
    })


# ── /alerts ───────────────────────────────────────────────────────────────────
@app.route("/alerts")
@require_api_key
def alerts(tenant_id):
    return jsonify(read_csv_tail(ALERT_LOG, 20))


# ── /signal ───────────────────────────────────────────────────────────────────
@app.route("/signal")
@require_api_key
def signal(tenant_id):
    return jsonify(read_csv_tail(SIGNAL_LOG, 20))


# ── /heatmap ──────────────────────────────────────────────────────────────────
@app.route("/heatmap")
@require_api_key
def heatmap(tenant_id):
    if os.path.exists(HEATMAP_FILE):
        return send_file(HEATMAP_FILE, mimetype="image/jpeg")
    abort(404)


# ── /snapshots ────────────────────────────────────────────────────────────────
@app.route("/snapshots")
@require_api_key
def snapshots(tenant_id):
    files = sorted(glob.glob(f"{SNAPSHOT_DIR}/*.jpg"), reverse=True)[:10]
    return jsonify([os.path.basename(f) for f in files])


@app.route("/snapshot/<filename>")
@require_api_key
def snapshot(filename, tenant_id):
    path = os.path.join(SNAPSHOT_DIR, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    abort(404)


# ── /incidents ────────────────────────────────────────────────────────────────
@app.route("/incidents")
@require_api_key
def incidents(tenant_id):
    files = sorted(glob.glob(f"{INCIDENT_DIR}/*.avi"), reverse=True)[:10]
    return jsonify([os.path.basename(f) for f in files])


# ── /report ───────────────────────────────────────────────────────────────────
@app.route("/report")
@require_api_key
def report(tenant_id):
    # Check plan allows reports
    plan = get_plan(tenant_id)
    if not plan.get("pdf_reports"):
        return jsonify({"error": "Reports not available on your plan. Upgrade to Standard or Enterprise."}), 403

    rows       = read_csv_tail(LOG_FILE, 1000)
    alert_rows = read_csv_tail(ALERT_LOG, 1000)

    if not rows:
        return jsonify({"lines": ["No data available yet."]})

    people_vals = [int(float(r.get("People Count", 0))) for r in rows]
    viol_vals   = [int(float(r.get("Violations",   0))) for r in rows]
    risk_vals   = [int(float(r.get("Risk",         0))) for r in rows]

    lines = [
        f"Tenant: {get_tenant(tenant_id).get('name', tenant_id)}",
        f"Total records: {len(rows)}",
        f"Peak people count: {max(people_vals)}",
        f"Average people: {sum(people_vals)/len(people_vals):.1f}",
        f"Total violations: {sum(viol_vals)}",
        f"Total risk events: {sum(risk_vals)}",
        f"Total alerts: {len(alert_rows)}",
    ]

    if alert_rows:
        types       = [r.get("Type", "") for r in alert_rows]
        most_common = max(set(types), key=types.count)
        lines.append(f"Most frequent alert type: {most_common}")

    lines.append("--- Recommendations ---")
    if max(people_vals) >= 5:
        lines.append("High crowd density detected — deploy extra monitoring.")
    if sum(viol_vals) > 10:
        lines.append("Frequent violations — recommend social distancing signage.")
    if sum(risk_vals) > 5:
        lines.append("Multiple collision risks — recommend speed control measures.")

    return jsonify({"lines": lines, "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


# ── /plans (public — no auth needed) ─────────────────────────────────────────
@app.route("/plans")
def plans():
    try:
        from saas_config import PLANS
        return jsonify(PLANS)
    except Exception:
        return jsonify({})


if __name__ == "__main__":
    print("SmartCity Vision API Server running on http://0.0.0.0:5000")
    print("Pass header:  X-API-Key: <your_tenant_api_key>")
    print("Example:      curl -H 'X-API-Key: PMC-2024-XKJH91' http://localhost:5000/status")
    app.run(host="0.0.0.0", port=5000, debug=False)
