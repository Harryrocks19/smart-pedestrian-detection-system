# 🏙️ SmartCity Vision — SaaS Startup Guide

## What Was Upgraded

### 1. YOLOv8 Person Detection (Core Upgrade)
- Replaced HOG detector with YOLOv8n for **10x better accuracy**
- HOG is kept as automatic fallback if ultralytics is not installed
- File: `Pedestrian_Detection.py`

### 2. Multi-Tenant SaaS Architecture
- Each city/client is a **tenant** with their own config
- Tenant-specific: crowd limit, restricted zone, signal threshold, cameras
- File: `saas_config.py`

### 3. Tenant-Aware Dashboard
- Login now shows **city name + plan badge** (Basic / Standard / Enterprise)
- Sidebar shows subscription details (max cameras, price, features)
- Enterprise plan gets **multi-camera selector**
- PDF reports gated behind Standard/Enterprise plan
- File: `dashboard.py`

### 4. API Key Authentication
- Every API endpoint now requires `X-API-Key` header
- Each tenant has their own API key
- `/plans` endpoint is public (for sales page)
- `/report` endpoint gated behind plan check
- File: `api_server.py`

---

## How to Run

```bash
# 1. Install YOLOv8 (one-time)
pip install ultralytics

# 2. Start detection for a specific tenant
set TENANT_ID=city_pune
python Pedestrian_Detection.py

# 3. Start web dashboard
streamlit run dashboard.py

# 4. Start API server (for Flutter app)
python api_server.py
```

---

## Tenant Credentials

| Username     | Password  | City / Client         | Plan       |
|-------------|-----------|----------------------|------------|
| admin        | admin123  | Pune Municipal Corp  | Enterprise |
| pune_guard   | guard456  | Pune Municipal Corp  | Enterprise |
| mumbai_admin | mum2024   | Mumbai Traffic Auth  | Enterprise |
| mall_admin   | mall2024  | Phoenix Mall         | Basic      |
| viewer       | view789   | Pune Municipal Corp  | Enterprise |

---

## API Usage (Flutter App)

```bash
# Get live status for Pune
curl -H "X-API-Key: PMC-2024-XKJH91" http://localhost:5000/status

# Get alerts
curl -H "X-API-Key: PMC-2024-XKJH91" http://localhost:5000/alerts

# Get tenant info
curl -H "X-API-Key: PMC-2024-XKJH91" http://localhost:5000/tenant

# View all plans (no auth needed)
curl http://localhost:5000/plans
```

---

## Adding a New City/Client

Edit `saas_config.py`:

```python
TENANTS["city_nagpur"] = {
    "name":              "Nagpur Smart City",
    "api_key":           "NGC-2024-XXXX99",
    "crowd_limit":       6,
    "cameras":           {"CAM_A": 0},
    "restricted_zone":   (200, 50, 500, 300),
    "signal_ped_thresh": 4,
    "plan":              "standard",
}

DASHBOARD_USERS["nagpur_admin"] = {
    "password":  "ngp2024",
    "tenant_id": "city_nagpur",
    "role":      "admin",
}
```

---

## Pricing (Monthly Subscription)

| Plan       | Cameras | Price/Month | PDF Reports | Cloud Push |
|------------|---------|-------------|-------------|------------|
| Basic      | 1       | ₹4,999      | ❌          | ❌         |
| Standard   | 3       | ₹12,999     | ✅          | ❌         |
| Enterprise | 10      | ₹29,999     | ✅          | ✅         |

---

## File Structure After Upgrade

```
AI Insem/
├── Pedestrian_Detection.py   ← YOLOv8 person detection + tenant config
├── saas_config.py            ← NEW: tenant registry + plans + users
├── dashboard.py              ← Multi-tenant SaaS dashboard
├── api_server.py             ← API key authenticated REST API
├── db_manager.py             ← PostgreSQL/SQLite database
├── sort.py                   ← SORT tracking algorithm
├── multi_camera.py           ← Multi-camera support
├── pdf_report.py             ← PDF report generator
├── register_face.py          ← Face registration
├── flutter_app/              ← Mobile app
└── logs/                     ← All output logs, heatmaps, snapshots
```
