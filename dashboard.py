import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import sqlite3
import time
from datetime import datetime
from PIL import Image

st.set_page_config(page_title="SmartCity Vision — SaaS Platform", layout="wide", page_icon="🏙️")

# ── Paths ─────────────────────────────────────────────────────────────────────
LOG_FILE      = "logs/detection_log.csv"
ALERT_LOG     = "logs/alert_log.csv"
SIGNAL_LOG    = "logs/signal_log.csv"
SNAPSHOT_DIR  = "logs/snapshots"
HEATMAP_FILE  = "logs/final_heatmap.jpg"
HEATMAP_DIR   = "logs/heatmaps"
INCIDENT_DIR  = "logs/incidents"
DB_FILE       = "logs/smart_pedestrian.db"
REPORTS_DIR   = "logs/reports"

# ── SaaS Multi-Tenant Config ──────────────────────────────────────────────────
try:
    from saas_config import DASHBOARD_USERS, get_tenant, get_plan, PLANS
    SAAS_ENABLED = True
except Exception:
    SAAS_ENABLED = False
    DASHBOARD_USERS = {
        "admin":  {"password": "admin123", "tenant_id": "default", "role": "admin"},
        "viewer": {"password": "view789",  "tenant_id": "default", "role": "viewer"},
    }
    def get_tenant(_): return {}
    def get_plan(_):   return {"max_cameras": 1, "price_per_month": 0, "pdf_reports": True, "cloud_push": False}
    PLANS = {}

# ── Login ─────────────────────────────────────────────────────────────────────
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        st.markdown("## 🏙️ SmartCity Vision — SaaS Platform")
        st.markdown("##### AI-Powered Pedestrian & Traffic Monitoring for Smart Cities")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True):
                user = DASHBOARD_USERS.get(username)
                if user and user["password"] == password:
                    st.session_state.logged_in   = True
                    st.session_state.username    = username
                    st.session_state.role        = user["role"]
                    st.session_state.tenant_id   = user["tenant_id"]
                    tenant_info = get_tenant(user["tenant_id"])
                    st.session_state.tenant_name = tenant_info.get("name", user["tenant_id"])
                    st.session_state.plan        = tenant_info.get("plan", "basic")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            st.caption("Demo: admin / admin123  |  viewer / view789")
        st.stop()

check_login()

# ── Sidebar ───────────────────────────────────────────────────────────────────
tenant_name = st.session_state.get("tenant_name", "Default")
plan        = st.session_state.get("plan", "basic")
plan_badge  = {"basic": "🔵 Basic", "standard": "🟡 Standard", "enterprise": "🟢 Enterprise"}.get(plan, plan)

st.sidebar.markdown(f"🏙️ **{tenant_name}**")
st.sidebar.markdown(f"👤 {st.session_state.get('username','?')} `{st.session_state.get('role','?')}`")
st.sidebar.markdown(f"Plan: {plan_badge}")
st.sidebar.markdown("---")

# Camera selector (enterprise only)
if SAAS_ENABLED and plan == "enterprise":
    tenant_cfg   = get_tenant(st.session_state.get("tenant_id", ""))
    cam_names    = list(tenant_cfg.get("cameras", {"CAM_A": 0}).keys())
    selected_cam = st.sidebar.selectbox("📹 Active Camera", cam_names)
    st.sidebar.caption(f"Source: {tenant_cfg['cameras'][selected_cam]}")
else:
    selected_cam = "CAM_A"

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

refresh = st.sidebar.slider("Auto Refresh (seconds)", 2, 30, 5)
st.sidebar.markdown("---")
st.sidebar.info("Run `python Pedestrian_Detection.py` to start detection")

# Subscription info panel (admin only)
if st.session_state.get("role") == "admin" and SAAS_ENABLED:
    plan_info = get_plan(st.session_state.get("tenant_id", ""))
    with st.sidebar.expander("💳 Subscription"):
        st.write(f"Plan: **{plan.title()}**")
        st.write(f"Max Cameras: {plan_info['max_cameras']}")
        st.write(f"Price: ₹{plan_info['price_per_month']:,}/month")
        st.write(f"PDF Reports: {'✅' if plan_info['pdf_reports'] else '❌'}")
        st.write(f"Cloud Push: {'✅' if plan_info['cloud_push'] else '❌'}")
        if plan != "enterprise":
            st.info("🔗 Upgrade to Enterprise for multi-camera + cloud push")

st.title(f"🏙️ SmartCity Vision — {tenant_name}")
st.caption(f"Camera: {selected_cam}  |  Plan: {plan_badge}  |  Powered by YOLOv8 AI")
st.markdown("---")

# ── Data Loaders ──────────────────────────────────────────────────────────────
def load_db_table(table, limit=500):
    if not os.path.exists(DB_FILE):
        return None
    try:
        conn = sqlite3.connect(DB_FILE)
        df   = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC LIMIT {limit}", conn)
        conn.close()
        return df if len(df) > 0 else None
    except Exception:
        return None

def load_csv(path):
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        return df if len(df) > 0 else None
    except Exception:
        return None

df = load_db_table("detection_log")
if df is None:
    df = load_csv(LOG_FILE)
    if df is not None:
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

adf      = load_db_table("alert_log")   or load_csv(ALERT_LOG)
sdf      = load_db_table("signal_log")  or load_csv(SIGNAL_LOG)
anom_df  = load_db_table("anomaly_log", 100)
queue_df = load_db_table("queue_log",   100)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
if df is not None:
    for col in ['people', 'people_count']:
        if col in df.columns:
            df['people'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            break
    for col in ['violations', 'vehicles', 'risk']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Current People",   int(df['people'].iloc[0])   if len(df) > 0 else 0)
    col2.metric("Peak People",      int(df['people'].max())     if len(df) > 0 else 0)
    col3.metric("Total Violations", int(df['violations'].sum()))
    col4.metric("Total Alerts",     len(adf)     if adf     is not None else 0)
    col5.metric("Anomalies",        len(anom_df) if anom_df is not None else 0)
    col6.metric("Queue Events",     len(queue_df)if queue_df is not None else 0)

    # ── Crowd Risk Level ─────────────────────────────────────────────────────────────
    if len(df) > 0:
        cur_people = int(df['people'].iloc[0])
        cur_viol   = int(df['violations'].iloc[0]) if 'violations' in df.columns else 0
        score = cur_people + cur_viol * 0.5
        if score < 3:
            risk_label, risk_color = "LOW 🟢",    "green"
        elif score < 6:
            risk_label, risk_color = "MEDIUM 🟡", "orange"
        else:
            risk_label, risk_color = "HIGH 🔴",   "red"
        st.markdown(f"### Crowd Risk Level: :{risk_color}[{risk_label}]")

    # ── Emergency Status ─────────────────────────────────────────────────────────────────
    emg_log = "logs/emergency_log.csv"
    if os.path.exists(emg_log):
        try:
            emg_df = pd.read_csv(emg_log)
            if len(emg_df) > 0:
                last_emg = emg_df.iloc[-1]
                if last_emg.get("Result", "") == "DISTRESS":
                    st.error(f"🚨 EMERGENCY DETECTED — Last input: `{last_emg.get('Input','')}` at {last_emg.get('Timestamp','')}")
                else:
                    st.success("✅ Emergency Status: NORMAL")
                with st.expander("🚨 Emergency Log"):
                    st.dataframe(emg_df.tail(10), use_container_width=True)
        except Exception:
            pass
    else:
        st.info("🚨 Emergency Status: No data yet. Run emergency_detector.py or type in terminal.")

    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("Peak Vehicles",   int(df['vehicles'].max()) if len(df) > 0 else 0)
    dc2.metric("Peak Risk Count", int(df['risk'].max())     if len(df) > 0 else 0)
    dc3.info("Face Blur: AUTO ON — Press B in detection window to toggle")
    st.markdown("---")

    # ── Charts ────────────────────────────────────────────────────────────────
    ts_col = 'timestamp' if 'timestamp' in df.columns else 'Timestamp'
    if ts_col in df.columns:
        df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📈 People Count Over Time")
        fig = px.line(df, x=ts_col, y='people', color_discrete_sequence=["#00ff88"])
        fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.subheader("⚠️ Violations Over Time")
        fig2 = px.bar(df, x=ts_col, y='violations', color_discrete_sequence=["#ff4444"])
        fig2.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("🚗 Vehicles Over Time")
        fig3 = px.line(df, x=ts_col, y='vehicles', color_discrete_sequence=["#ff8800"])
        fig3.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig3, use_container_width=True)
    with col_d:
        st.subheader("⚡ Collision Risk Over Time")
        fig4 = px.bar(df, x=ts_col, y='risk', color_discrete_sequence=["#ff0066"])
        fig4.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig4, use_container_width=True)

    if anom_df is not None and len(anom_df) > 0:
        st.subheader("🔬 Anomaly Events")
        anom_df['timestamp'] = pd.to_datetime(anom_df['timestamp'], errors='coerce')
        fig5 = px.scatter(anom_df, x='timestamp', y='z_score', size='people',
                          color_discrete_sequence=["#00ffff"], title="Anomaly Z-Score Over Time")
        fig5.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig5, use_container_width=True)

    if queue_df is not None and len(queue_df) > 0:
        st.subheader("🚶 Queue Events")
        queue_df['timestamp'] = pd.to_datetime(queue_df['timestamp'], errors='coerce')
        fig6 = px.bar(queue_df, x='timestamp', y='queue_count', color_discrete_sequence=["#ffa500"])
        fig6.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig6, use_container_width=True)

    # ── Alert Log ─────────────────────────────────────────────────────────────
    st.subheader("🚨 Smart Alert Log")
    if adf is not None and len(adf) > 0:
        type_col = 'type' if 'type' in adf.columns else 'Type'
        st.dataframe(adf.head(20), use_container_width=True)
        ac1, ac2, ac3 = st.columns(3)
        ac1.metric("Crowd Alerts",    int((adf[type_col] == "CROWD").sum()))
        ac2.metric("Zone Breaches",   int((adf[type_col] == "ZONE_BREACH").sum()))
        ac3.metric("Collision Risks", int((adf[type_col] == "COLLISION_RISK").sum()))
    else:
        st.success("No alerts logged yet.")

    with st.expander("📋 View Raw Detection Log"):
        st.dataframe(df.head(50), use_container_width=True)

else:
    st.warning("No log data found. Start `Pedestrian_Detection.py` first.")

st.markdown("---")

# ── Heatmap ───────────────────────────────────────────────────────────────────
col_h, col_s = st.columns(2)
with col_h:
    st.subheader("🔥 Live Crowd Heatmap")
    if os.path.exists(HEATMAP_FILE):
        st.image(HEATMAP_FILE, use_container_width=True)
    else:
        st.info("Heatmap will appear after session ends.")
    st.subheader("📊 Heatmap History")
    if os.path.exists(HEATMAP_DIR):
        hmaps = sorted(glob.glob(f"{HEATMAP_DIR}/*.jpg"), reverse=True)[:4]
        if hmaps:
            hcols = st.columns(min(len(hmaps), 4))
            for i, hf in enumerate(hmaps):
                hcols[i].image(hf, caption=os.path.basename(hf), use_container_width=True)
        else:
            st.info("Hourly heatmap snapshots will appear here.")

with col_s:
    st.subheader("📸 Alert Snapshots")
    if os.path.exists(SNAPSHOT_DIR):
        snaps = sorted(glob.glob(f"{SNAPSHOT_DIR}/*.jpg"), reverse=True)[:6]
        if snaps:
            cols = st.columns(3)
            for i, snap in enumerate(snaps):
                cols[i % 3].image(snap, caption=os.path.basename(snap), use_container_width=True)
        else:
            st.info("No snapshots yet.")
    else:
        st.info("Snapshots folder not found.")

st.markdown("---")

# ── Traffic Signal ────────────────────────────────────────────────────────────
st.subheader("🚦 Smart Traffic Signal")
if sdf is not None and len(sdf) > 0:
    sig_col   = 'signal' if 'signal' in sdf.columns else 'Signal'
    sig       = sdf.iloc[0][sig_col]
    sig_color = {"RED": "red", "YELLOW": "orange", "GREEN": "green"}.get(sig, "gray")
    st.markdown(f"### Current Signal: :{sig_color}[{sig}]")
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("RED triggers",    int((sdf[sig_col] == "RED").sum()))
    sc2.metric("YELLOW triggers", int((sdf[sig_col] == "YELLOW").sum()))
    sc3.metric("GREEN triggers",  int((sdf[sig_col] == "GREEN").sum()))
    st.dataframe(sdf.head(20), use_container_width=True)
else:
    st.info("Signal log not found. Start Pedestrian_Detection.py first.")

st.markdown("---")

# ── Incident Recordings ───────────────────────────────────────────────────────
st.subheader("🎥 Incident Recordings")
if os.path.exists(INCIDENT_DIR):
    clips = sorted(glob.glob(f"{INCIDENT_DIR}/*.avi"), reverse=True)[:5]
    if clips:
        for clip in clips:
            with open(clip, "rb") as f:
                st.download_button(f"Download {os.path.basename(clip)}",
                                   f, file_name=os.path.basename(clip))
    else:
        st.info("No incident clips yet.")
else:
    st.info("Incident folder not found.")

st.markdown("---")

# ── Emergency Detector UI ─────────────────────────────────────────────────────
st.subheader("🚨 Silent Emergency Detection")
st.caption("Type a message below. Gemini AI will classify it as DISTRESS or NORMAL. Safe word: 'pineapple'")

col_e1, col_e2 = st.columns([3, 1])
with col_e1:
    emg_input = st.text_input("Enter message (e.g. 'help', 'pineapple', 'I need assistance')",
                               key="emg_input", placeholder="Type here...")
with col_e2:
    check_btn = st.button("🔍 Check", use_container_width=True)

if check_btn and emg_input:
    try:
        from emergency_detector import EmergencyDetector
        det    = EmergencyDetector()
        result = det.check(emg_input, source="dashboard")
        if result:
            st.error(f"🚨 EMERGENCY DETECTED! Input: `{emg_input}`")
        else:
            st.success(f"✅ NORMAL — No distress detected in: `{emg_input}`")
    except Exception as e:
        st.warning(f"Emergency detector error: {e}")

st.markdown("---")

# ── Cloud Status ──────────────────────────────────────────────────────────────
st.subheader("☁️ Edge + Cloud Status")
plan_info = get_plan(st.session_state.get("tenant_id", ""))
if plan_info.get("cloud_push"):
    st.success("Cloud Push: ENABLED for your plan. Set CLOUD_ENDPOINT in Pedestrian_Detection.py.")
else:
    st.info("Cloud Push: Not available on your plan. Upgrade to Enterprise to enable.")

st.markdown("---")

# ── PDF Report Generator ──────────────────────────────────────────────────────
st.subheader("📄 AI Report Generator")

def generate_report_text(df, adf):
    if df is None or len(df) == 0:
        return ["No detection data available yet."]
    lines = []
    people_col  = 'people' if 'people' in df.columns else 'People Count'
    viol_col    = 'violations' if 'violations' in df.columns else 'Violations'
    people_vals = pd.to_numeric(df[people_col], errors='coerce').fillna(0)
    viol_vals   = pd.to_numeric(df[viol_col],   errors='coerce').fillna(0)
    lines.append(f"Tenant: {tenant_name}")
    lines.append(f"Total records: {len(df)}")
    lines.append(f"Peak people count: {int(people_vals.max())}")
    lines.append(f"Average people: {people_vals.mean():.1f}")
    lines.append(f"Total violations: {int(viol_vals.sum())}")
    lines.append(f"Total alerts: {len(adf) if adf is not None else 0}")
    if anom_df is not None:
        lines.append(f"Anomaly events: {len(anom_df)}")
    if queue_df is not None:
        lines.append(f"Queue events: {len(queue_df)}")
    lines.append("--- Recommendations ---")
    if people_vals.max() >= 5:
        lines.append("High crowd density — deploy extra monitoring.")
    if viol_vals.sum() > 10:
        lines.append("Frequent violations — recommend social distancing signage.")
    if anom_df is not None and len(anom_df) > 0:
        lines.append(f"{len(anom_df)} anomalies detected — review footage.")
    if queue_df is not None and len(queue_df) > 5:
        lines.append("Frequent queues — consider adding service counters.")
    return lines

col_r1, col_r2 = st.columns(2)
with col_r1:
    if st.button("🤖 Generate AI Text Report"):
        lines = generate_report_text(df, adf)
        st.markdown("### Analysis Report")
        for line in lines:
            if line.startswith("---"):
                st.markdown("---")
            else:
                st.write(f"• {line}")
        report_text = "\n".join(lines)
        st.download_button("📅 Download Report (.txt)", report_text,
                           file_name=f"report_{tenant_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")

with col_r2:
    pdf_allowed = plan_info.get("pdf_reports", True)
    if not pdf_allowed:
        st.warning("PDF Reports require Standard or Enterprise plan.")
    elif st.button("📄 Generate PDF Report"):
        try:
            from pdf_report import generate_pdf
            path = generate_pdf()
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    st.download_button("⬇️ Download PDF", f,
                                       file_name=os.path.basename(path),
                                       mime="application/pdf")
                st.success(f"PDF generated: {os.path.basename(path)}")
            else:
                st.error("PDF generation failed. Run: pip install reportlab")
        except Exception as e:
            st.error(f"Error: {e}. Run: pip install reportlab")

if os.path.exists(REPORTS_DIR):
    reports = sorted(glob.glob(f"{REPORTS_DIR}/*.pdf"), reverse=True)[:5]
    if reports:
        st.subheader("📁 Previous Reports")
        for rpt in reports:
            with open(rpt, "rb") as f:
                st.download_button(os.path.basename(rpt), f,
                                   file_name=os.path.basename(rpt),
                                   mime="application/pdf")

st.markdown("---")
st.caption(f"SmartCity Vision SaaS | Tenant: {tenant_name} | Dashboard auto-refreshes every {refresh}s")
time.sleep(refresh)
st.rerun()
