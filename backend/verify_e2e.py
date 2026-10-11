"""
Full End-to-End Verification and Demonstration Script.

This script:
1. Performs real HTTP calls against the FastAPI app (or running server):
   - Counsellor logs in (admin_counsellor)
   - Creates a new case 'V-ATROC-99'
   - Retrieves victim credentials (username and generated OTP)
   - Victim logs in, gets JWT
   - Victim submits 3 sequential check-ins:
       * Check-in 1: Baseline calm (no alerts)
       * Check-in 2: Acute threat and fear (triggers Safety Concern [P1] + Distress Jump [P3])
       * Check-in 3: Explicit counselling request + legal anxiety (triggers Counselling Request [P2] + support categories)
   - Counsellor queries /dashboard/summary
   - Counsellor queries /alerts (sorted by priority)
   - Counsellor queries /cases/V-ATROC-99/checkins and /trend
   - Counsellor reviews an alert (PATCH /alerts/{id}/review)
   - Counsellor records follow-up clinical action (POST /alerts/{id}/actions)
   - Admin triggers overdue follow-up scanner (POST /admin/run-followup-check)
2. Uses Playwright to drive the frontend UI in a real browser:
   - Captures 01_login_page.png
   - Submits victim login -> captures 02_victim_checkin_form.png
   - Submits victim check-in -> captures 03_victim_confirmation.png
   - Counsellor logs in -> captures 04_counsellor_dashboard.png
   - Opens case detail modal -> captures 05_case_detail_chart_and_breakdown.png
   - Records action -> captures 06_action_recorded.png
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import secrets
from pathlib import Path
import httpx

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://127.0.0.1:8000"


async def run_http_verification():
    print("=" * 80)
    print("MHM BACKEND FULL END-TO-END HTTP VERIFICATION")
    print("=" * 80)

    case_code = f"V-DEMO-{secrets.token_hex(2).upper()}"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90.0) as client:
        # 1. Counsellor Login
        print("\n[Step 1] Logging in as Counsellor (admin_counsellor)...")
        login_resp = await client.post(
            "/auth/login",
            json={"username": "admin_counsellor", "password": "changeme123"},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        counsellor_data = login_resp.json()
        c_token = counsellor_data["access_token"]
        c_headers = {"Authorization": f"Bearer {c_token}"}
        print(f"-> Counsellor Token received.")

        # 2. Create Case
        print(f"\n[Step 2] Creating Case '{case_code}' with informed consent...")
        case_resp = await client.post(
            "/cases",
            json={
                "case_code": case_code,
                "consent_given": True,
                "follow_up_interval_days": 7,
            },
            headers=c_headers,
        )
        assert case_resp.status_code == 201, f"Create case failed: {case_resp.text}"
        case_data = case_resp.json()
        case_info = case_data["case"]
        v_username = case_data["victim_username"]
        v_password = case_data["one_time_password"]
        print(f"-> Case Created: ID={case_info['id']}, Code={case_info['case_code']}")
        print(f"-> Generated Victim Credentials: Username={v_username}, OTP={v_password}")

        # 3. Victim Login
        print(f"\n[Step 3] Victim logging in ({v_username})...")
        v_login_resp = await client.post(
            "/auth/login",
            json={"username": v_username, "password": v_password},
        )
        assert v_login_resp.status_code == 200, f"Victim login failed: {v_login_resp.text}"
        victim_token = v_login_resp.json()["access_token"]
        v_headers = {"Authorization": f"Bearer {victim_token}"}
        print("-> Victim Token received.")

        # 4. Check-in 1: Baseline Calm
        print("\n[Step 4] Submitting Check-in 1: Baseline Calm...")
        checkin_1_payload = {
            "stress_level": 3,
            "feels_safe": True,
            "faces_threat": False,
            "sleep_difficulty": False,
            "wants_counselling": False,
            "free_text": "I spent the morning resting at home. Feeling reasonably calm and safe today.",
        }
        c1_resp = await client.post("/checkins", json=checkin_1_payload, headers=v_headers)
        assert c1_resp.status_code == 201, f"Checkin 1 failed: {c1_resp.text}"
        c1_data = c1_resp.json()
        chk1 = c1_data["checkin"]
        print(f"-> Check-in 1 Saved: ID={chk1['id']}, Score={chk1['distress_score']}, Band={chk1['distress_band']}")
        print(f"-> Emotion={chk1['emotion_label']}, Sentiment={chk1['sentiment_label']}")
        print(f"-> Alerts Triggered: {len(c1_data['alerts'])}")

        # 5. Check-in 2: Acute Threat and Fear
        print("\n[Step 5] Submitting Check-in 2: Acute Threat & Severe Fear...")
        checkin_2_payload = {
            "stress_level": 9,
            "feels_safe": False,
            "faces_threat": True,
            "sleep_difficulty": True,
            "wants_counselling": False,
            "free_text": "Someone suspicious was lingering outside my doorway last night. I am terrified, shaking, and could not sleep at all.",
        }
        c2_resp = await client.post("/checkins", json=checkin_2_payload, headers=v_headers)
        assert c2_resp.status_code == 201, f"Checkin 2 failed: {c2_resp.text}"
        c2_data = c2_resp.json()
        chk2 = c2_data["checkin"]
        print(f"-> Check-in 2 Saved: ID={chk2['id']}, Score={chk2['distress_score']}, Band={chk2['distress_band']}")
        print(f"-> Emotion={chk2['emotion_label']}, Sentiment={chk2['sentiment_label']}")
        print(f"-> Alerts Triggered ({len(c2_data['alerts'])}):")
        for alert in c2_data["alerts"]:
            print(f"   * [{alert['alert_type'].upper()}] - {alert['reason']}")

        # 6. Check-in 3: Counselling Request & Legal/Support Keywords
        print("\n[Step 6] Submitting Check-in 3: Counselling Request & Legal Support Need...")
        checkin_3_payload = {
            "stress_level": 7,
            "feels_safe": True,
            "faces_threat": False,
            "sleep_difficulty": True,
            "wants_counselling": True,
            "free_text": "I really need to speak with a psychological counsellor or therapist to cope with the trauma. Also I am worried about the lawyer fees for my legal case.",
        }
        c3_resp = await client.post("/checkins", json=checkin_3_payload, headers=v_headers)
        assert c3_resp.status_code == 201, f"Checkin 3 failed: {c3_resp.text}"
        c3_data = c3_resp.json()
        chk3 = c3_data["checkin"]
        print(f"-> Check-in 3 Saved: ID={chk3['id']}, Score={chk3['distress_score']}, Band={chk3['distress_band']}")
        print(f"-> Alerts Triggered ({len(c3_data['alerts'])}):")
        for alert in c3_data["alerts"]:
            print(f"   * [{alert['alert_type'].upper()}] - {alert['reason']}")
        print(f"-> Suggested Support Categories (Pending Professional Review):")
        for tag in c3_data.get("support_suggestions", []):
            print(f"   * Tag: {tag['category']} (Status: {tag['status_label']})")

        # 7. Counsellor Dashboard Summary
        print("\n[Step 7] Fetching Counsellor Dashboard Summary...")
        summary_resp = await client.get("/dashboard/summary", headers=c_headers)
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        print(f"-> Dashboard Metrics: Total Cases={summary['total_cases']}, Open Alerts={summary['open_alerts']}, "
              f"Pending Follow-ups={summary['pending_followups']}, High-Band Cases={summary['high_band_cases']}")

        # 8. Counsellor Alerts Queue
        print("\n[Step 8] Fetching Counsellor Alerts Queue (Sorted by Priority)...")
        alerts_resp = await client.get("/alerts", headers=c_headers)
        assert alerts_resp.status_code == 200
        alerts = alerts_resp.json()
        print(f"-> Total Active Alerts: {len(alerts)}")
        for a in alerts:
            print(f"   * [Alert #{a['id']}] Case: {a['case_code']} | Priority: {a['priority']} | Status: {a['status']} | Type: {a['alert_type']}")
            print(f"     Reason: {a['reason']}")

        # 9. Case Detail: Trend & Checkins
        print(f"\n[Step 9] Fetching Trend and Check-in History for Case '{case_code}'...")
        trend_resp = await client.get(f"/cases/{case_code}/trend", headers=c_headers)
        assert trend_resp.status_code == 200
        trend = trend_resp.json()
        print(f"-> Trend Data Points ({len(trend)}):")
        for pt in trend:
            print(f"   * {pt['date'][:19]} | Score={pt['distress_score']:.1f} | Stress={pt['stress_level']} | Emotion={pt['emotion_label']} | Alert Flag={pt['has_alert']}")

        history_resp = await client.get(f"/cases/{case_code}/checkins", headers=c_headers)
        assert history_resp.status_code == 200
        history = history_resp.json()
        print(f"-> History Items: {len(history)}")
        latest = history[-1]
        print(f"-> Latest Check-in Score Breakdown (Explainability):")
        print(json.dumps(latest["score_breakdown"], indent=4))

        # 10. Alert Review & Action Recording
        safety_alert = next((a for a in alerts if a["alert_type"] == "safety_concern"), alerts[0])
        alert_id = safety_alert["id"]
        print(f"\n[Step 10] Reviewing Alert #{alert_id} (marking reviewed)...")
        review_resp = await client.patch(f"/alerts/{alert_id}/review", headers=c_headers)
        assert review_resp.status_code == 200
        print(f"-> Review timestamp recorded: {review_resp.json()['reviewed_at']}")

        print(f"\n[Step 11] Recording Clinical Action and Resolving Alert #{alert_id}...")
        action_payload = {
            "action_taken": "Contacted individual via emergency secure mobile channel. Verified current physical location and connected to immediate local safe house / witness protection coordinator.",
            "contact_channel": "phone",
            "outcome": "Individual safely accommodated in secure shelter. Threat assessment filed with legal support unit.",
            "resolve_alert": True,
        }
        action_resp = await client.post(f"/alerts/{alert_id}/actions", json=action_payload, headers=c_headers)
        assert action_resp.status_code == 201
        act_res = action_resp.json()
        print(f"-> Action Recorded (ID={act_res['id']}) for Alert #{act_res['alert_id']}")
        print(f"-> Action Note: {act_res['action_taken']}")
        print(f"-> Outcome: {act_res['outcome']}")

        # 12. Run Follow-up Check
        print("\n[Step 12] Triggering Admin Follow-up Check...")
        admin_resp = await client.post("/admin/run-followup-check", headers=c_headers)
        assert admin_resp.status_code == 200
        print(f"-> Follow-up check result: {admin_resp.json()}")

    print("\n" + "=" * 80)
    print("BACKEND HTTP VERIFICATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    return v_username, v_password


async def run_playwright_screenshots(v_username: str, v_password: str):
    from playwright.async_api import async_playwright

    print("\n" + "=" * 80)
    print("PLAYWRIGHT FRONTEND BROWSER AUTOMATION & SCREENSHOT CAPTURE")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # 1. Login Page
        print("\n[UI 1] Loading Login Page...")
        await page.goto(f"{BASE_URL}/static/index.html")
        await page.wait_for_selector("#username")
        ss_path_1 = SCREENSHOT_DIR / "01_login_page.png"
        await page.screenshot(path=str(ss_path_1), full_page=True)
        print(f"-> Screenshot saved: {ss_path_1.name}")

        # 2. Login as Victim
        print(f"\n[UI 2] Logging in as Victim ({v_username})...")
        await page.fill("#username", v_username)
        await page.fill("#password", v_password)
        await page.click("button[type='submit']")

        # Wait for navigation to victim.html
        await page.wait_for_url("**/victim.html*")
        await page.wait_for_selector("#checkin-form")
        ss_path_2 = SCREENSHOT_DIR / "02_victim_checkin_form.png"
        await page.screenshot(path=str(ss_path_2), full_page=True)
        print(f"-> Screenshot saved: {ss_path_2.name}")

        # 3. Fill and Submit Victim Check-in
        print("\n[UI 3] Filling and submitting victim check-in form...")
        await page.fill("#stress-range", "6")
        await page.check("input[name='feels_safe'][value='true']")
        await page.check("input[name='faces_threat'][value='false']")
        await page.check("input[name='sleep_difficulty'][value='true']")
        await page.check("input[name='wants_counselling'][value='true']")
        await page.fill("#free-text", "Attended counselling session today and feeling more grounded. Appreciate the continued support.")
        await page.click("button[type='submit']")

        # Wait for confirmation screen
        await page.wait_for_selector("#confirmation-screen", state="visible")
        ss_path_3 = SCREENSHOT_DIR / "03_victim_confirmation.png"
        await page.screenshot(path=str(ss_path_3), full_page=True)
        print(f"-> Screenshot saved: {ss_path_3.name}")

        # 4. Counsellor Login and Dashboard
        print("\n[UI 4] Logging in as Counsellor (admin_counsellor)...")
        # Clear victim session from localStorage before navigating to login page
        await page.evaluate("window.localStorage.clear()")
        await page.goto(f"{BASE_URL}/static/index.html", wait_until="domcontentloaded")
        await page.wait_for_selector("#username", state="visible", timeout=15000)
        await page.fill("#username", "admin_counsellor")
        await page.fill("#password", "changeme123")
        # Use expect_navigation to catch the JS-driven redirect to dashboard.html
        async with page.expect_navigation(url="**/dashboard.html*", timeout=25000):
            await page.click("button[type='submit']")
        # Wait for a stable element that's always in the DOM on dashboard.html
        await page.wait_for_selector("#metric-cases", timeout=20000)
        await page.wait_for_timeout(2500)  # Allow API responses and table rendering
        ss_path_4 = SCREENSHOT_DIR / "04_counsellor_dashboard.png"
        await page.screenshot(path=str(ss_path_4), full_page=True)
        print(f"-> Screenshot saved: {ss_path_4.name}")

        # 5. Open Case Detail (click Assigned Cases tab first, since Alerts Priority Queue tab is default)
        print("\n[UI 5] Opening Case Detail modal...")
        await page.click("button.tab-btn:has-text('Assigned Cases')")
        await page.wait_for_selector("#tab-cases", state="visible", timeout=10000)
        await page.wait_for_timeout(2000)  # Let cases list render from API
        await page.wait_for_selector("button:has-text('View Details')", timeout=12000)
        case_btn = page.locator("button:has-text('View Details')").first
        await case_btn.click()
        await page.wait_for_selector("#case-modal.active", state="visible", timeout=10000)
        await page.wait_for_timeout(2500)  # Allow Chart.js animation
        ss_path_5 = SCREENSHOT_DIR / "05_case_detail_chart_and_breakdown.png"
        await page.screenshot(path=str(ss_path_5), full_page=True)
        print(f"-> Screenshot saved: {ss_path_5.name}")

        # 6. Fill Action Form
        print("\n[UI 6] Filling Follow-up Action form inside Case Detail...")
        alert_opts = page.locator("#action-target-alert option")
        if (await alert_opts.count()) > 1:
            await page.select_option("#action-target-alert", index=1)
        await page.fill("#action-text", "Completed follow-up consultation with individual. Reviewed coping techniques and verified housing security.")
        await page.select_option("#action-channel", "Phone call")
        await page.fill("#action-outcome", "Individual reports feeling calmer; scheduled next follow-up in 7 days.")
        await page.click("#btn-save-action")
        await page.wait_for_timeout(2000)
        ss_path_6 = SCREENSHOT_DIR / "06_action_recorded.png"
        await page.screenshot(path=str(ss_path_6), full_page=True)
        print(f"-> Screenshot saved: {ss_path_6.name}")

        await browser.close()

    print("\n" + "=" * 80)
    print("PLAYWRIGHT SCREENSHOT CAPTURE COMPLETED SUCCESSFULLY!")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}")
    print("=" * 80)


async def main():
    v_user, v_pass = await run_http_verification()
    await run_playwright_screenshots(v_user, v_pass)


if __name__ == "__main__":
    asyncio.run(main())
