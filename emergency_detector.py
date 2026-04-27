"""
emergency_detector.py — Silent Emergency Detection Module
Uses Gemini AI to classify text input as distress or normal.
Safe word: "pineapple" triggers instant alert.
Run standalone: python emergency_detector.py
Or import: from emergency_detector import EmergencyDetector
"""

import os
import csv
import time
import threading
import winsound
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")   # set via: set GEMINI_API_KEY=your_key
SAFE_WORD       = "pineapple"
LOG_FILE        = "logs/emergency_log.csv"
DISTRESS_KEYWORDS = ["help", "emergency", "danger", "attack", "fire", "save me",
                     "call police", "hurt", "bleeding", "trapped", "sos"]

os.makedirs("logs", exist_ok=True)
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(["Timestamp", "Input", "Result", "Source"])


def _log_event(text, result, source="text"):
    with open(LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text, result, source
        ])


def _play_emergency_alarm():
    for _ in range(5):
        winsound.Beep(1500, 400)
        time.sleep(0.1)


def classify_with_gemini(text):
    """Returns 'DISTRESS' or 'NORMAL' using Gemini API."""
    if not GEMINI_API_KEY:
        return _keyword_fallback(text)
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model  = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are a public safety AI. Classify the following message as either "
            "DISTRESS or NORMAL. Reply with only one word: DISTRESS or NORMAL.\n\n"
            f"Message: \"{text}\""
        )
        response = model.generate_content(prompt)
        result   = response.text.strip().upper()
        return "DISTRESS" if "DISTRESS" in result else "NORMAL"
    except Exception as e:
        print(f"Gemini error: {e} — using keyword fallback")
        return _keyword_fallback(text)


def _keyword_fallback(text):
    """Simple keyword check when Gemini is unavailable."""
    lower = text.lower()
    return "DISTRESS" if any(kw in lower for kw in DISTRESS_KEYWORDS) else "NORMAL"


class EmergencyDetector:
    def __init__(self, on_emergency=None):
        """
        on_emergency: optional callback(text, source) called when emergency detected.
        """
        self.on_emergency  = on_emergency
        self.last_alert_ts = 0
        self.status        = "NORMAL"   # "NORMAL" or "EMERGENCY"
        self.last_input    = ""

    def check(self, text, source="text"):
        """Classify text. Returns True if emergency detected."""
        text = text.strip()
        if not text:
            return False

        self.last_input = text

        # Safe word — instant alert, no AI needed
        if SAFE_WORD in text.lower():
            self._trigger(text, "SAFE_WORD")
            return True

        result = classify_with_gemini(text)
        _log_event(text, result, source)

        if result == "DISTRESS":
            self._trigger(text, source, log=False)  # already logged above
            return True

        self.status = "NORMAL"
        return False

    def _trigger(self, text, source, log=True):
        self.status = "EMERGENCY"
        now = time.time()
        print(f"\n🚨 EMERGENCY DETECTED [{source}]: {text}")
        if log:
            _log_event(text, "DISTRESS", source)
        if now - self.last_alert_ts > 10:
            threading.Thread(target=_play_emergency_alarm, daemon=True).start()
            self.last_alert_ts = now
        if self.on_emergency:
            self.on_emergency(text, source)

    def reset(self):
        self.status = "NORMAL"


# ── Standalone CLI mode ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Silent Emergency Detector ===")
    print(f"Safe word: '{SAFE_WORD}' | Type 'quit' to exit\n")

    detector = EmergencyDetector()

    while True:
        try:
            text = input("Enter message: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() == "quit":
            break
        if not text:
            continue

        is_emergency = detector.check(text)
        if is_emergency:
            print("🚨 STATUS: EMERGENCY DETECTED — Alert triggered!")
        else:
            print("✅ STATUS: NORMAL")
        print()
