"""
pdf_report.py — Automatic PDF Report Generator
Run manually: python pdf_report.py
Or schedule: runs automatically at midnight via schedule library
pip install reportlab schedule
"""
import os
import csv
import sqlite3
from datetime import datetime, timedelta

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.units import cm
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("Install reportlab: pip install reportlab")

DB_FILE      = "logs/smart_pedestrian.db"
LOG_FILE     = "logs/detection_log.csv"
ALERT_LOG    = "logs/alert_log.csv"
HEATMAP_FILE = "logs/final_heatmap.jpg"
REPORTS_DIR  = "logs/reports"


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_db(sql, params=()):
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def generate_pdf(output_path=None):
    if not REPORTLAB_OK:
        print("reportlab not installed. Run: pip install reportlab")
        return None

    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    if output_path is None:
        output_path = f"{REPORTS_DIR}/report_{ts}.pdf"

    # Load data
    det_rows   = read_db("SELECT * FROM detection_log ORDER BY id DESC LIMIT 500") or read_csv(LOG_FILE)
    alert_rows = read_db("SELECT * FROM alert_log ORDER BY id DESC LIMIT 100")    or read_csv(ALERT_LOG)
    sig_rows   = read_db("SELECT * FROM signal_log ORDER BY id DESC LIMIT 100")
    anom_rows  = read_db("SELECT * FROM anomaly_log ORDER BY id DESC LIMIT 50")
    queue_rows = read_db("SELECT * FROM queue_log ORDER BY id DESC LIMIT 50")

    doc    = SimpleDocTemplate(output_path, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    # Title
    title_style = ParagraphStyle('title', parent=styles['Title'],
                                 fontSize=20, textColor=colors.HexColor('#1F6FEB'))
    story.append(Paragraph("Smart Pedestrian Detection System", title_style))
    story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                           styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    # Summary stats
    story.append(Paragraph("Summary Statistics", styles['Heading2']))
    people_vals = [int(float(r.get('people', r.get('People Count', 0)))) for r in det_rows]
    viol_vals   = [int(float(r.get('violations', r.get('Violations', 0)))) for r in det_rows]

    summary_data = [
        ['Metric', 'Value'],
        ['Total Records',        str(len(det_rows))],
        ['Peak People Count',    str(max(people_vals)) if people_vals else '0'],
        ['Average People',       f"{sum(people_vals)/len(people_vals):.1f}" if people_vals else '0'],
        ['Total Violations',     str(sum(viol_vals))],
        ['Total Alerts',         str(len(alert_rows))],
        ['Anomalies Detected',   str(len(anom_rows))],
        ['Queue Events',         str(len(queue_rows))],
        ['Signal Changes',       str(len(sig_rows))],
    ]
    t = Table(summary_data, colWidths=[8*cm, 8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F6FEB')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F0F4FF')]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,0), (-1,-1), 10),
        ('PADDING',    (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Alert breakdown
    if alert_rows:
        story.append(Paragraph("Alert Breakdown", styles['Heading2']))
        types = [r.get('type', r.get('Type', '')) for r in alert_rows]
        type_counts = {t: types.count(t) for t in set(types)}
        alert_data = [['Alert Type', 'Count']] + [[k, str(v)] for k, v in type_counts.items()]
        at = Table(alert_data, colWidths=[8*cm, 8*cm])
        at.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#FF4444')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FFF0F0')]),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE',   (0,0), (-1,-1), 10),
            ('PADDING',    (0,0), (-1,-1), 6),
        ]))
        story.append(at)
        story.append(Spacer(1, 0.5*cm))

    # Recent alerts table
    if alert_rows:
        story.append(Paragraph("Recent Alerts (Last 10)", styles['Heading2']))
        recent = alert_rows[:10]
        cols = ['timestamp', 'type', 'people', 'vehicles', 'risk']
        headers = ['Timestamp', 'Type', 'People', 'Vehicles', 'Risk']
        tdata = [headers] + [[str(r.get(c, r.get(c.title(), ''))) for c in cols] for r in recent]
        rt = Table(tdata, colWidths=[4.5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#333333')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F5F5')]),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE',   (0,0), (-1,-1), 8),
            ('PADDING',    (0,0), (-1,-1), 4),
        ]))
        story.append(rt)
        story.append(Spacer(1, 0.5*cm))

    # Heatmap image
    if os.path.exists(HEATMAP_FILE):
        story.append(Paragraph("Crowd Heatmap", styles['Heading2']))
        story.append(Image(HEATMAP_FILE, width=12*cm, height=7*cm))
        story.append(Spacer(1, 0.5*cm))

    # Recommendations
    story.append(Paragraph("AI Recommendations", styles['Heading2']))
    recs = []
    if people_vals and max(people_vals) >= 5:
        recs.append("High crowd density detected — consider deploying extra monitoring staff.")
    if sum(viol_vals) > 10:
        recs.append("Frequent social distancing violations — recommend public awareness signage.")
    if len(anom_rows) > 0:
        recs.append(f"{len(anom_rows)} anomaly events detected — review footage for unusual activity.")
    if len(queue_rows) > 5:
        recs.append("Frequent queue formation — consider adding service counters or staff.")
    if not recs:
        recs.append("No critical issues detected. System operating normally.")
    for rec in recs:
        story.append(Paragraph(f"• {rec}", styles['Normal']))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("— End of Report —", styles['Normal']))

    doc.build(story)
    print(f"PDF Report saved: {output_path}")
    return output_path


# Auto-schedule at midnight
def schedule_daily():
    try:
        import schedule, time
        schedule.every().day.at("00:00").do(generate_pdf)
        print("PDF report scheduled daily at midnight.")
        while True:
            schedule.run_pending()
            time.sleep(60)
    except ImportError:
        print("Install schedule: pip install schedule")


if __name__ == "__main__":
    path = generate_pdf()
    if path:
        print(f"Report generated: {path}")
