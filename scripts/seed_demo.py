"""
Seed Script for MHM Demo (scripts/seed_demo.py)
Creates one counsellor account and 5 fictional cases with realistic synthetic narratives
going through the real API endpoints (NOT direct DB inserts of distress scores).

Case Trajectories:
  1. V001: Escalation trajectory (Moderate stress -> High anxiety & insomnia -> Explicit counselling request)
  2. V002: Stable low distress (Consistent low stress, high feelings of safety)
  3. V003: Safety concern alert (Severe active threat & fear triggers P1 priority alert)
  4. V004: Missed follow-up (Overdue check-in triggers P4 missed follow-up alert)
  5. V005: Gradual recovery (High initial trauma distress steadily improves over time)
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

import httpx

# Add backend directory to sys.path so we can import models/security if needed
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

COUNSELLOR_USERNAME = "admin_counsellor"
COUNSELLOR_PASSWORD = "changeme123"

# Defined synthetic case stories
SYNTHETIC_CASES = [
    {
        "code": "V001",
        "interval_days": 5,
        "victim_password": "DemoPass_V001!",
        "checkins": [
            {
                "offset_days": -10,
                "stress_level": 5,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Managing daily routines okay. Experiencing mild fatigue at work, but generally coping with tasks.",
            },
            {
                "offset_days": -5,
                "stress_level": 7,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": True,
                "wants_counselling": False,
                "free_text": "Waking up multiple times at night with persistent worry and intrusive thoughts about the upcoming legal hearing. Feeling tense throughout the day.",
            },
            {
                "offset_days": -1,
                "stress_level": 8,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": True,
                "wants_counselling": True,
                "free_text": "The anxiety is feeling overwhelming this week. I am having panic symptoms in crowds and would really appreciate speaking to a counsellor as soon as possible.",
            },
        ],
    },
    {
        "code": "V002",
        "interval_days": 7,
        "victim_password": "DemoPass_V002!",
        "checkins": [
            {
                "offset_days": -7,
                "stress_level": 2,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Feeling peaceful and settled in the temporary accommodation. Supported by local community support network.",
            },
            {
                "offset_days": -2,
                "stress_level": 2,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Attended community gardening and sleeping soundly through the night. Very grateful for ongoing support.",
            },
        ],
    },
    {
        "code": "V003",
        "interval_days": 5,
        "victim_password": "DemoPass_V003!",
        "checkins": [
            {
                "offset_days": -4,
                "stress_level": 4,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Routine week, started attending computer training courses.",
            },
            {
                "offset_days": 0,
                "stress_level": 9,
                "feels_safe": False,
                "faces_threat": True,
                "sleep_difficulty": True,
                "wants_counselling": True,
                "free_text": "A known associate of the perpetrator confronted me near the grocery store and shouted direct threats. I am terrified and do not feel safe in this neighborhood. Need immediate protection assistance.",
            },
        ],
    },
    {
        "code": "V004",
        "interval_days": 3,
        "victim_password": "DemoPass_V004!",
        "checkins": [
            {
                "offset_days": -12,
                "stress_level": 3,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Everything stable. Will check in again next week.",
            },
        ],
    },
    {
        "code": "V005",
        "interval_days": 7,
        "victim_password": "DemoPass_V005!",
        "checkins": [
            {
                "offset_days": -14,
                "stress_level": 8,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": True,
                "wants_counselling": True,
                "free_text": "Very difficult transition period. Nightmares and intrusive recollections are frequent since moving.",
            },
            {
                "offset_days": -7,
                "stress_level": 5,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": True,
                "wants_counselling": False,
                "free_text": "Attended first trauma coping seminar. Grounding exercises are helping reduce acute panic.",
            },
            {
                "offset_days": -1,
                "stress_level": 3,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Sleeping much better. Reconnected with family members and feeling hopeful about the future.",
            },
        ],
    },
]


def set_deterministic_victim_password(username: str, plain_password: str):
    """Update victim password in backend/mhm.db so credentials printed in the table work reliably."""
    try:
        import sqlite3
        from app.security import hash_password
        db_path = BACKEND_DIR / "mhm.db"
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(plain_password), username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Warn] Could not set deterministic password for {username}: {e}")


async def seed_demo():
    print("=" * 80)
    print("MHM DEMO DATABASE SEEDING SCRIPT")
    print("Generating synthetic cases via live API endpoints...")
    print("=" * 80)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # 1. Login as Counsellor
        print(f"\n[1] Authenticating counsellor '{COUNSELLOR_USERNAME}'...")
        login_resp = await client.post(
            "/auth/login",
            json={"username": COUNSELLOR_USERNAME, "password": COUNSELLOR_PASSWORD},
        )
        if login_resp.status_code != 200:
            print(f"Error logging in as counsellor: {login_resp.text}")
            sys.exit(1)
        counsellor_token = login_resp.json()["access_token"]
        counsellor_headers = {"Authorization": f"Bearer {counsellor_token}"}
        print("-> Counsellor authenticated successfully.")

        results_table = []

        now = datetime.now(timezone.utc)

        # 2. Iterate each synthetic case
        for case_spec in SYNTHETIC_CASES:
            case_code = case_spec["code"]
            interval = case_spec["interval_days"]
            v_password = case_spec["victim_password"]

            print(f"\n[2] Processing case '{case_code}'...")

            # Check if case exists
            chk_case = await client.get(f"/cases/{case_code}", headers=counsellor_headers)
            victim_username = f"v_{case_code.lower()}"

            if chk_case.status_code == 404:
                # Create case via API
                create_resp = await client.post(
                    "/cases",
                    headers=counsellor_headers,
                    json={
                        "case_code": case_code,
                        "follow_up_interval_days": interval,
                        "consent_given": True,
                        "initial_victim_password": v_password,
                    },
                )
                if create_resp.status_code != 201:
                    print(f"Failed to create case {case_code}: {create_resp.text}")
                    continue
                c_data = create_resp.json()
                victim_username = c_data["victim_username"]
                print(f"-> Created new case {case_code} with victim user {victim_username}")
            else:
                print(f"-> Case {case_code} already exists. Ensuring idempotency...")
                # Ensure deterministic victim password in DB if existing
                set_deterministic_victim_password(victim_username, v_password)

            # Authenticate as victim
            v_login = await client.post(
                "/auth/login",
                json={"username": victim_username, "password": v_password},
            )
            if v_login.status_code != 200:
                print(f"Failed to login as victim {victim_username}: {v_login.text}")
                continue
            victim_token = v_login.json()["access_token"]
            victim_headers = {"Authorization": f"Bearer {victim_token}"}

            # Check existing check-ins count
            hist_resp = await client.get(f"/cases/{case_code}/checkins", headers=counsellor_headers)
            existing_count = len(hist_resp.json()) if hist_resp.status_code == 200 else 0

            # Submit check-ins if not already present
            if existing_count == 0:
                print(f"-> Submitting {len(case_spec['checkins'])} check-ins via POST /checkins (AI inference active)...")
                for chk in case_spec["checkins"]:
                    chk_time = now + timedelta(days=chk["offset_days"])
                    chk_payload = {
                        "stress_level": chk["stress_level"],
                        "feels_safe": chk["feels_safe"],
                        "faces_threat": chk["faces_threat"],
                        "sleep_difficulty": chk["sleep_difficulty"],
                        "wants_counselling": chk["wants_counselling"],
                        "free_text": chk["free_text"],
                        "created_at": chk_time.isoformat(),
                    }
                    c_resp = await client.post("/checkins", headers=victim_headers, json=chk_payload)
                    if c_resp.status_code == 201:
                        data = c_resp.json()
                        sc = data["checkin"]["distress_score"]
                        band = data["checkin"]["distress_band"]
                        alerts_num = len(data["alerts"])
                        print(f"   * Check-in @ {chk_time.strftime('%Y-%m-%d')}: Score={sc:.1f} ({band}) | Alerts={alerts_num}")
                    else:
                        print(f"   * Check-in failed: {c_resp.text}")
            else:
                print(f"-> Case already contains {existing_count} check-ins. Skipping duplicate submission.")

            # Record for summary table
            results_table.append({
                "code": case_code,
                "victim_user": victim_username,
                "victim_pass": v_password,
                "pattern": case_spec["checkins"][-1]["free_text"][:40] + "...",
            })

        # 3. Trigger Missed Follow-up Audit to generate P4 alert for V004
        print("\n[3] Triggering admin follow-up audit to evaluate overdue cases...")
        audit_resp = await client.post("/admin/run-followup-check", headers=counsellor_headers)
        if audit_resp.status_code == 200:
            print(f"-> Follow-up audit result: {audit_resp.json()}")

        # 4. Print Summary Credentials Table
        print("\n" + "=" * 80)
        print("DEMO CREDENTIALS & CASE ACCESS SUMMARY")
        print("=" * 80)
        print(f"Counsellor Portal:")
        print(f"  URL:      {BASE_URL}/static/index.html")
        print(f"  Username: {COUNSELLOR_USERNAME}")
        print(f"  Password: {COUNSELLOR_PASSWORD}\n")

        print("Victim Accounts (Synthetic Demo Cases):")
        print(f"{'Case Code':<10} | {'Username':<18} | {'Password':<18} | {'Scenario Note'}")
        print("-" * 80)
        for r in results_table:
            print(f"{r['code']:<10} | {r['victim_user']:<18} | {r['victim_pass']:<18} | {r['pattern']}")

        print("=" * 80)
        print("Demo seeding complete. System ready for clinical dashboard walkthrough.")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(seed_demo())
