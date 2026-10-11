# System Architecture & Data Flow

## 1. System Component Architecture

```mermaid
graph TD
    subgraph ClientLayer["Client & User Interfaces"]
        C1["Victim Self-Report Portal<br/>(Plain HTML/CSS/JS)"]
        C2["Counsellor Triage Dashboard<br/>(Chart.js, Plain HTML/CSS/JS)"]
    end

    subgraph APILayer["FastAPI Application Core"]
        R1["Auth Router<br/>(JWT + bcrypt)"]
        R2["Cases Router<br/>(Role Guards + Consent Enforcement)"]
        R3["Check-ins Router<br/>(NLP Pipeline + Scoring Trigger)"]
        R4["Alerts Router<br/>(Priority Queue + Review/Resolve)"]
        R5["Dashboard Router<br/>(Caseload Summary Metrics)"]
        R6["Reports Router<br/>(ReportLab PDF Dossiers)"]
        R7["Admin Router<br/>(Follow-up Scheduled Sweeper)"]
    end

    subgraph AIEngine["AI & Decision Support Layer"]
        NLP["Transformer NLP Service<br/>(RoBERTa Sentiment + GoEmotions Grouping)"]
        SC["Pure Function Distress Scoring Engine<br/>(Multi-Factor Mathematical Formulation)"]
        AL["Rule-Based Clinical Alert Engine<br/>(P1–P4 Priority & Deduplication)"]
        SU["Support Suggestions Heuristic<br/>(Keyword & Structured Flag Mapper)"]
    end

    subgraph PersistenceLayer["Storage & Data Persistence"]
        DB[("SQLAlchemy 2.0 Async ORM<br/>SQLite / PostgreSQL")]
        PDF["In-Memory PDF Buffer<br/>(Matplotlib + ReportLab)"]
    end

    C1 -->|POST /auth/login<br/>POST /checkins| R1
    C1 -->|POST /checkins| R3
    C2 -->|GET /dashboard/summary<br/>GET /alerts<br/>POST /cases| R5
    C2 -->|PATCH /alerts/:id/review<br/>POST /alerts/:id/actions| R4
    C2 -->|GET /cases/:code/report<br/>GET /reports/summary| R6

    R3 --> NLP
    R3 --> SC
    R3 --> AL
    R3 --> SU

    R3 --> DB
    R4 --> DB
    R2 --> DB
    R6 --> DB
    R6 --> PDF
```

---

## 2. End-to-End Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor V as Victim
    participant API as FastAPI Backend
    participant NLP as RoBERTa NLP Models
    participant Score as Scoring Engine
    participant Alert as Alert Engine
    participant DB as Database (SQLAlchemy)
    actor C as Clinical Counsellor

    Note over C,API: Case Enrollment & Informed Consent
    C->>API: POST /cases {case_code: "V001", consent_given: true, interval: 5}
    API->>DB: INSERT into cases, INSERT victim user (bcrypt hash)
    API-->>C: Returns 201 Created + One-Time Password

    Note over V,API: Victim Check-in Submission
    V->>API: POST /checkins {stress: 8, safe: true, sleep: true, counselling: true, text: "..."}
    API->>NLP: analyze_text(text)
    NLP-->>API: Sentiment: negative (0.84), Emotion: fear/worry (0.78)
    API->>DB: Fetch previous check-in for Case V001 (for delta calculation)
    API->>Score: compute_distress_score(stress, flags, sentiment, emotion, delta)
    Score-->>API: Score: 78.4, Band: 'higher', Breakdown: {...}
    API->>Alert: evaluate_alerts(checkin, previous_score)
    Alert-->>API: Triggers P2 Alert ('counselling_request')
    API->>DB: INSERT into checkins, INSERT into alerts, UPDATE next_follow_up_due
    API-->>V: Returns 201 Created + Reassurance Confirmation

    Note over C,API: Counsellor Triage & Clinical Action
    C->>API: GET /alerts?status=open
    API->>DB: SELECT alerts ORDER BY priority ASC, created_at ASC
    API-->>C: Returns P2 Counselling Request for Case V001
    C->>API: PATCH /alerts/:id/review
    API->>DB: UPDATE alerts SET status='reviewed', reviewed_at=NOW
    C->>API: POST /alerts/:id/actions {action: "Conducted grounding phone call", resolve: true}
    API->>DB: INSERT into actions, UPDATE alerts SET status='resolved'
    API-->>C: Returns 201 Created

    Note over C,API: Downloadable Clinical Dossier
    C->>API: GET /cases/V001/report
    API->>DB: SELECT case, checkins, alerts, actions
    API->>API: Compile Matplotlib chart & ReportLab PDF
    API-->>C: Returns application/pdf ("case_report_V001.pdf")
```

---

## 3. Case V001 Clinical Workflow Walkthrough

Case **V001** illustrates the dynamic escalation of an individual navigating post-trauma legal processes:

### Check-in 1: Baseline Stability (Day -10)
- **Input**: Stress 5/10, `feels_safe=True`, `faces_threat=False`, `sleep_difficulty=False`, `wants_counselling=False`. Text: *"Managing daily routines okay. Experiencing mild fatigue at work, but generally coping with tasks."*
- **NLP Analysis**: Neutral sentiment, low emotional activation.
- **Scoring Output**: Score = `15.0` (Low band). Points breakdown: Stress (15.0), Safety (0.0), Sleep (0.0), Counselling (0.0).
- **Outcome**: No alerts triggered. Case remains on routine 5-day monitoring schedule.

### Check-in 2: Acute Escalation & Sleep Disturbance (Day -5)
- **Input**: Stress 7/10, `sleep_difficulty=True`, text: *"Waking up multiple times at night with persistent worry and intrusive thoughts about the upcoming legal hearing. Feeling tense throughout the day."*
- **NLP Analysis**: RoBERTa identifies negative sentiment and `fear/worry` emotion.
- **Scoring Output**: Score jumps to `50.0` (Moderate band). Sleep points (+5) activated. Delta point adjustment applied (+10 for $\Delta \ge 15$).
- **Outcome**: The longitudinal trendline reflects an upward risk vector. Counsellor monitors case trajectory.

### Check-in 3: Direct Request for Clinical Intervention (Day -1)
- **Input**: Stress 8/10, `sleep_difficulty=True`, `wants_counselling=True`. Text: *"The anxiety is feeling overwhelming this week. I am having panic symptoms in crowds and would really appreciate speaking to a counsellor as soon as possible."*
- **NLP Analysis**: High confidence negative sentiment; elevated panic/worry markers.
- **Scoring Output**: Score = `46.0` (Moderate/Elevated). Counselling points (+5) added.
- **Alert Engine Trigger**:
  - Rule 2 (`counselling_request`) triggered with Priority **P2 (Urgent)**.
  - Reason: *"Individual explicitly requested psychological/support counselling."*
- **Support Suggestion Engine**: Automatically flags `Psychological Support & Counselling` and `Sleep Hygiene & Somatic Care`.
- **Counsellor Action**:
  1. Counsellor observes P2 alert in queue.
  2. Marks alert as `reviewed`.
  3. Conducts clinical telephone consultation and schedules an in-person grounding session.
  4. Logs action note and resolves alert.
- **Reporting**: Downloads PDF dossier (`GET /cases/V001/report`) documenting the complete trajectory from initial intake to resolution.
