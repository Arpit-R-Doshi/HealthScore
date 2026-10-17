# HealthScore Clinical Semantic Validation Report (Phase 2 — Stage B)

**Document Version:** 1.0  
**Evaluation Date:** October 2026  
**Evaluation Scope:** Clinical Feature Lineage Audit, Runtime Inference Semantics, Adversarial Challenge Suite, and Gold-Standard Protocol  
**Repository Branch:** `feature/ml-pipeline-rebuild`  
**Compliance Mandate:** Phase 2 Research Hardening Protocol  

---

## Executive Summary & Status Declaration

> [!CAUTION]
> **CLINICAL SEMANTIC VALIDATION STATUS: NOT YET ESTABLISHED**
> 
> Passing unit tests and synthetic challenge suites verify code execution, syntax parsing, and boundary handling. **They do not constitute clinical validation.**
> 
> Because genuine, independently annotated clinical medical records and double-reviewed gold-standard patient descriptions are currently unavailable, HealthScore's clinical semantic validity remains **unvalidated**. The free-text regex NLP pathway functions solely as an unaccredited heuristic proxy. The new structured intake pathway establishes semantic interface alignment, but empirical concordance with clinician chart extraction requires formal clinical trials or retrospective electronic health record (EHR) adjudication.

---

## B1. End-to-End Feature Lineage Audit

The table below documents the exact lineage for every input feature in HealthScore's predictive architecture, contrasting its training derivation in the MEPS Full-Year Consolidated Files (`HC-251` / `HC-256`) against runtime intake mechanisms.

| Feature Name | MEPS Source Variable(s) | MEPS Coding Semantics & Skip Patterns | Exact Phase 1 Training Formula | Runtime Generation (Free-Text vs Structured) | Distinguishability (Affirmed / Negated / Historical / Uncertain / Inapp) | Semantic Match Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`AGE23X` / `AGE24X`** | `AGE23X` / `AGE24X` | Age at end of round 5/3 (0–85; top-coded at 85 by AHRQ; inapplicable `-1` dropped). | Continuous numeric float $\ge 0$. Top-coded at 85. | Direct numeric input (`data['age']`). Enforces range $[0, 125]$. **Age Policy:** Runtime top-codes model covariate at 85 (`min(float(age), 85.0)`), preserving biological age in audit diagnostics while guaranteeing exact support parity with MEPS training bounds $[0, 85]$. | Affirmative continuous value. Inapplicable / negative values rejected with `ValueError`. | **COMPUTATIONAL MAPPING & TOP-CODING ALIGNED AT 85.0 (PRESERVES TRUE INTAKE AGE IN AUDIT)** |
| **`Gender_Male`** | `SEX` | 1 = Male, 2 = Female. | `1 if SEX == 1 else 0` | Mapped from string (`'male'`, `'female'`). **Strict Input Policy:** Missing or unparseable gender strictly rejected with `ValueError`. No silent default to male. | Binary indicator. Missing input is rejected rather than imputed. | **COMPUTATIONAL MAPPING ALIGNED (STRICT REJECTION POLICY)** |
| **`Cardio_ACG`** | `HIBPDX`, `CHDDX`, `MIDX`, `STRKDX` | Doctor-diagnosed conditions ($\ge 18$, `-1` inapplicable). `ANGIDX` omitted in Phase 1 training line 168. | `HIBPDX + CHDDX + MIDX + STRKDX` (integer sum, range 0–4). | **Free-Text:** Regex keyword match for stroke/MI/CAD/HTN with clause negation. <br>**Structured:** Exact Phase 1 integer sum of affirmed conditions. Unmapped `angina` quarantined in audit metadata. | **Free-Text:** Cannot separate family history, historical stroke, or uncertain angina.<br>**Structured:** Separates affirmed, negated, historical, and uncertain; enforces age $\ge 18$. | **Free-Text:** Heuristic Proxy.<br>**Structured:** Computational feature mapping aligned; clinical semantic validity pending. *(Note: Not a proprietary ACG)* |
| **`Metabolic_ACG`** | `DIABDX_M18`, `CHOLDX` | `DIABDX_M18` (diabetes $\ge 18$), `CHOLDX` (high cholesterol $\ge 18$). 1 = Yes, 2 = No; `-1` = Inapplicable. | `DIABDX_M18 + CHOLDX` (integer sum, range 0–2). | **Free-Text:** Regex for diabetes/cholesterol keywords. <br>**Structured:** Exact Phase 1 integer sum. Unmapped `thyroid_disorder` quarantined. | **Free-Text:** Fails on family diabetes history.<br>**Structured:** Distinguishes active patient diabetes from family history. Enforces age $\ge 18$. | **Free-Text:** Heuristic Proxy.<br>**Structured:** Computational feature mapping aligned; clinical semantic validity pending. |
| **`Respiratory_ACG`** | `CHBRON` / `CHBRON31`, `EMPHDX`, `ASTHDX` | `CHBRON` (bronchitis $\ge 18$), `EMPHDX` ($\ge 18$), `ASTHDX` (all ages $0+$). 1 = Yes, 2 = No. | `ASTHDX + EMPHDX + CHBRON31` (integer sum, range 0–3). | **Free-Text:** Regex for copd/emphysema/bronchitis/asthma. <br>**Structured:** Exact Phase 1 integer sum. | **Free-Text:** Childhood asthma 30 yrs ago falsely scores as active acute asthma.<br>**Structured:** Historical resolved asthma separated from active chronic COPD. | **Free-Text:** Heuristic Proxy.<br>**Structured:** Computational feature mapping aligned; clinical semantic validity pending. |
| **`Oncology_ACG`** | `CANCERDX` | Ever told had cancer/malignancy (all ages $0+$). 1 = Yes, 2 = No. | `1 if CANCERDX==1 else 0` (binary indicator, range 0–1). | **Free-Text:** Regex for cancer/malignancy keywords. <br>**Structured:** Exact Phase 1 binary indicator. | **Free-Text:** Past benign tumors or family cancer trigger false positives.<br>**Structured:** Separates active malignancy from historical remission. | **Free-Text:** Heuristic Proxy.<br>**Structured:** Computational feature mapping aligned; clinical semantic validity pending. |
| **`Musculoskeletal_ACG`** | `ARTHDX`, `JTPAIN31_M18` | `ARTHDX` (arthritis $\ge 18$), `JTPAIN31_M18` (joint pain $\ge 18$). 1 = Yes, 2 = No. | `ARTHDX + JTPAIN31_M18` (integer sum, range 0–2). | **Free-Text:** Regex for arthritis/osteoarthritis/joint pain. <br>**Structured:** Exact Phase 1 integer sum. | **Free-Text:** General back pain triggers arthritis flag.<br>**Structured:** Requires affirmed arthritis diagnosis or joint pain; rejects age $< 18$. | **Free-Text:** Heuristic Proxy.<br>**Structured:** Computational feature mapping aligned; clinical semantic validity pending. |
| **`Psychiatric_ACG`** | `ADDPRS42`, `ADHDADDX` | `ADDPRS42` (depressive symptoms past 2 weeks, adults $\ge 18$, values 1–3); `ADHDADDX` (ADHD, children 5–17, value 1). | `ADDPRS42 + ADHDADDX` (integer sum, range 0–2). | **Free-Text:** Regex for depression/anxiety/bipolar/ADHD. <br>**Structured:** Exact Phase 1 integer sum. Unmapped `bipolar`, `anxiety` quarantined in audit metadata. | **Free-Text:** Acute bereavement/situational anxiety triggers chronic psych cluster.<br>**Structured:** Validates age applicability (pediatric ADHD vs adult depression). | **Free-Text:** Heuristic Proxy.<br>**Structured:** Computational feature mapping aligned; clinical semantic validity pending. |
| **`Comorbidity_Count`** | Derived from 6 condition clusters | Count of clusters with score $> 0$ (range 0–6). | $\sum \mathbb{I}(\text{Cluster}_k > 0)$ | Derived directly from the 6 condition scores. | Derived integer. Reflects intake quality. | **EXACT COMPUTATIONAL MATCH** (Inherits intake limitations) |
| **`Multimorbidity_Penalty`** | Derived from `Comorbidity_Count` | Quadratic scaling of comorbidity count (range 0–36). | $(\text{Comorbidity\_Count})^2$ | Derived directly. | Exact quadratic calculation. | **EXACT COMPUTATIONAL MATCH** |
| **`Age_x_Comorbidity`** | Derived from `Age` and `Comorbidity_Count` | Interaction term between age and comorbidity count. | $\text{Age} \times \text{Comorbidity\_Count}$ | Derived directly. | Exact multiplication. | **EXACT COMPUTATIONAL MATCH** |
| **`Frailty_Index`** | `RTHLTH42`, `ANYLMI23`/`24`, `COGLIM42` | Self-administered questionnaire (SAQ) & limitation items: General health (1=Exc to 5=Poor), physical limitation (1=Yes), cognitive limitation (1=Yes). | $\text{Health} + 2\times\text{PhysLim} + 2\times\text{CogLim}$ | **Observable Model:** Imputed using conditional expectation lookup table $\mathbb{E}[\text{Frailty} \mid \text{AgeGroup}, \text{Comorb}]$. | Full models: Imputed if unobserved. Free text heuristic keywords (`"wheelchair"`, `"dementia"`) partially infer. | **DIVERGENT GENERATION PROCESS** (Population expectation vs observed clinical status) |
| **`Age_x_Frailty`** | Derived from `Age` and `Frailty_Index` | Interaction term. | $\text{Age} \times \text{Frailty\_Index}$ | Derived directly from age and imputed/observed frailty. | Continuous interaction. | **DERIVED MATCH** |
| **`K6SUM42`** | `K6SUM42` | Kessler 6 Non-Specific Psychological Distress Scale (sum 0–24, adults $\ge 18$). | Continuous score $[0, 24]$. | **Observable Model:** Imputed via conditional expectation lookup table $\mathbb{E}[\text{K6} \mid \text{AgeGroup}, \text{Comorb}]$. | Numeric if provided; otherwise conditional demographic imputation. | **DIVERGENT GENERATION PROCESS** |

> [!IMPORTANT]
> **Proprietary Grouper Clarification:**
> The feature names `Cardio_ACG`, `Metabolic_ACG`, `Respiratory_ACG`, `Oncology_ACG`, `Musculoskeletal_ACG`, and `Psychiatric_ACG` are **heuristic internal cluster labels**. They are **NOT** generated by the Johns Hopkins Adjusted Clinical Groups (ACG) System, 3M Clinical Risk Groups (CRG), or any proprietary clinical grouper software. They are simple deterministic heuristic groupings of standard MEPS survey items.

---

## B2. Structured Clinical Intake Pathway

To address the fundamental semantic divergence between MEPS survey questions and free-text regex parsing, HealthScore has implemented an optional **structured clinical intake pathway** (`parse_structured_clinical_conditions`) in `ml_model/risk_engine.py`.

### Architectural Capabilities
1. **Explicit Condition Categorization:**
   Supports per-condition structured records:
   ```json
   {
     "conditions_structured": {
       "hypertension": {"status": "affirmed"},
       "stroke": {"status": "negated"},
       "asthma": {"status": "historical", "notes": "resolved childhood asthma"},
       "angina": {"status": "uncertain", "notes": "rule-out workup"}
     }
   }
   ```
2. **Strict Status Semantics:**
   - `affirmed` / `active`: Confirmed active clinical diagnosis; contributes to comorbidity scoring.
   - `negated` / `absent`: Clinically confirmed absence; assigned score 0.
   - `historical` / `resolved`: Tracked for record, but does **not** silently escalate acute comorbidity spending scores without active symptoms.
   - `uncertain` / `rule_out`: Preserved as diagnostic workup; does **not** fabricate a positive chronic comorbidity.
   - `unmentioned`: Explicitly tracked in `unmentioned_clusters`; **never silently converted to confirmed negatives**.
3. **Age-Applicability Enforcement:**
   Enforces official MEPS survey skip patterns:
   - Chronic adult conditions (`hypertension`, `cad`, `angina`, `heart_attack`, `stroke`, `diabetes`, `hyperlipidemia`, `copd`, `chronic_bronchitis`, `arthritis`, `depression`) are flagged as inapplicable for patients under 18.
   - Pediatric ADHD is flagged as inapplicable for patients $\ge 18$ or $< 5$.
4. **Insufficient Input Rejection:**
   When `require_structured_inputs=True`, requests with empty or unmentioned clinical conditions are rejected with status `"insufficient_input"` rather than assigning an unearned zero-cost healthy score.

---

## B3. Adversarial Parser Evaluation Suite Results

An adversarial software challenge suite consisting of 21 test cases was executed against the regex parser and structured intake engine across 10 distinct error categories (`ml_model/tests/test_phase2_clinical_semantics.py`).

### Summary of Challenge Test Results

| Error Category | Challenge Case Example | Free-Text Regex Parser Behavior | Structured Intake Pathway Behavior | Test Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Individual Concepts** | "patient diagnosed with malignant neoplasm cancer" | Correctly fires oncology cluster (score 1). | Correctly maps to MEPS concept `CANCERDX`. | **PASSED** |
| **2. Affirmed vs Negated** | "denies diabetes, no history of asthma, negative for cancer" | Correctly identifies clause negations and zeros clusters. | Correctly parses `status="negated"` for each concept. | **PASSED** |
| **3. Mixed Same-Cluster** | "no hypertension, but suffered a prior stroke" | Local clause splitting preserves stroke (score 2) despite negated hypertension. | Preserves stroke affirmation (score 2) independently of hypertension negation. | **PASSED** |
| **4. Family History** | "mother had severe diabetes and father died of stroke; patient is healthy" | **FAILS (False Positive):** Triggers diabetes and stroke on patient. | **PASSES:** Patient condition status set to `negated`; family history quarantined in notes. | **PASSED** (Failure documented, structured remedy verified) |
| **5. Historical Conditions** | "had childhood asthma 30 years ago, resolved; current hypertension" | **FAILS (False Positive):** Regex triggers active respiratory cluster score. | **PASSES:** `status="historical"` quaranatines asthma; respiratory score remains 0. | **PASSED** |
| **6. Diagnostic Uncertainty** | "atypical chest pain, ruling out angina; confirmed diabetes" | **FAILS (False Positive):** Regex triggers cardio cluster on "angina". | **PASSES:** `status="uncertain"` quaranatines angina; cardio score remains 0. | **PASSED** |
| **7. Typos & Misspellings** | "patient has hypertention and diabtes" | Fails to match keywords; sets `unparseable_or_unmentioned`. | Validates concept keys; rejects invalid/unmatched terms with structured warning. | **PASSED** |
| **8. Conflicting Statements** | "patient has hypertension, denies high blood pressure, but reports hypertension" | Affirmation logic takes precedence over negation. | Requires explicit adjudication or records conflict warning. | **PASSED** |
| **9. Age-Inapplicability** | 5-year-old child with reported adult osteoarthritis | Regex blindly scores arthritis (score 1). | Enforces MEPS skip pattern; flags arthritis as inapplicable for age 5. | **PASSED** |
| **10. Invalid Structure** | Input status `"maybe_kinda"`, unknown condition `"alien_syndrome"` | N/A (text only). | Raises `ValueError` on invalid status; quarantines unknown conditions in `unknown_fields`. | **PASSED** |

---

## B4. Protocol for Establishing Genuine Clinical Validation

Because synthetic software unit tests do not constitute clinical validation, the following formal protocol is required before HealthScore can claim clinical semantic validity.

### 1. Clinical Annotation Schema
A representative sample of $N = 1,000$ de-identified clinical notes (history and physical examinations, discharge summaries, outpatient intake notes) from diverse healthcare settings must be annotated.

For each note, annotators must label:
- **Concept Mention:** Exact text span.
- **Assertion Status:** `Affirmed` (active personal), `Negated` (absent personal), `Historical` (resolved prior condition), `Uncertain` (suspected/rule-out), or `Family History` (relative only).
- **Target Mapping:** Standard ICD-10-CM code and corresponding HealthScore condition cluster (Cardio, Metabolic, Respiratory, Oncology, MSK, Psych).

### 2. Double-Review and Adjudication Protocol
- **Reviewers:** Two independent board-certified physicians (MD/DO) or credentialed clinical documentation specialists.
- **Blinding:** Annotators are blinded to model predictions and to each other's annotations.
- **Inter-Rater Agreement (IRA):** Measured via Cohen's Kappa ($\kappa$) for binary cluster presence and Fleiss' Kappa for multi-class assertion status.
- **Adjudication:** All discrepancies ($\kappa < 0.85$ on any cluster) must be formally adjudicated by a third senior physician referee to produce the final **Adjudicated Gold Standard**.

### 3. Predeclared Acceptance Criteria
Before unblinding the model on the gold-standard corpus, HealthScore must achieve the following performance thresholds across all 6 condition clusters:
- **Cluster Sensitivity (Recall):** $\ge 0.90$
- **Cluster Positive Predictive Value (Precision):** $\ge 0.85$
- **Negation Specificity:** $\ge 0.95$
- **Family History Disambiguation Accuracy:** $\ge 0.95$
- **Historical vs Active Chronicity Discrimination:** $\ge 0.90$

### 4. Definitive Status Statement
- **Are genuine, independently annotated clinical examples available?** **NO.**
- **Has clinical semantic validation been established?** **NO.**
- **Current Operational Designation:** Free-text NLP is an **unvalidated heuristic proxy**. The structured pathway provides **syntactic schema parity**, but **clinical semantic validity is NOT YET ESTABLISHED.**

---
*Report Author: Antigravity Autonomous Research Agent*  
*Repository: HealthScore | Branch: `feature/ml-pipeline-rebuild`*
