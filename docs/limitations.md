# System Limitations, Ethical Boundaries, and Production Roadmap

> ⚠️ **MANDATORY CLINICAL DISCLAIMER**: This system is strictly an **algorithmic decision-support and triage-prioritisation tool** designed for licensed, authorized counsellors. It is **NOT** a medical diagnostic device, psychiatric screening instrument, or automated crisis response tool.

---

## 1. Dataset Limitations & Domain Transfer Mismatch

Machine learning models deployed in mental health prototypes frequently rely on open benchmark datasets. In the context of atrocity survivors and acute trauma, these datasets suffer from fundamental domain transfer gaps:

### A. GoEmotions (Reddit Corpus)
- **Origin**: Curated from public Reddit comments (subreddits: general internet discourse).
- **Mismatch**: Colloquial internet jargon, sarcasm, memes, and casual social venting differ radically from traumatic disclosure, dissociative language, and acute atrocity testimonies.
- **Label Noise**: Crowdsourced MTurk annotators with low inter-rater agreement on nuanced psychological states (e.g., distinguishing remorse from grief, or fear from nervousness).

### B. Speech Emotion Datasets (RAVDESS & CREMA-D)
- **Origin**: Posed recordings by professional actors reciting standardized, semantically neutral scripts with exaggerated emotional inflections.
- **Mismatch**: Traumatized speech often exhibits flat affect, monotone pitch, sudden vocal tremors, or emotional constriction—patterns entirely absent from theatrical acted datasets.

### C. DAIC-WOZ (Clinical Depression & PTSD Interviews)
- **Origin**: Semi-structured interviews conducted by a virtual interviewer (Ellie) with US military veterans and community cohorts.
- **Mismatch**: Focused on standard Western DSM-5 depression and combat PTSD; does not capture cultural trauma idioms, displacement, survivor guilt, or systemic persecution experienced by victims of mass atrocities.

---

## 2. Why the Distress Score is NOT a Crisis Prediction

The composite Distress Score ($S \in [0, 100]$) is an empirical heuristic combining self-reports with NLP text features:

1. **Prioritization vs Prediction**:
   - The score does **NOT** compute the probability of self-harm, suicide, or psychiatric decompensation.
   - It is designed solely to help counsellors sort high caseloads so individuals showing indicators of distress receive outreach sooner.
2. **Dynamic Volatility**:
   - Scores fluctuate based on daily stressors, text length, and phrasing. A high score on a given day may reflect healthy emotional processing or situational frustration rather than escalating pathology.
3. **Absence of Clinical Calibration**:
   - The weights assigned to factors (e.g., $3.0 \times \text{stress}$, $+15$ for negative sentiment) reflect defensible expert heuristics, not statistically fitted regression coefficients from longitudinal clinical outcome trials.

---

## 3. Lack of Longitudinal Clinical Outcome Data

- **No Empirical Ground Truth**: In this prototype, there is no paired ground truth of clinician-administered clinical scales (such as PCL-5, PHQ-9, or CAPS-5) recorded simultaneously with check-ins.
- **Untested Intervention Efficacy**: The system records counsellor actions, but whether early outreach triggered by the alert engine leads to measurable improvements in survivor wellbeing remains an unverified empirical hypothesis requiring institutional review board (IRB) approved clinical trials.

---

## 4. Privacy & Security Limits of the Prototype

While the prototype implements zero-PII storage, bcrypt hashing, and JWT authorization, a production healthcare deployment requires significant additional safeguards:

| Dimension | Prototype Implementation | Required Production Architecture |
|---|---|---|
| **Transport Security** | HTTP localhost (dev mode) | Mandatory TLS 1.3, strict HSTS, certificate pinning |
| **Data at Rest** | SQLite / Local disk plaintext | AES-256 transparent database encryption, encrypted volume blocks |
| **Field-level Privacy** | Free-text stored in DB column | Zero-knowledge client-side encryption; homomorphic search or pseudonymized tokenization |
| **Audit Logging** | stdout / application logger | Tamper-evident, append-only, cryptographic audit logs compliant with HIPAA / GDPR |
| **Consent Lifecycle** | Single boolean CHECK constraint | Dynamic consent management (consent revocation, granular data-sharing preferences, right to erasure) |
| **Regulatory & Ethics** | Synthetic demo evaluation | IRB ethics approval, clinical safety committee review, CE / FDA Software-as-a-Medical-Device (SaMD) clearance |

---

## 5. Future Scope & Roadmap

1. **Multimodal Speech Emotion Analysis**:
   - Integrate acoustic feature extraction (Wav2Vec 2.0 / HuBERT) for voice check-ins to support non-literate or visually impaired survivors.
2. **Multilingual & Cultural Adaptation**:
   - Fine-tune multilingual transformer models (e.g. XLM-RoBERTa) on domain-specific idioms of distress across regional dialects and languages.
3. **Database Migration to PostgreSQL**:
   - Transition to multi-region PostgreSQL with read replicas, row-level security (RLS), and automated disaster recovery via the pre-configured `DATABASE_URL` environment variable.
4. **Automated Clinical Trial Validation**:
   - Conduct prospective observational studies with humanitarian NGOs to validate the predictive validity of the alert engine against standardized clinician ratings.
