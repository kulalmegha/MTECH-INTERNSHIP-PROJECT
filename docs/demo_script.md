# Step-by-Step Demo Video Narration Script

> **Project**: AI-Powered Dynamic Mental Health Monitoring and Distress Prediction System for Victims of Atrocities  
> **Target Video Length**: 5–7 Minutes  
> **Audience**: Clinical Supervisors, Humanitarian Evaluators, and Technical Reviewers

---

## Scene 1: Introduction & Ethical Framing (0:00 – 0:45)
**Screen**: Title slide / Landing page with prominent ethical banner.  
**Speaker Narration**:  
> "Welcome to this demonstration of the Mental Health Monitoring and Distress Prediction prototype.  
> Before diving into the technology, we must emphasize the fundamental design principle of this system: this is strictly a clinical support-prioritisation tool for authorised counsellors—it is NOT a medical diagnostic tool or crisis prediction engine.  
> In mass-casualty and atrocity response contexts, clinical teams face overwhelming caseloads with limited human resources. Our goal is to augment counsellors with transparent, explainable decision-support so that individuals signaling acute distress or safety concerns are surfaced immediately.  
> All data demonstrated today is 100% synthetic."

---

## Scene 2: Dual-Role Authentication & Privacy Guardrails (0:45 – 1:30)
**Screen**: `http://127.0.0.1:8000/static/index.html` (Login Screen).  
**Actions**: Show login interface, explain zero-PII architecture.  
**Speaker Narration**:  
> "We begin at the login portal. Notice that the system enforces strict role-based isolation between clinical counsellors and victims.  
> Under our zero-PII architecture, victims never enter their real names, phone numbers, or residential addresses. Each case is identified solely by a pseudonymous case code—such as `V001`.  
> Furthermore, informed consent is mandatory. If consent is not explicitly recorded, the API strictly rejects case enrollment at both the Pydantic validator and the database constraint layer."

---

## Scene 3: Victim Check-In Portal & NLP Analysis (1:30 – 2:45)
**Screen**: Log in as `v_v001` with `DemoPass_V001!`.  
**Actions**: Walk through the self-report slider (Stress Level), toggle the structured indicators (Safety, Threat, Sleep, Counselling Request), and enter an open-ended reflection.  
**Speaker Narration**:  
> "Now, we log in as survivor `v_v001`. The victim portal is designed to be gentle, lightweight, and low-friction.  
> The individual answers five simple structured questions: their subjective stress rating from 1 to 10, whether they feel safe in their current environment, whether they are experiencing active threats or intimidation, sleep disturbance, and whether they want to request counselling.  
> An optional free-text box allows them to share reflections in their own words.  
> When the victim submits this check-in, our Hugging Face RoBERTa transformer pipeline runs on the server. It classifies sentiment and maps 27 nuanced GoEmotions categories into six clinically relevant clusters: fear/worry, sadness, anger, joy, neutral, or other.  
> After submission, the survivor sees immediate confirmation and standard local emergency contact numbers."

---

## Scene 4: Counsellor Dashboard & Alert Prioritisation (2:45 – 4:00)
**Screen**: Log out and log in as `admin_counsellor` with `changeme123`.  
**Actions**: View the caseload metrics cards, explore the **Alerts Priority Queue**, and filter alerts.  
**Speaker Narration**:  
> "Switching to the counsellor view, we arrive at the clinical triage dashboard.  
> At a glance, the counsellor sees their caseload metrics: active cases, open alerts, overdue follow-ups, and high-band cases.  
> Look at the Alerts Priority Queue. Alerts are automatically ranked by clinical urgency:  
> - Priority 1: Immediate Safety Concerns (if an individual reports feeling unsafe or threatened).  
> - Priority 2: Direct Requests for Counselling.  
> - Priority 3: Acute Distress Increases (where the composite score jumped by 20 points or more).  
> - Priority 4: Missed Scheduled Follow-ups.  
> Deduplication ensures counsellors are not flooded with redundant notifications for the same case."

---

## Scene 5: Case V001 Trajectory & Explainability Breakdown (4:00 – 5:15)
**Screen**: Click "View Details" on Case `V001`. Modal opens with Chart.js trendline.  
**Actions**: Trace the 3 check-ins on the graph. Expand the "Breakdown" button for check-in 3.  
**Speaker Narration**:  
> "Let’s open Case `V001`. Here we see their longitudinal distress trajectory plotted across low, moderate, and high risk bands.  
> Over the past 10 days, this individual started at a moderate stress level of 5. By day 5, their worry and insomnia increased. By day 9, they reached out requesting direct counselling.  
> Crucially, our system is not a black box. Clicking 'Breakdown' reveals the exact mathematical point contributions: 24 points from subjective stress, 5 points from sleep disturbance, 5 points from the counselling request, and points from NLP negative sentiment and fear/worry classification.  
> Below the chart, our support recommendation engine automatically flags multidisciplinary resources—in this case, Psychological Support and Sleep Somatic Care."

---

## Scene 6: Logging Clinical Outreach & Resolving Alerts (5:15 – 6:15)
**Screen**: Action form inside the Case Detail modal.  
**Actions**: Select the open alert, select "Phone Call", type intervention note and outcome, check "Mark resolved", and submit.  
**Speaker Narration**:  
> "The counsellor can immediately record their clinical intervention.  
> Here, we select the open counselling request alert, document that a phone consultation was conducted, review grounding exercises, and record the outcome.  
> Submitting this form persists an immutable audit entry and transitions the alert status from open to resolved."

---

## Scene 7: PDF Progress Dossier & Summary Report (6:15 – 7:00)
**Screen**: Click "📄 Download PDF" in the modal, then "📄 Caseload PDF" in the header. Show generated PDFs.  
**Actions**: Open the downloaded PDF in viewer, showcasing the title, trend chart image, check-in history table, alert records, action log, and the prominent clinical disclaimer footer.  
**Speaker Narration**:  
> "Finally, accountability and record-keeping are built in.  
> With one click, the counsellor generates a downloadable PDF dossier containing the full longitudinal chart, tabulated check-in history, alert logs, actions taken, and our mandatory ethical disclaimer footer.  
> They can also download an overall caseload risk summary report.  
> This concludes our walkthrough of the Mental Health Monitoring system—providing trauma-informed, privacy-preserving triage support for counsellors when it matters most."
