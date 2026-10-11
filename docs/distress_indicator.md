# Distress Indicator Specification & Sensitivity Analysis

> [!WARNING]
> **MANDATORY CLINICAL & ETHICAL DISCLAIMER**  
> **"This is an experimental support-prioritisation indicator, not a clinically validated probability of crisis."**  
> This indicator is designed solely as a workflow triage aid for licensed human counsellors and case workers. It does NOT generate psychiatric diagnoses, calculate suicide risk probabilities, or replace professional human clinical judgment.

---

## 1. Design Rationale & Ethical Foundations

Victims of mass violence, hate crimes, and systemic atrocities face multidimensional trauma compounded by ongoing intimidation, legal stressors, and physiological disruption. In low-resource settings where counsellor caseloads are overwhelming, automated systems must never make autonomous life-altering decisions or psychiatric determinations.

Instead, this system computes an **interpretable, deterministic 0–100 Distress Score** designed for **support prioritisation**. The objective is simply: *Who on the counsellor's caseload needs proactive outreach first today?*

### Key Design Principles:
1. **Total Interpretability:** Every point scored maps directly to an identifiable, transparent factor (no "black-box" risk scoring).
2. **Safety Primacy:** Objective threats and perceived lack of safety are weighted heavily (25 points) because physical protection is paramount.
3. **Multi-Modal Triangulation:** Self-reports (stress 1–10) are cross-referenced with physiological sleep indicators, explicit counselling requests, and text-inferred affective cues.
4. **Temporal Sensitivity:** Sudden spikes in distress compared to the victim's previous baseline add priority points to highlight acute decompensation.

---

## 2. Mathematical Formulation & Weighting Schema

The distress score is bounded in $[0, 100]$:

$$\text{Distress Score} = \min\left(100.0, \, S_{\text{stress}} + S_{\text{safety}} + S_{\text{sentiment}} + S_{\text{emotion}} + S_{\text{sleep}} + S_{\text{counsel}} + S_{\text{delta}}\right)$$

### Factor Breakdown & Maximum Point Allocations

| Factor | Parameter / Condition | Weight Formula | Max Points | Rationale |
| :--- | :--- | :--- | :---: | :--- |
| **Self-Reported Stress** | `stress_level` $\in [1, 10]$ | $\frac{\text{stress\_level}}{10.0} \times 30$ | **30 pts** | Direct subjective self-assessment; highest individual weighting. |
| **Safety Concern** | `feels_safe == False` OR `faces_threat == True` | $25.0 \text{ if (not safe or threat) else } 0.0$ | **25 pts** | Immediate physical safety is the prerequisite for all mental health interventions. |
| **Negative Sentiment** | `sentiment_label == 'negative'` | $\text{confidence} \times 15.0$ | **15 pts** | Textual tone indicates affective valence of free-text disclosure. |
| **Distress Emotion** | `emotion_label` $\in$ {fear/worry, sadness, anger} | $\text{confidence} \times 10.0$ | **10 pts** | Fine-grained emotional distress extracted from victim narrative. |
| **Sleep Difficulty** | `sleep_difficulty == True` | $5.0 \text{ if True else } 0.0$ | **5 pts** | Critical somatic indicator of hyperarousal and trauma-related insomnia. |
| **Counselling Request** | `wants_counselling == True` | $5.0 \text{ if True else } 0.0$ | **5 pts** | Explicit cry for human contact; prompts proactive scheduling. |
| **Temporal Delta Spike** | Baseline increase vs previous check-in | $\min(10.0, \, \max(0.0, \, \text{base} - \text{prev\_score}))$ | **10 pts** | Rapid escalation in distress indicates acute situational deterioration. |
| **Theoretical Maximum** | *All factors co-occurring* | Sum of all max weights | **100 pts** | Capped at 100.0 with mathematical consistency. |

---

## 3. Thresholds and Priority Bands

| Score Range | Priority Band | Recommended Counsellor Action | SLA / Response Guideline |
| :---: | :---: | :--- | :--- |
| **0 – 33** | `low` | Routine monitoring; standard follow-up interval (e.g. 7–14 days). | Normal check-in cadence. |
| **34 – 66** | `moderate` | Review check-in free text; offer psychoeducational resources or schedule routine check-in. | Counsellor review within 48 hours. |
| **67 – 100** | `higher` | Priority triage; immediate counsellor outreach; assess immediate physical safety and emergency support. | Same-day review and triage outreach. |

### Justification of Band Cutoffs:
- **0–33 (Low):** An individual with moderate baseline stress (5/10 = 15 pts) and sleep difficulty (5 pts) without safety threats or negative text scores $20.0$, staying safely in the `low` band.
- **34–66 (Moderate):** A person reporting elevated stress (7/10 = 21 pts), negative sentiment (12 pts), and sleep difficulty (5 pts) totals $38.0$, entering the `moderate` band for supportive follow-up.
- **67–100 (Higher):** Any combination involving an acute safety threat ($25$ pts) alongside high stress ($24$ pts) and distressed text ($20$ pts) immediately enters $\ge 69.0$ (`higher`), prompting immediate counsellor attention.

---

## 4. Sensitivity Analysis

The following table demonstrates how changing individual input parameters shifts the final score from a calibrated baseline:

### Baseline Check-in Definition:
- `stress_level`: 3 (9.0 pts)
- `feels_safe`: True (0.0 pts)
- `faces_threat`: False (0.0 pts)
- `sleep_difficulty`: False (0.0 pts)
- `wants_counselling`: False (0.0 pts)
- `sentiment_label`: "neutral" (conf 0.6) (0.0 pts)
- `emotion_label`: "neutral" (conf 0.6) (0.0 pts)
- **Baseline Score:** **9.0 / 100** (Band: `low`)

### Sensitivity Table: Single & Multi-Factor Variations

| Scenario # | Description of Parameter Shift | Absolute Change ($\Delta$) | New Score | New Band | Clinical Triage Implication |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **Base** | Baseline calm check-in | — | **9.0** | `low` | Routine cadence. |
| **1** | Stress increased from 3 to 7 (+4 levels) | +12.0 | **21.0** | `low` | Elevated subjective tension; remains manageable. |
| **2** | Stress increased from 3 to 10 (+7 levels) | +21.0 | **30.0** | `low` | High self-reported stress near the moderate cusp. |
| **3** | Sleep difficulty develops (`True`) | +5.0 | **14.0** | `low` | Somatic symptom noted. |
| **4** | Explicit counselling request (`True`) | +5.0 | **14.0** | `low` | Voluntary outreach flagged. |
| **5** | Negative sentiment detected (conf = 0.85) | +12.8 | **21.8** | `low` | Distressed narrative tone. |
| **6** | Fear/worry emotion detected (conf = 0.90) | +9.0 | **18.0** | `low` | Specific affective fear marker detected. |
| **7** | Safety concern arises (`feels_safe=False`) | +25.0 | **34.0** | `moderate` | **Crosses threshold into moderate band** immediately. |
| **8** | Active threat reported (`faces_threat=True`) | +25.0 | **34.0** | `moderate` | **Crosses threshold into moderate band** immediately. |
| **9** | Stress 7 + Negative text (0.8) + Sleep issues | +29.0 | **38.0** | `moderate` | Multi-symptom distress cluster. |
| **10** | Safety concern + Stress 8 + Negative text | +56.0 | **65.0** | `moderate` | Severe distress bordering on high priority. |
| **11** | Safety concern + Stress 8 + Fear text + Sleep | +65.0 | **74.0** | `higher` | **High priority:** immediate counsellor engagement required. |
| **12** | Acute Jump: Prior score was 20.0, current base 60.0 | +10.0 (delta) | **70.0** | `higher` | Rapid decompensation penalty triggers priority triage. |
| **13** | Worst-Case Convergence (All factors maximized) | +91.0 | **100.0** | `higher` | Max cap enforced; immediate multi-agency emergency safety protocol. |

---

## 5. Summary Breakdown Example

For the canonical test sentence:
> *"I am worried about the upcoming court hearing, and I have not been sleeping properly."*

With inputs:
- `stress_level`: 8 (24.0 pts)
- `feels_safe`: True (0.0 pts)
- `faces_threat`: False (0.0 pts)
- `sleep_difficulty`: True (5.0 pts)
- `wants_counselling`: True (5.0 pts)
- `sentiment`: negative, conf 0.88 (13.2 pts)
- `emotion`: fear/worry, conf 0.85 (8.5 pts)
- `previous_score`: 35.0 (Delta = 55.7 - 35.0 = +20.7 $\rightarrow$ 10.0 pts)

**Calculated Breakdown:**
```json
{
  "stress_points": 24.0,
  "safety_points": 0.0,
  "sentiment_points": 13.2,
  "emotion_points": 8.5,
  "sleep_points": 5.0,
  "counselling_points": 5.0,
  "delta_points": 10.0,
  "raw_delta": 20.7,
  "raw_total": 65.7,
  "final_score": 65.7,
  "band": "moderate"
}
```
*Triage interpretation:* The individual is experiencing acute court-related anticipatory anxiety and insomnia, jumping +20.7 points from their previous baseline. While physical safety is intact (no active threats reported), the acute jump and explicit counselling request trigger alerts for priority counsellor follow-up.
