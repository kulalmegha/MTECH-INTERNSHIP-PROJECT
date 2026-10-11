# MHM – AI-Powered Dynamic Mental Health Monitoring and Distress Prediction System

> **A Clinical Support-Prioritisation Tool for Authorised Counsellors Working with Victims of Atrocities**
> 
> ⚠️ **Clinical & Ethical Disclaimer**: This system is strictly a **decision-support and prioritization tool** designed for authorized counsellors. It is **NOT** a medical diagnostic tool. All test data and simulated case scenarios use synthetic data only.

---

## 1. System Overview & Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Runtime** | Python 3.11 / 3.13 | Native async execution |
| **Web Framework** | FastAPI 0.111 | OpenAPI / Swagger docs, async endpoints, static files |
| **ORM & DB** | SQLAlchemy 2.0 (Async) | SQLite (`sqlite+aiosqlite`) default, swappable to PostgreSQL via `DATABASE_URL` |
| **Validation** | Pydantic v2 | Strict schema validation, consent enforcement |
| **Auth & Security** | JWT (python-jose) + bcrypt | Role-based authorization (`counsellor`, `victim`), zero PII |
| **NLP AI Engine** | Hugging Face Transformers | RoBERTa Sentiment (`cardiffnlp/twitter-roberta-base-sentiment-latest`) + GoEmotions RoBERTa (`SamLowe/roberta-base-go_emotions`) mapped to 6 primary clinical groups with offline fallback |
| **Testing** | pytest + pytest-asyncio (33 tests) | Isolated test suites with SQLite StaticPool |
| **Browser Testing** | Playwright Chromium | Automated end-to-end verification and UI screenshot capture |
| **Frontend UI** | HTML5, CSS3, Vanilla JavaScript | Responsive clinical dashboard, Chart.js visualizations |

---

## 2. Architecture & Data Model

### Database Tables (Zero-PII Design)
- **`users`**: `id`, `username`, `password_hash`, `role` (`'counsellor' | 'victim'`), `case_id` (FK to cases for victims), `created_at`
- **`cases`**: `id`, `case_code` (unique pseudonymous identifier), `counsellor_id` (FK to users), `consent_given` (strict CHECK constraint `consent_given = 1`), `follow_up_interval_days`, `next_follow_up_due`, `status` (`'active' | 'closed'`), `created_at`
- **`checkins`**: `id`, `case_id` (FK to cases), `timestamp`, `stress_level` (1–10), `feels_safe` (bool), `faces_threat` (bool), `sleep_difficulty` (bool), `wants_counselling` (bool), `free_text` (optional), `sentiment_label`, `sentiment_score`, `emotion_label`, `emotion_score`, `distress_score` (0–100), `score_breakdown` (JSON explainability object)
- **`alerts`**: `id`, `case_id` (FK), `checkin_id` (nullable FK), `rule_triggered` (`'safety_concern' | 'counselling_request' | 'distress_increase' | 'missed_followup'`), `priority` (1–4), `status` (`'open' | 'reviewed' | 'resolved'`), `created_at`, `reviewed_at`, `resolved_at`, `notes`
- **`actions`**: `id`, `alert_id` (FK to alerts), `case_id` (FK to cases), `counsellor_id` (FK to users), `action_taken` (text), `contact_channel` (phone, in-person, etc.), `outcome` (text), `created_at`
- **`support_tags`**: `id`, `case_id` (FK to cases), `tag` (`'housing' | 'legal' | 'medical' | 'psychological' | 'family' | 'protection'`), `suggested_by_system` (bool), `confirmed_by_counsellor` (bool), `created_at`

---

## 3. Distress Scoring Algorithm & Explainability

The composite distress score $S \in [0, 100]$ is computed using multi-dimensional evidence:

$$S = \min\left(100, \max\left(0, F_{\text{stress}} + F_{\text{safety}} + F_{\text{sentiment}} + F_{\text{emotion}} + F_{\text{sleep}} + F_{\text{counselling}} + F_{\Delta}\right)\right)$$

### Point Breakdown
1. **Stress Level ($F_{\text{stress}}$)**: $3.0 \times \text{stress\_level}$ (Range: 3 to 30 points).
2. **Safety & Threat Concerns ($F_{\text{safety}}$)**:
   - If `feels_safe = False`: $+15$ points.
   - If `faces_threat = True`: $+20$ points (Combined max $+35$).
3. **NLP Sentiment ($F_{\text{sentiment}}$)**:
   - `negative`: $+15.0 \times \text{confidence}$
   - `neutral`: $+3.0 \times \text{confidence}$
   - `positive`: $-10.0 \times \text{confidence}$
4. **NLP Emotion ($F_{\text{emotion}}$)**:
   - `fear/worry`: $+15.0 \times \text{confidence}$
   - `sadness`: $+12.0 \times \text{confidence}$
   - `anger`: $+10.0 \times \text{confidence}$
   - `neutral`: $0$
   - `joy`: $-8.0 \times \text{confidence}$
   - `other`: $+5.0 \times \text{confidence}$
5. **Sleep & Self-Identified Support**:
   - `sleep_difficulty = True`: $+5$ points.
   - `wants_counselling = True`: $+5$ points.
6. **Dynamic Delta Adjustment ($F_{\Delta}$)**:
   - If $\Delta = S_{\text{current}} - S_{\text{prev}} \ge +15$: $+10$ points (acute escalation).
   - If $\Delta \le -15$: $-5$ points (sustained de-escalation).

### Risk Bands
- **Low**: $0.0 \le S < 35.0$
- **Moderate**: $35.0 \le S < 70.0$
- **High**: $70.0 \le S \le 100.0$

Every check-in stores its exact `score_breakdown` JSON in the database for transparent counsellor review.

---

## 4. Alert Engine & Prioritization Rules

Alerts are automatically triggered during check-ins and through scheduled follow-up scans:

| Priority | Rule ID | Trigger Condition | Severity / Urgency |
|---|---|---|---|
| **P1** | `safety_concern` | `feels_safe = False` OR `faces_threat = True` | Critical immediate safety threat |
| **P2** | `counselling_request` | `wants_counselling = True` | Direct request for clinical intervention |
| **P3** | `distress_increase` | Raw score increase $\ge 20$ points from previous check-in | Rapid psychological escalation |
| **P4** | `missed_followup` | Check-in overdue past `next_follow_up_due` | Welfare check required |

*Alerts deduplicate against existing open alerts for the same rule on the same case.*

---

## 5. Setup & Installation

### 1. Environment Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration (`.env`)
```ini
DATABASE_URL=sqlite+aiosqlite:///./mhm.db
# To switch to PostgreSQL (zero code changes):
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mhm_db

SECRET_KEY=supersecretkeyforprototypeevalonly32char
ACCESS_TOKEN_EXPIRE_MINUTES=60
DEBUG=false

SEED_COUNSELLOR_USERNAME=admin_counsellor
SEED_COUNSELLOR_PASSWORD=changeme123
```

### 3. Launch Development Server
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Web Application: **http://127.0.0.1:8000/static/index.html**
- Interactive Swagger API: **http://127.0.0.1:8000/docs**

---

## 6. Verification & Automated Testing

### Backend Unit & Integration Tests (33 Passed)
```bash
python -m pytest tests -v
```

```
tests/test_alerts.py .................................. [ 18%]
tests/test_api.py ..................................... [ 60%]
tests/test_checkins_flow.py ........................... [ 63%]
tests/test_nlp.py ..................................... [ 75%]
tests/test_scoring.py ................................. [100%]
============================= 33 passed in 43.18s =============================
```

### Full End-to-End Test & Screenshot Capture
Run the comprehensive verification script which tests the entire lifecycle (case creation, multi-point check-ins, NLP evaluation, alerts queue, alert actions, admin follow-up scan, and Playwright UI navigation):
```bash
python verify_e2e.py
```

### Captured Screenshots (`docs/screenshots/`)
1. `01_login_page.png` — Dual-role authentication portal (Counsellor / Victim).
2. `02_victim_checkin_form.png` — Simple, safe, trauma-informed self-report questionnaire.
3. `03_victim_confirmation.png` — Post-submission reassurance and emergency contact resources.
4. `04_counsellor_dashboard.png` — Priority alert queue, caseload metrics, and follow-up tracker.
5. `05_case_detail_chart_and_breakdown.png` — Longitudinal distress trajectory chart, explainability breakdown, and AI support suggestions.
6. `06_action_recorded.png` — Case action logging and clinical alert resolution modal.
