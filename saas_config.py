"""
saas_config.py — Smart City SaaS Tenant Configuration
Each city/client is a tenant with its own cameras, limits, and branding.
"""

# ── Tenant Registry ───────────────────────────────────────────────────────────
# tenant_id -> config dict
TENANTS = {
    "city_pune": {
        "name":         "Pune Municipal Corporation",
        "api_key":      "PMC-2024-XKJH91",
        "crowd_limit":  8,
        "cameras": {
            "CAM_A": 0,                                  # webcam
            "CAM_B": "http://10.211.20.90:8080/video",
            "CAM_C": "http://10.211.20.34:8080/video",
        },
        "restricted_zone": (300, 50, 580, 300),
        "signal_ped_thresh": 4,
        "plan": "enterprise",
    },
    "city_mumbai": {
        "name":         "Mumbai Traffic Authority",
        "api_key":      "MTA-2024-LMNP42",
        "crowd_limit":  10,
        "cameras": {
            "CAM_A": "http://192.168.1.10:8080/video",
        },
        "restricted_zone": (200, 100, 500, 350),
        "signal_ped_thresh": 6,
        "plan": "enterprise",
    },
    "mall_phoenix": {
        "name":         "Phoenix Mall Security",
        "api_key":      "PHX-2024-QRST77",
        "crowd_limit":  15,
        "cameras": {
            "CAM_A": "http://192.168.2.5:8080/video",
        },
        "restricted_zone": (100, 50, 400, 300),
        "signal_ped_thresh": 10,
        "plan": "basic",
    },
}

# ── Dashboard Users (per tenant) ──────────────────────────────────────────────
# username -> {password, tenant_id, role}
DASHBOARD_USERS = {
    "admin":        {"password": "admin123",   "tenant_id": "city_pune",    "role": "admin"},
    "pune_guard":   {"password": "guard456",   "tenant_id": "city_pune",    "role": "viewer"},
    "mumbai_admin": {"password": "mum2024",    "tenant_id": "city_mumbai",  "role": "admin"},
    "mall_admin":   {"password": "mall2024",   "tenant_id": "mall_phoenix", "role": "admin"},
    "viewer":       {"password": "view789",    "tenant_id": "city_pune",    "role": "viewer"},
}

# ── Subscription Plans ────────────────────────────────────────────────────────
PLANS = {
    "basic":      {"max_cameras": 1,  "price_per_month": 4999,  "pdf_reports": False, "cloud_push": False},
    "standard":   {"max_cameras": 3,  "price_per_month": 12999, "pdf_reports": True,  "cloud_push": False},
    "enterprise": {"max_cameras": 10, "price_per_month": 29999, "pdf_reports": True,  "cloud_push": True},
}

def get_tenant(tenant_id: str) -> dict:
    return TENANTS.get(tenant_id, {})

def get_plan(tenant_id: str) -> dict:
    tenant = get_tenant(tenant_id)
    return PLANS.get(tenant.get("plan", "basic"), PLANS["basic"])

def validate_api_key(api_key: str) -> str | None:
    """Returns tenant_id if valid, else None."""
    for tid, cfg in TENANTS.items():
        if cfg["api_key"] == api_key:
            return tid
    return None
