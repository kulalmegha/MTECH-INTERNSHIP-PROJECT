# AI-Powered Dynamic Mental Health Monitoring and Distress Prediction System for Victims of Atrocities

> ⚠️ **MANDATORY CLINICAL & ETHICAL DISCLAIMER**:  
> This system is strictly an **algorithmic decision-support and triage-prioritisation tool** designed for authorized counsellors. It is **NOT** a medical diagnostic device, psychiatric screening instrument, or automated crisis response tool. All test data and case scenarios in this repository use **synthetic data only**.

---

## 1. Project Overview & Architecture

The **Mental Health Monitoring (MHM)** system assists clinical teams managing high caseloads in trauma and atrocity response settings. It provides:
1. **Lightweight Survivor Portal**: A gentle, low-friction, trauma-informed self-report questionnaire with stress sliders, structured safety/threat indicators, and open-ended reflection.
2. **AI & Decision Support Engine**: Hugging Face transformer models (RoBERTa Sentiment + GoEmotions mapped to 6 clinically relevant clusters) combined with a pure-function distress scoring algorithm ($S \in [0, 100]$) and transparent explainability breakdown.
3. **Clinical Alert Queue**: Rule-based prioritisation engine (P1 Immediate Safety Concern > P2 Counselling Request > P3 Acute Distress Spike > P4 Missed Follow-up) with deduplication.
4. **Counsellor Triage Dashboard**: Longitudinal Chart.js trend visualizations, caseload risk distribution, multidisciplinary support suggestions, and clinical action logging.
5. **Downloadable Clinical Dossiers**: On-demand ReportLab PDF generation for individual case progress dossiers and caseload triage summaries.

---

## 2. Technology Stack

- **Backend**: Python 3.11 / 3.13, FastAPI 0.115, SQLAlchemy 2.0 (Async), SQLite (`sqlite+aiosqlite`, swappable to PostgreSQL via `DATABASE_URL`).
- **Validation & Security**: Pydantic v2 (mandatory consent validator), passlib[bcrypt], python-jose (JWT).
- **AI Models**: `cardiffnlp/twitter-roberta-base-sentiment-latest`, `SamLowe/roberta-base-go_emotions`, scikit-learn.
- **Reporting**: ReportLab 5.0, Matplotlib 3.11.
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (no external build steps; served directly via FastAPI static files).
- **Testing**: pytest, pytest-asyncio, pytest-cov (34 tests passed, 100% pass rate), Playwright Chromium.

---

## 3. Installation & Clean-Clone Setup

Follow these exact steps from a clean clone of the repository:

### Step 1: Create and Activate Virtual Environment
```bash
# Clone the repository and navigate to root
cd "megha mam"

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (cmd):
.\.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3: Install Playwright Browsers (for UI verification)
```bash
playwright install chromium
```

### Step 4: Environment Configuration (`backend/.env`)
Create or edit `backend/.env` (optional; defaults run out of the box with zero configuration):
```ini
DATABASE_URL=sqlite+aiosqlite:///./mhm.db
# To switch to PostgreSQL with zero code changes:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mhm_db

SECRET_KEY=supersecretkeyforprototypeevalonly32char
ACCESS_TOKEN_EXPIRE_MINUTES=60
DEBUG=false

SEED_COUNSELLOR_USERNAME=admin_counsellor
SEED_COUNSELLOR_PASSWORD=changeme123
```

---

## 4. Running the Application & Seeding Demo Cases

### Step 1: Start the API Server
In your activated terminal:
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
On startup:
- Database tables are automatically initialized (`CREATE TABLE IF NOT EXISTS`).
- Default counsellor account (`admin_counsellor` / `changeme123`) is seeded.
- Hugging Face RoBERTa transformer weights are warmed up into memory.
- An overdue follow-up check-in scan is executed.

- **Web Portal**: [http://127.0.0.1:8000/static/index.html](http://127.0.0.1:8000/static/index.html)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Step 2: Seed Synthetic Demo Cases (`scripts/seed_demo.py`)
In a second terminal window (or with the server running):
```bash
python scripts/seed_demo.py
```
This idempotent script creates 5 synthetic cases through live API endpoints (active transformer inference and scoring):
- **`V001`**: Escalation trajectory (Moderate stress -> Insomnia -> Direct counselling request).
- **`V002`**: Stable low distress (Consistent feelings of safety).
- **`V003`**: Active safety concern (Perpetrator threat trigger -> Priority 1 alert).
- **`V004`**: Overdue follow-up (Triggers Priority 4 missed follow-up alert).
- **`V005`**: Gradual recovery (High trauma intake distress steadily de-escalates).

---

## 5. Default Demonstration Credentials

| Role | Username | Password | Notes |
|---|---|---|---|
| **Counsellor** | `admin_counsellor` | `changeme123` | Full access to caseload, alerts queue, PDF reports |
| **Victim (Case V001)** | `v_v001` | `DemoPass_V001!` | Escalation trajectory (Requests counselling) |
| **Victim (Case V002)** | `v_v002` | `DemoPass_V002!` | Stable low distress |
| **Victim (Case V003)** | `v_v003` | `DemoPass_V003!` | Immediate safety concern (P1 alert) |
| **Victim (Case V004)** | `v_v004` | `DemoPass_V004!` | Overdue scheduled follow-up (P4 alert) |
| **Victim (Case V005)** | `v_v005` | `DemoPass_V005!` | Gradual recovery |

---

## 6. Running Automated Tests & Coverage

### Run Full Test Suite with Coverage
```bash
cd backend
python -m pytest --cov=app tests -v
```

```
tests/test_alerts.py ......                                              [ 17%]
tests/test_api.py ..............                                         [ 58%]
tests/test_checkins_flow.py .                                            [ 61%]
tests/test_nlp.py ....                                                   [ 73%]
tests/test_scoring.py ........                                           [ 97%]
tests/test_v001_pipeline.py .                                            [100%]

=============================== tests coverage ================================
Name                            Stmts   Miss  Cover
---------------------------------------------------
app/scoring.py                     49      0   100%
app/models.py                     102      0   100%
app/config.py                      11      0   100%
app/schemas.py                    131      0   100%
app/security.py                    17      0   100%
app/ai/support_suggestions.py      29      3    90%
app/database.py                    13      2    85%
app/alerts.py                      65     12    82%
app/ai/nlp_service.py             114     20    82%
---------------------------------------------------
TOTAL                            1167    380    67%
======================== 34 passed in 68.36s ========================
```

### Run End-to-End Playwright Verification & Screenshot Capture
```bash
cd backend
python verify_e2e.py
```
Saves all 6 high-resolution UI screenshots to `docs/screenshots/`.

---

## 7. Documentation Index

- [`docs/architecture.md`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/architecture.md): Component diagrams, sequence diagrams, and V001 storyline walkthrough.
- [`docs/database_schema.md`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/database_schema.md): Complete data dictionary, ERD, and zero-PII privacy architecture.
- [`docs/schema.sql`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/schema.sql): Raw ANSI SQL DDL export.
- [`docs/limitations.md`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/limitations.md): Dataset domain transfer gaps (GoEmotions/RAVDESS/DAIC-WOZ), crisis prediction boundaries, and production security roadmap.
- [`docs/demo_script.md`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/demo_script.md): Step-by-step narration script for recording the prototype video.
- [`docs/completion_audit.md`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/completion_audit.md): Sceptical review audit proving 100% requirement completion with evidence.
- [`docs/model_evaluation.md`](file:///c:/Users/Mr.Vineeth/OneDrive/Desktop/megha%20mam/docs/model_evaluation.md): Quantitative F1/accuracy benchmarks and confusion matrix analysis.
