"""
HealthScore Risk & Inference Engine
Executes validated inference using trained MEPS models:
  - Primary Deployment Model: 11-feature observable-inputs model (achieves exact data parity with intake).
  - Actuarial Dollar-Scale Expected Spending: Tweedie Compound Poisson-Gamma GLM.
  - Relative Expenditure Scoring: Inverse percentile rank among model cohort expectations.
  - Heuristic Monte Carlo parametric loss simulations.
"""

import os
import sys
import json
import pickle
import warnings
import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

REG_MODEL_PATH = os.path.join(BASE_DIR, "risk_model.pkl")
TWEEDIE_MODEL_PATH = os.path.join(ARTIFACTS_DIR, "risk_model_tweedie_observable.pkl")
CLS_MODEL_PATH = os.path.join(ARTIFACTS_DIR, "risk_model_classifier_observable_weighted_p90.pkl")
BENCHMARK_PATH = os.path.join(BASE_DIR, "benchmark_costs.pkl")
METADATA_PATH = os.path.join(ARTIFACTS_DIR, "training_metadata.json")
MANIFEST_PATH = os.path.join(BASE_DIR, "model_manifest.json")

# Observable feature columns (direct data parity with frontend patient intake)
OBSERVABLE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Age_x_Comorbidity'
]

# Canonical 14-feature column ordering (for full models and Tweedie GLM)
FEATURE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Frailty_Index',
    'Age_x_Frailty', 'Age_x_Comorbidity', 'K6SUM42'
]

# Lazy-loaded model and artifact holders
_REG_MODEL = None
_TWEEDIE_MODEL = None
_CLS_MODEL = None
_BENCHMARK_DATA = None
_IMPUTATION_LOOKUP = None
_MANIFEST = None
_VERIFIED_ARTIFACTS = None


def load_and_verify_manifest(manifest_path=MANIFEST_PATH):
    """
    Loads and validates the machine-readable model manifest against serialized disk artifacts.
    Enforces exact SHA-256 hash matching, feature schema and count verification, and intended runtime role.
    FAILS CLOSED if any artifact is missing, hash mismatches, or schema differs.
    """
    import hashlib
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Model manifest not found at {manifest_path}")

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    approved = manifest.get("approved_models", {})
    verified_artifacts = {}

    for model_key, spec in approved.items():
        rel_path = spec["artifact_path"]
        abs_path = os.path.join(BASE_DIR, rel_path) if not os.path.isabs(rel_path) else rel_path

        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Approved artifact for '{model_key}' missing at {abs_path}")

        with open(abs_path, "rb") as f:
            data = f.read()

        computed_hash = hashlib.sha256(data).hexdigest()
        expected_hash = spec["sha256"]

        if computed_hash.lower() != expected_hash.lower():
            raise RuntimeError(
                f"Artifact hash mismatch for '{model_key}' ({abs_path}): "
                f"expected {expected_hash}, got {computed_hash}. Fail closed."
            )

        obj = pickle.loads(data)
        expected_feature_count = spec.get("feature_count")
        if expected_feature_count is not None and hasattr(obj, "n_features_in_"):
            if obj.n_features_in_ != expected_feature_count:
                raise ValueError(
                    f"Feature count mismatch for '{model_key}': "
                    f"model has {obj.n_features_in_}, manifest expected {expected_feature_count}"
                )

        expected_schema = spec.get("feature_schema")
        if expected_schema and hasattr(obj, "feature_names_in_"):
            model_features = [str(x) for x in obj.feature_names_in_]
            expected_features = [str(x) for x in expected_schema]
            if model_features != expected_features:
                raise ValueError(
                    f"Feature schema mismatch for '{model_key}': "
                    f"model has {model_features}, manifest expected {expected_features}"
                )

        verified_artifacts[model_key] = {
            "model": obj,
            "spec": spec,
            "path": abs_path,
            "sha256": computed_hash
        }

    return manifest, verified_artifacts


def get_models():
    """Loads and caches regression, classification, Tweedie models and benchmark distributions via manifest verification."""
    global _REG_MODEL, _TWEEDIE_MODEL, _CLS_MODEL, _BENCHMARK_DATA, _IMPUTATION_LOOKUP, _MANIFEST, _VERIFIED_ARTIFACTS

    if _VERIFIED_ARTIFACTS is None:
        if os.path.exists(MANIFEST_PATH):
            _MANIFEST, _VERIFIED_ARTIFACTS = load_and_verify_manifest(MANIFEST_PATH)
            _REG_MODEL = _VERIFIED_ARTIFACTS["relative_expenditure_ranker"]["model"]
            _TWEEDIE_MODEL = _VERIFIED_ARTIFACTS["direct_dollar_regressor"]["model"]
            _CLS_MODEL = _VERIFIED_ARTIFACTS["high_cost_classifier"]["model"]
        else:
            if _REG_MODEL is None and os.path.exists(REG_MODEL_PATH):
                with open(REG_MODEL_PATH, "rb") as f:
                    _REG_MODEL = pickle.load(f)
            if _TWEEDIE_MODEL is None and os.path.exists(TWEEDIE_MODEL_PATH):
                with open(TWEEDIE_MODEL_PATH, "rb") as f:
                    _TWEEDIE_MODEL = pickle.load(f)
            if _CLS_MODEL is None and os.path.exists(CLS_MODEL_PATH):
                with open(CLS_MODEL_PATH, "rb") as f:
                    _CLS_MODEL = pickle.load(f)

    if _BENCHMARK_DATA is None and os.path.exists(BENCHMARK_PATH):
        with open(BENCHMARK_PATH, "rb") as f:
            _BENCHMARK_DATA = pickle.load(f)

    if _IMPUTATION_LOOKUP is None and os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, "r") as f:
                meta = json.load(f)
                _IMPUTATION_LOOKUP = meta.get("conditional_imputation_lookup", None)
        except Exception:
            _IMPUTATION_LOOKUP = None

    return _REG_MODEL, _TWEEDIE_MODEL, _CLS_MODEL, _BENCHMARK_DATA, _IMPUTATION_LOOKUP


def validate_input(data):
    """
    Validates inference inputs against schema requirements.
    Raises ValueError with descriptive diagnostics if input is invalid.
    """
    if not isinstance(data, dict):
        raise ValueError("Input data must be a JSON object / dictionary")

    if "age" not in data or data["age"] is None:
        raise ValueError("Missing required field: 'age'")
    try:
        age = float(data["age"])
    except (TypeError, ValueError):
        raise ValueError(f"Invalid age '{data['age']}': must be a positive number")
    if age < 0 or age > 125:
        raise ValueError(f"Age out of plausible range: {age} (must be 0-125)")

    if "gender" not in data or data["gender"] is None or str(data["gender"]).strip() == "":
        raise ValueError("Missing required field: 'gender' (must be 'male' or 'female')")

    gender_str = str(data["gender"]).strip().lower()
    if gender_str in ["male", "m", "1"]:
        gender_male = 1
    elif gender_str in ["female", "f", "0", "2"]:
        gender_male = 0
    else:
        raise ValueError(f"Invalid gender '{data['gender']}': must be 'male' or 'female'")

    return age, gender_male


def parse_clinical_conditions_detailed(user_text):
    """
    Detailed clinical NLP keyword parser with condition-level negation scope detection mapping free text
    to chronic condition clusters and diagnostics.

    CRITICAL METHODOLOGICAL CAVEAT & DATA GENERATION DIFFERENCE:
    MEPS diagnosis flags and frontend free-text parsing represent fundamentally distinct data-generation processes:
      - In MEPS HC-251, conditions are household-reported doctor diagnoses backed by medical-provider event followback
        and professionally mapped to ICD-10-CM / CCSR categories.
      - In the frontend intake, conditions are extracted via regex keyword pattern matching with condition-level negation scoping.
    Regex-derived disease flags are heuristic intake features and must NOT be described as clinically equivalent to MEPS diagnoses.
    Equal feature counts establish 'Input Availability Parity; Semantic Validation Pending', not semantic equivalence.
    Unresolved semantic limitations:
      1. Syntactic ambiguity and long-range dependencies: Complex syntax or nested parentheticals may misalign negation boundaries.
      2. Family medical history: Statements such as 'mother had diabetes' or 'family history of heart attack' are not distinguished from personal diagnoses.
      3. Temporal resolution: Past resolved conditions (e.g. 'had asthma as a child') cannot be separated from active chronic illnesses.
      4. Diagnostic uncertainty: Phrases like 'possible angina' or 'testing for lupus' are treated heuristically.
    """
    import re

    text = str(user_text or "").strip().lower()

    cluster_conditions = {
        "cardio": {
            "stroke": ["stroke", "cva", "transient ischemic attack", "tia", "cerebrovascular accident"],
            "heart_attack": ["heart attack", "myocardial infarction", "infarction"],
            "cad": ["coronary artery disease", "cad", "coronary", "angina", "congestive heart failure", "heart failure", "chf"],
            "hypertension": ["hypertension", "high blood pressure", "htn", "blood pressure", "elevated bp"],
            "cardiac_general": ["heart disease", "cardiac condition", "cardiac"]
        },
        "metabolic": {
            "diabetes": ["diabetes", "diabetic", "type 1 diabetes", "type 2 diabetes", "t2d", "t1d", "sugar", "high blood sugar"],
            "hyperlipidemia": ["high cholesterol", "cholesterol", "hyperlipidemia", "hypercholesterolemia", "lipids"],
            "thyroid": ["thyroid", "hypothyroidism", "hyperthyroidism"],
            "prediabetes": ["prediabetes", "borderline diabetes"]
        },
        "respiratory": {
            "copd": ["copd", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"],
            "asthma": ["asthma", "bronchial asthma", "wheezing", "reactive airway"],
            "bronchitis": ["bronchitis", "respiratory illness", "breathing difficulties"]
        },
        "oncology": {
            "cancer": ["cancer", "carcinoma", "malignancy", "malignant", "oncology", "neoplasm", "tumor", "lymphoma", "leukemia", "melanoma"]
        },
        "msk": {
            "arthritis": ["arthritis", "osteoarthritis", "rheumatoid arthritis", "joint pain", "joint degeneration"],
            "fracture": ["fracture", "broken bone"],
            "msk_general": ["orthopedic", "musculoskeletal", "chronic back pain"]
        },
        "psych": {
            "bipolar": ["bipolar", "bipolar disorder", "manic depression"],
            "depression": ["depression", "depressed", "major depressive disorder", "mdd"],
            "anxiety": ["anxiety", "generalized anxiety disorder", "gad", "panic disorder"],
            "adhd": ["adhd", "add", "attention deficit"],
            "psych_general": ["psychiatric", "mental health", "mental illness"]
        }
    }

    all_clusters = list(cluster_conditions.keys())

    # Case 1: Empty or missing text
    if not text:
        return {
            "flags": (0, 0, 0, 0, 0, 0),
            "explicitly_negated": [],
            "explicitly_present": [],
            "unmentioned": sorted(all_clusters),
            "input_status": "missing_or_empty",
            "clinical_interpretation": "Conditions are unmentioned/unobserved. Zero scores reflect an uninformative numerical default for regression input, NOT confirmed absence of illness.",
            "unresolved_semantic_limitations": [
                "Regex pattern matching cannot assess syntactic dependencies, family history, or temporal chronicity.",
                "Flags reflect heuristic user self-report keywords, NOT clinically confirmed MEPS diagnoses."
            ]
        }

    # Case 2: Explicit general negation of all chronic medical conditions
    general_neg_pattern = re.compile(
        r'\b(?:no\s+(?:(?:chronic|medical|known|prior|significant)\s+)*(?:conditions?|illnesses?|diseases?|problems?|health\s+issues?)|denies\s+(?:any\s+)?(?:medical|chronic)?\s*(?:conditions?|illnesses?)|completely\s+healthy|healthy\s*(?:patient)?\s*(?:,\s*)?(?:with\s+)?no\s+(?:(?:chronic|medical|known)\s+)*(?:conditions?|history|illness)|negative\s+for\s+all|zero\s+conditions?)\b',
        re.IGNORECASE
    )
    if general_neg_pattern.search(text):
        return {
            "flags": (0, 0, 0, 0, 0, 0),
            "explicitly_negated": sorted(all_clusters),
            "explicitly_present": [],
            "unmentioned": [],
            "input_status": "explicitly_negated_general",
            "clinical_interpretation": "Patient explicitly reports absence of all chronic medical conditions.",
            "unresolved_semantic_limitations": [
                "Self-reported absence of conditions is not clinically verified by medical records or billing data.",
                "Regex pattern matching cannot verify completeness of self-report."
            ]
        }

    neg_prefix_pattern = re.compile(
        r'\b(?:no\s+(?:history\s+of|prior|evidence\s+of|known|sign\s+of)?|denies\s+(?:any\s+)?(?:history\s+of\s+)?|denied\s+(?:any\s+)?(?:history\s+of\s+)?|negative\s+for|without\s+(?:any\s+)?|free\s+of|not\s+having|never\s+had|zero\s+history\s+of|rules?\s+out|ruled\s+out|no)\b',
        re.IGNORECASE
    )

    affirm_pattern = re.compile(
        r'\b(?:diagnosed\s+with|history\s+of|has|suffers\s+from|reports|with|confirmed|positive\s+for|prior)\b',
        re.IGNORECASE
    )

    # Split text on punctuation and adversative conjunctions
    raw_clauses = re.split(
        r'[;\.\n]|,\s*(?:but|however|except|although|whereas|yet|nevertheless)\b|\b(?:but|however|except|although|whereas|yet|nevertheless)\b|,\s*(?:has|diagnosed\s+with|with|reports|confirmed)\b',
        text
    )

    clauses = []
    for rc in raw_clauses:
        parts = rc.split(',')
        if len(parts) > 1:
            has_neg = bool(neg_prefix_pattern.search(parts[0]))
            for i, p in enumerate(parts):
                p_clean = p.strip()
                if not p_clean:
                    continue
                if i > 0 and has_neg:
                    if affirm_pattern.search(p_clean):
                        has_neg = False
                        clauses.append(p_clean)
                    elif p_clean.startswith(('or ', 'nor ')):
                        clauses.append('no ' + p_clean)
                    elif not any(p_clean.startswith(w) for w in ['has', 'with']):
                        clauses.append('no ' + p_clean)
                    else:
                        clauses.append(p_clean)
                else:
                    clauses.append(p_clean)
        else:
            if rc.strip():
                clauses.append(rc.strip())

    # Condition-level tracking (cluster, condition_key)
    conditions_affirmed = set()
    conditions_negated = set()

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        neg_match = neg_prefix_pattern.search(clause)
        if neg_match:
            aff_match = affirm_pattern.search(clause[neg_match.end():])
            if aff_match:
                neg_part = clause[:neg_match.end() + aff_match.start()]
                aff_part = clause[neg_match.end() + aff_match.start():]
                for cluster, cond_dict in cluster_conditions.items():
                    for cond_key, kws in cond_dict.items():
                        for kw in kws:
                            if re.search(r'\b' + re.escape(kw) + r'\b', neg_part):
                                conditions_negated.add((cluster, cond_key))
                            if re.search(r'\b' + re.escape(kw) + r'\b', aff_part):
                                conditions_affirmed.add((cluster, cond_key))
            else:
                for cluster, cond_dict in cluster_conditions.items():
                    for cond_key, kws in cond_dict.items():
                        for kw in kws:
                            if re.search(r'\b' + re.escape(kw) + r'\b', clause):
                                conditions_negated.add((cluster, cond_key))
        else:
            for cluster, cond_dict in cluster_conditions.items():
                for cond_key, kws in cond_dict.items():
                    for kw in kws:
                        if re.search(r'\b' + re.escape(kw) + r'\b', clause):
                            conditions_affirmed.add((cluster, cond_key))

    # Condition-level to cluster resolution:
    # Preserves condition-level affirmation so negation of condition X does not suppress affirmed condition Y in same cluster
    final_flags = {}
    explicitly_present_clusters = set()
    explicitly_negated_clusters = set()

    for cluster in all_clusters:
        affirmed_in_cl = {cond for cl, cond in conditions_affirmed if cl == cluster}
        negated_in_cl = {cond for cl, cond in conditions_negated if cl == cluster}

        # Any affirmed condition establishes cluster presence
        if len(affirmed_in_cl) > 0:
            explicitly_present_clusters.add(cluster)
            if cluster == "cardio":
                score = 2 if any(c in affirmed_in_cl for c in ["stroke", "heart_attack", "cad"]) else 1
            elif cluster == "metabolic":
                score = 2 if ("diabetes" in affirmed_in_cl and "hyperlipidemia" in affirmed_in_cl) else 1
            elif cluster == "respiratory":
                score = 2 if "copd" in affirmed_in_cl else 1
            elif cluster == "psych":
                score = 2 if ("bipolar" in affirmed_in_cl or ("depression" in affirmed_in_cl and "anxiety" in affirmed_in_cl)) else 1
            else:
                score = 1
            final_flags[cluster] = score
        elif len(negated_in_cl) > 0:
            explicitly_negated_clusters.add(cluster)
            final_flags[cluster] = 0
        else:
            final_flags[cluster] = 0

    unmentioned_clusters = [c for c in all_clusters if c not in explicitly_present_clusters and c not in explicitly_negated_clusters]

    input_status = "partially_or_fully_specified"
    if len(explicitly_present_clusters) == 0 and len(explicitly_negated_clusters) == 0:
        input_status = "unparseable_or_unmentioned"

    return {
        "flags": (
            final_flags["cardio"],
            final_flags["metabolic"],
            final_flags["respiratory"],
            final_flags["oncology"],
            final_flags["msk"],
            final_flags["psych"]
        ),
        "explicitly_negated": sorted(list(explicitly_negated_clusters)),
        "explicitly_present": sorted(list(explicitly_present_clusters)),
        "unmentioned": sorted(unmentioned_clusters),
        "conditions_affirmed_detail": sorted([f"{cl}:{cd}" for cl, cd in conditions_affirmed]),
        "conditions_negated_detail": sorted([f"{cl}:{cd}" for cl, cd in conditions_negated]),
        "input_status": input_status,
        "clinical_interpretation": (
            "Condition-level regex extraction with local negation scoping. "
            "Absence of mentions reflects unobserved status rather than verified clinical exclusion."
        ),
        "unresolved_semantic_limitations": [
            "Regex pattern matching cannot assess syntactic dependencies, family history, or temporal chronicity.",
            "Flags reflect heuristic user self-report keywords, NOT clinically confirmed MEPS diagnoses."
        ]
    }


def parse_clinical_conditions(user_text):
    """
    Clinical NLP keyword substring parser with negation handling mapping user intake text
    to custom heuristic condition clusters. Returns 6-tuple of condition scores.
    """
    detailed = parse_clinical_conditions_detailed(user_text)
    return detailed["flags"]


parse_conditions_from_text = parse_clinical_conditions


# MEPS-aligned condition concept registry with age restrictions and exact training variable mappings
STRUCTURED_CONDITION_REGISTRY = {
    # Cardio indicators (HIBPDX, CHDDX, MIDX, STRKDX) - Adult 18+
    "hypertension": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "HIBPDX"},
    "high_blood_pressure": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "HIBPDX"},
    "coronary_heart_disease": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "CHDDX"},
    "cad": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "CHDDX"},
    "heart_attack": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "MIDX"},
    "myocardial_infarction": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "MIDX"},
    "stroke": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": "STRKDX"},

    # Metabolic indicators (DIABDX_M18, CHOLDX) - Adult 18+
    "diabetes": {"cluster": "metabolic", "min_age": 18, "max_age": 125, "meps_var": "DIABDX_M18"},
    "type_1_diabetes": {"cluster": "metabolic", "min_age": 18, "max_age": 125, "meps_var": "DIABDX_M18"},
    "type_2_diabetes": {"cluster": "metabolic", "min_age": 18, "max_age": 125, "meps_var": "DIABDX_M18"},
    "hyperlipidemia": {"cluster": "metabolic", "min_age": 18, "max_age": 125, "meps_var": "CHOLDX"},
    "high_cholesterol": {"cluster": "metabolic", "min_age": 18, "max_age": 125, "meps_var": "CHOLDX"},

    # Respiratory indicators (ASTHDX: 0+, EMPHDX: 18+, CHBRON: 18+)
    "asthma": {"cluster": "respiratory", "min_age": 0, "max_age": 125, "meps_var": "ASTHDX"},
    "emphysema": {"cluster": "respiratory", "min_age": 18, "max_age": 125, "meps_var": "EMPHDX"},
    "copd": {"cluster": "respiratory", "min_age": 18, "max_age": 125, "meps_var": "EMPHDX"},
    "chronic_bronchitis": {"cluster": "respiratory", "min_age": 18, "max_age": 125, "meps_var": "CHBRON"},

    # Oncology indicator (CANCERDX: 0+)
    "cancer": {"cluster": "oncology", "min_age": 0, "max_age": 125, "meps_var": "CANCERDX"},
    "malignancy": {"cluster": "oncology", "min_age": 0, "max_age": 125, "meps_var": "CANCERDX"},

    # Musculoskeletal indicators (ARTHDX: 18+, JTPAIN31_M18: 18+)
    "arthritis": {"cluster": "msk", "min_age": 18, "max_age": 125, "meps_var": "ARTHDX"},
    "osteoarthritis": {"cluster": "msk", "min_age": 18, "max_age": 125, "meps_var": "ARTHDX"},
    "rheumatoid_arthritis": {"cluster": "msk", "min_age": 18, "max_age": 125, "meps_var": "ARTHDX"},
    "joint_pain": {"cluster": "msk", "min_age": 18, "max_age": 125, "meps_var": "JTPAIN31_M18"},

    # Psychiatric indicators (ADDPRS42: 18+, ADHDADDX: 5-17)
    "depression": {"cluster": "psych", "min_age": 18, "max_age": 125, "meps_var": "ADDPRS42"},
    "depressive_symptoms": {"cluster": "psych", "min_age": 18, "max_age": 125, "meps_var": "ADDPRS42"},
    "adhd": {"cluster": "psych", "min_age": 5, "max_age": 17, "meps_var": "ADHDADDX"},

    # Clinical concepts with NO direct MEPS survey counterpart in 11-feature training schema
    # (Documented and quarantined; NOT mapped into training feature sum)
    "bipolar": {"cluster": "psych", "min_age": 18, "max_age": 125, "meps_var": None},
    "anxiety": {"cluster": "psych", "min_age": 18, "max_age": 125, "meps_var": None},
    "generalized_anxiety_disorder": {"cluster": "psych", "min_age": 18, "max_age": 125, "meps_var": None},
    "thyroid_disorder": {"cluster": "metabolic", "min_age": 0, "max_age": 125, "meps_var": None},
    "angina": {"cluster": "cardio", "min_age": 18, "max_age": 125, "meps_var": None}
}

VALID_STRUCTURED_STATUSES = {
    "affirmed": "affirmed",
    "present": "affirmed",
    "active": "affirmed",
    "yes": "affirmed",
    "true": "affirmed",
    "negated": "negated",
    "absent": "negated",
    "no": "negated",
    "false": "negated",
    "historical": "historical",
    "resolved": "historical",
    "in_remission": "historical",
    "prior": "historical",
    "uncertain": "uncertain",
    "suspected": "uncertain",
    "rule_out": "uncertain",
    "pending": "uncertain",
    "unmentioned": "unmentioned"
}


def parse_structured_clinical_conditions(structured_input, age=None):
    """
    Validated structured per-condition clinical intake parser.
    Maps validated clinical condition records directly to MEPS-aligned feature clusters
    matching the exact Phase 1 training feature formulas.
    
    Distinguishes:
      - Explicit affirmation (active clinical condition)
      - Explicit negation (clinically confirmed absence)
      - Historical conditions (e.g. childhood illness, resolved cancer; not silently converted to active comorbidity)
      - Diagnostic uncertainty / rule-out (not counted as confirmed affirmation)
      - Unmentioned / missing conditions (explicitly tracked; NOT silently converted to confirmed negatives)
      - Age-inapplicable conditions (enforces official MEPS survey skip patterns, e.g. adult arthritis vs pediatric ADHD)
      - Unmapped clinical concepts (e.g. bipolar, anxiety; quarantined to prevent artificial feature distortion)
      
    Returns a standardized dictionary with flags (6-tuple) and audit provenance.
    """
    all_clusters = ["cardio", "metabolic", "respiratory", "oncology", "msk", "psych"]
    
    if not isinstance(structured_input, (dict, list)):
        raise ValueError(f"structured_input must be a dictionary or list of condition records, got {type(structured_input).__name__}")
    
    # Normalize input into a standardized item dict: {condition_key: {"status": ..., "notes": ...}}
    norm_items = {}
    if isinstance(structured_input, list):
        for idx, item in enumerate(structured_input):
            if isinstance(item, str):
                norm_items[item.lower().strip()] = {"status": "affirmed"}
            elif isinstance(item, dict):
                cond_name = item.get("condition") or item.get("name") or item.get("concept")
                if not cond_name:
                    raise ValueError(f"Structured record at index {idx} missing 'condition' or 'name' field: {item}")
                status = item.get("status", "affirmed")
                norm_items[str(cond_name).lower().strip()] = {
                    "status": status,
                    "notes": item.get("notes", "")
                }
            else:
                raise ValueError(f"Invalid condition item at index {idx}: {item}")
    else:
        for k, v in structured_input.items():
            k_clean = str(k).lower().strip()
            if isinstance(v, (str, bool, int)):
                norm_items[k_clean] = {"status": v}
            elif isinstance(v, dict):
                norm_items[k_clean] = v
            else:
                raise ValueError(f"Invalid structured condition record for '{k}': {v}")

    # Track categorized conditions
    affirmed = []
    negated = []
    historical = []
    uncertain = []
    unmentioned_conditions = []
    inapplicable = []
    unknown_fields = []
    unmapped_concepts = []
    
    cluster_affirmed = {cl: set() for cl in all_clusters}
    cluster_negated = {cl: set() for cl in all_clusters}
    affirmed_meps_indicators = set()

    for cond_key, record in norm_items.items():
        raw_status = str(record.get("status", "affirmed")).lower().strip()
        status = VALID_STRUCTURED_STATUSES.get(raw_status)
        if status is None:
            raise ValueError(f"Invalid condition status '{raw_status}' for '{cond_key}'. Allowed: {sorted(list(set(VALID_STRUCTURED_STATUSES.values())))}")

        # Check if direct cluster key was passed (e.g. "cardio": {"status": "affirmed"})
        if cond_key in all_clusters:
            if status == "affirmed":
                cluster_affirmed[cond_key].add(cond_key)
                affirmed.append(cond_key)
            elif status == "negated":
                cluster_negated[cond_key].add(cond_key)
                negated.append(cond_key)
            elif status == "historical":
                historical.append(cond_key)
            elif status == "uncertain":
                uncertain.append(cond_key)
            continue

        if cond_key not in STRUCTURED_CONDITION_REGISTRY:
            unknown_fields.append(cond_key)
            continue

        meta = STRUCTURED_CONDITION_REGISTRY[cond_key]
        cluster = meta["cluster"]
        meps_var = meta.get("meps_var")

        # Check age applicability
        if age is not None:
            min_age = meta.get("min_age", 0)
            max_age = meta.get("max_age", 125)
            if age < min_age or age > max_age:
                inapplicable.append({
                    "condition": cond_key,
                    "patient_age": age,
                    "applicable_range": f"{min_age}-{max_age}",
                    "reason": f"Condition '{cond_key}' inapplicable for age {age} under MEPS survey design specifications."
                })
                continue

        if status == "affirmed":
            affirmed.append(cond_key)
            if meps_var is not None:
                cluster_affirmed[cluster].add(cond_key)
                affirmed_meps_indicators.add(meps_var)
            else:
                unmapped_concepts.append({
                    "condition": cond_key,
                    "status": status,
                    "reason": f"Concept '{cond_key}' has no discrete counterpart in MEPS 11-feature training schema; excluded from feature calculation to preserve training parity."
                })
        elif status == "negated":
            negated.append(cond_key)
            cluster_negated[cluster].add(cond_key)
        elif status == "historical":
            historical.append(cond_key)
        elif status == "uncertain":
            uncertain.append(cond_key)
        elif status == "unmentioned":
            unmentioned_conditions.append(cond_key)

    # Compute cluster scores with exact Phase 1 training semantics:
    # Cardio_ACG: HIBPDX + CHDDX + MIDX + STRKDX (range 0 to 4)
    # Metabolic_ACG: DIABDX_M18 + CHOLDX (range 0 to 2)
    # Respiratory_ACG: ASTHDX + EMPHDX + CHBRON (range 0 to 3)
    # Oncology_ACG: CANCERDX (range 0 to 1)
    # Musculoskeletal_ACG: ARTHDX + JTPAIN31_M18 (range 0 to 2)
    # Psychiatric_ACG: ADDPRS42 + ADHDADDX (range 0 to 2)
    final_flags = {
        "cardio": sum(1 for v in ["HIBPDX", "CHDDX", "MIDX", "STRKDX"] if v in affirmed_meps_indicators) or (1 if "cardio" in cluster_affirmed["cardio"] else 0),
        "metabolic": sum(1 for v in ["DIABDX_M18", "CHOLDX"] if v in affirmed_meps_indicators) or (1 if "metabolic" in cluster_affirmed["metabolic"] else 0),
        "respiratory": sum(1 for v in ["ASTHDX", "EMPHDX", "CHBRON"] if v in affirmed_meps_indicators) or (1 if "respiratory" in cluster_affirmed["respiratory"] else 0),
        "oncology": (1 if "CANCERDX" in affirmed_meps_indicators or "oncology" in cluster_affirmed["oncology"] else 0),
        "msk": sum(1 for v in ["ARTHDX", "JTPAIN31_M18"] if v in affirmed_meps_indicators) or (1 if "msk" in cluster_affirmed["msk"] else 0),
        "psych": sum(1 for v in ["ADDPRS42", "ADHDADDX"] if v in affirmed_meps_indicators) or (1 if "psych" in cluster_affirmed["psych"] else 0),
    }

    unmentioned_clusters = [cl for cl in all_clusters if len(cluster_affirmed[cl]) == 0 and len(cluster_negated[cl]) == 0]

    # Evaluate completeness
    if len(affirmed) == 0 and len(negated) == 0 and len(historical) == 0 and len(uncertain) == 0:
        input_status = "insufficient_input"
    elif len(inapplicable) > 0 or len(unknown_fields) > 0:
        input_status = "structured_with_warnings"
    else:
        input_status = "structured_valid"

    return {
        "flags": (
            final_flags["cardio"],
            final_flags["metabolic"],
            final_flags["respiratory"],
            final_flags["oncology"],
            final_flags["msk"],
            final_flags["psych"]
        ),
        "Cardio_ACG": final_flags["cardio"],
        "Metabolic_ACG": final_flags["metabolic"],
        "Respiratory_ACG": final_flags["respiratory"],
        "Oncology_ACG": final_flags["oncology"],
        "Musculoskeletal_ACG": final_flags["msk"],
        "Psychiatric_ACG": final_flags["psych"],
        "conditions_affirmed": sorted(affirmed),
        "conditions_negated": sorted(negated),
        "conditions_historical": sorted(historical),
        "conditions_uncertain": sorted(uncertain),
        "conditions_inapplicable": inapplicable,
        "unmapped_clinical_concepts": unmapped_concepts,
        "unknown_fields": sorted(unknown_fields),
        "unmentioned_clusters": sorted(unmentioned_clusters),
        "input_status": input_status,
        "provenance": "structured_clinical_intake_pathway",
        "is_heuristic_proxy": False,
        "clinical_interpretation": (
            "Standardized structured clinical intake with explicit per-condition status tracking. "
            "Historical and uncertain conditions are separated from active comorbidities; "
            "age-specific applicability constraints are enforced."
        ),
        "missing_data_policy": (
            "Unmentioned conditions are flagged as unobserved; they are not silently converted into confirmed negatives. "
            "For regression scoring, zero weights are applied as numerical uninformative baseline."
        )
    }



def monte_carlo_simulation(predicted_mean_cost, n_simulations=5000, seed=None, base_cost=500.0):
    """
    Monte Carlo parametric Value-at-Risk (VaR) simulation using a synthetic Gamma loss distribution.
    
    IMPORTANT REGULATORY & ACTUARIAL DISCLAIMER:
    This output is strictly an exploratory parametric loss simulation heuristic for technical demonstration.
    Current MEPS prediction metrics and statistical associations do NOT validate commercial insurance pricing,
    premium calculation, underwriting adequacy, or reserve solvency.
    Output describes an exploratory simulated loss percentile heuristic, NOT an insurance quote.

    NOTE ON BASE_COST FLOOR:
    The default base_cost ($500.00) is an empirical heuristic baseline offset representing baseline
    administrative/preventative overhead. It is NOT derived from statutory filings or actuarial standards,
    and is configurable here for empirical sensitivity analysis.
    """
    # 1. Validate n_simulations as positive integer
    if not isinstance(n_simulations, (int, np.integer)) or isinstance(n_simulations, bool) or n_simulations <= 0:
        raise ValueError(f"n_simulations must be a positive integer, got {n_simulations}")

    # 2. Validate base_cost as finite non-negative number
    if not isinstance(base_cost, (int, float, np.floating, np.integer)) or isinstance(base_cost, bool) or not np.isfinite(base_cost) or base_cost < 0:
        raise ValueError(f"base_cost must be a finite non-negative number, got {base_cost}")
    base_cost = float(base_cost)

    # 3. Validate predicted_mean_cost: handle invalid model outputs explicitly instead of silently masking
    if predicted_mean_cost is None:
        raise ValueError("predicted_mean_cost cannot be None. Expected finite non-negative predicted expenditure.")
    try:
        val = float(predicted_mean_cost)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid predicted_mean_cost '{predicted_mean_cost}': must be convertible to float.")

    if not np.isfinite(val) or val < 0:
        raise ValueError(f"Invalid predicted_mean_cost '{predicted_mean_cost}': must be a finite non-negative number.")

    predicted_mean_cost = min(val, 10_000_000.0)

    # Boundary case: zero predicted expenditure
    if predicted_mean_cost == 0.0:
        return round(base_cost, 2), round(base_cost, 2), round(base_cost, 2)

    shape = 1.5
    scale = predicted_mean_cost / shape

    if seed is not None:
        rng = np.random.default_rng(seed)
        gamma_draws = rng.gamma(shape, scale, n_simulations)
    else:
        gamma_draws = np.random.gamma(shape, scale, n_simulations)

    simulated_costs = np.maximum(base_cost, gamma_draws + base_cost)
    target_premium = float(np.percentile(simulated_costs, 95))
    p5 = float(np.percentile(simulated_costs, 5))
    p95 = float(np.percentile(simulated_costs, 95))

    return round(target_premium, 2), round(p5, 2), round(p95, 2)


def get_imputed_defaults(age, comorbidity_count, lookup_table=None):
    """
    Returns empirical conditional expectations for unobserved SAQ / functional variables
    stratified by age bracket and comorbidity tier from training data.
    """
    if age < 18:
        age_bracket = 'pediatric'
    elif age < 45:
        age_bracket = 'young_adult'
    elif age < 65:
        age_bracket = 'middle_aged'
    else:
        age_bracket = 'senior'

    if comorbidity_count == 0:
        tier = 'tier_0'
    elif comorbidity_count == 1:
        tier = 'tier_1'
    else:
        tier = 'tier_2plus'

    key = f"{age_bracket}_{tier}"
    if lookup_table and key in lookup_table:
        return lookup_table[key]

    return {
        "perceived_health": 2.0,
        "physical_limitation": 0.05,
        "cognitive_difficulty": 0.03,
        "k6_distress": 1.00
    }


def calculate_risk(data, require_structured_inputs=False):
    """
    Primary inference pipeline for a patient profile.
    
    Accepts:
      - age (required)
      - gender (optional, default 'male')
      - diseaseInput (optional free-text)
      - perceived_health (optional 1-5; used if explicit SAQ inputs are available)
      - physical_limitation (optional bool/int)
      - cognitive_difficulty (optional bool/int)
      - k6_distress (optional 0-24)
      - require_structured_inputs (optional bool, default False):
          If True and clinical conditions are unmentioned/unparseable, returns an insufficient-input response.
      
    Returns:
      - relative_expenditure_score: Inverse percentile rank among model cohort expectations (0-100)
      - health_score: Alias for relative_expenditure_score (for backward-compatibility)
      - risk_score: Expected dollar expenditure (USD)
      - expected_annual_dollar_expenditure: Direct dollar-scale expenditure prediction from Tweedie GLM (USD)
      - premium: 95th-percentile VaR simulation heuristic (USD)
      - high_cost_probability: Estimated probability of exceeding top-decile expenditure
      - confidence_interval: { p5, p95 }
      - top_risk_factors: list of clinical indicators contributing to prediction
      - data_parity_diagnostics: detailed breakdown of observed vs imputed features
      - score_semantics: scientific interpretation of scores and limitations
    """
    age, gender_male = validate_input(data)

    structured_data = data.get("conditions_structured") or data.get("structured_conditions")
    user_text = str(data.get("diseaseInput", ""))

    if structured_data is not None:
        parsed_conditions = parse_structured_clinical_conditions(structured_data, age=age)
        intake_mode = "structured_clinical_intake"
        is_heuristic_proxy = False
        if require_structured_inputs and parsed_conditions["input_status"] == "insufficient_input":
            return {
                "status": "insufficient_input",
                "error": "Structured clinical condition input is empty or insufficient. Explicit status required for conditions.",
                "unmentioned_clusters": parsed_conditions["unmentioned_clusters"],
                "input_status": parsed_conditions["input_status"],
                "resolution": "Provide structured condition records with explicit affirmation or negation."
            }
    else:
        parsed_conditions = parse_clinical_conditions_detailed(user_text)
        intake_mode = "free_text_heuristic_proxy"
        is_heuristic_proxy = True
        if require_structured_inputs and parsed_conditions["input_status"] in ["missing_or_empty", "unparseable_or_unmentioned"]:
            return {
                "status": "insufficient_input",
                "error": "Clinical conditions are unmentioned or unparseable. Explicit structured inputs or condition affirmations/negations are required.",
                "unmentioned_clusters": parsed_conditions["unmentioned"],
                "input_status": parsed_conditions["input_status"],
                "resolution": "Provide structured condition indicators or text with explicit affirmation/negation."
            }

    cardio, metabolic, respiratory, oncology, msk, psych = parsed_conditions["flags"]

    # Derived comorbidities
    cluster_vals = [cardio, metabolic, respiratory, oncology, msk, psych]
    comorbidity_count = sum(1 for v in cluster_vals if v > 0)
    multimorbidity_penalty = comorbidity_count ** 2

    # MEPS Training Representation Parity:
    # In MEPS public use files (HC-251/HC-256), AGE23X is top-coded at 85 to protect confidentiality.
    # While runtime intake validates plausible biological ages (0-125), model covariates must be
    # capped at 85.0 to maintain exact training-serving distribution parity and avoid unconstrained linear extrapolation.
    age_model = min(float(age), 85.0)
    age_x_comorbidity = age_model * comorbidity_count

    reg_model, tweedie_model, cls_model, benchmark_bundle, lookup_table = get_models()
    if reg_model is None:
        raise RuntimeError("Model artifact not found. Please train model first via python train_model.py")

    # Observable feature vector (Leading Deployment Candidate - 11 features)
    patient_obs_df = pd.DataFrame([{
        'AGE23X': age_model,
        'Gender_Male': gender_male,
        'Cardio_ACG': cardio,
        'Metabolic_ACG': metabolic,
        'Respiratory_ACG': respiratory,
        'Oncology_ACG': oncology,
        'Musculoskeletal_ACG': msk,
        'Psychiatric_ACG': psych,
        'Comorbidity_Count': comorbidity_count,
        'Multimorbidity_Penalty': multimorbidity_penalty,
        'Age_x_Comorbidity': age_x_comorbidity
    }])[OBSERVABLE_COLS]

    # Full 14-feature vector (for Tweedie GLM, classifier, or 14-feature models)
    observed_features = ["age", "gender"]
    imputed_features = []
    if user_text:
        observed_features.append("diseaseInput")

    defaults = get_imputed_defaults(age, comorbidity_count, lookup_table)

    if "perceived_health" in data and data["perceived_health"] is not None:
        perceived_health = float(data["perceived_health"])
        perceived_health = max(1.0, min(5.0, perceived_health))
        observed_features.append("perceived_health")
    else:
        perceived_health = float(defaults["perceived_health"])
        imputed_features.append("perceived_health")

    if "physical_limitation" in data and data["physical_limitation"] is not None:
        limitation = float(data["physical_limitation"])
        observed_features.append("physical_limitation")
    else:
        if any(kw in user_text for kw in ["mobility", "wheelchair", "paralysis"]):
            limitation = 1.0
            observed_features.append("physical_limitation (NLP-inferred)")
        else:
            limitation = float(defaults["physical_limitation"])
            imputed_features.append("physical_limitation")

    if "cognitive_difficulty" in data and data["cognitive_difficulty"] is not None:
        cognitive = float(data["cognitive_difficulty"])
        observed_features.append("cognitive_difficulty")
    else:
        if any(kw in user_text for kw in ["dementia", "alzheimer"]):
            cognitive = 1.0
            observed_features.append("cognitive_difficulty (NLP-inferred)")
        else:
            cognitive = float(defaults["cognitive_difficulty"])
            imputed_features.append("cognitive_difficulty")

    if "k6_distress" in data and data["k6_distress"] is not None:
        k6_distress = float(data["k6_distress"])
        k6_distress = max(0.0, min(24.0, k6_distress))
        observed_features.append("k6_distress")
    else:
        k6_distress = float(defaults["k6_distress"])
        imputed_features.append("k6_distress")

    frailty_index = perceived_health + (limitation * 2.0) + (cognitive * 2.0)
    age_x_frailty = age_model * frailty_index

    patient_full_df = pd.DataFrame([{
        'AGE23X': age_model,
        'Gender_Male': gender_male,
        'Cardio_ACG': cardio,
        'Metabolic_ACG': metabolic,
        'Respiratory_ACG': respiratory,
        'Oncology_ACG': oncology,
        'Musculoskeletal_ACG': msk,
        'Psychiatric_ACG': psych,
        'Comorbidity_Count': comorbidity_count,
        'Multimorbidity_Penalty': multimorbidity_penalty,
        'Frailty_Index': frailty_index,
        'Age_x_Frailty': age_x_frailty,
        'Age_x_Comorbidity': age_x_comorbidity,
        'K6SUM42': k6_distress
    }])[FEATURE_COLS]

    # 1. Primary Model Prediction (11-feature observable model if fitted with 11, else 14)
    if hasattr(reg_model, "n_features_in_") and reg_model.n_features_in_ == 11:
        pred_log = float(reg_model.predict(patient_obs_df)[0])
        model_used = "11-feature observable-inputs model (direct input availability parity)"
    else:
        pred_log = float(reg_model.predict(patient_full_df)[0])
        model_used = "14-feature model"

    expected_log_cost_dollar = float(max(0.0, np.expm1(pred_log)))

    # 2. Direct Dollar-Scale Expenditure Prediction (Tweedie GLM)
    if tweedie_model is not None:
        if hasattr(tweedie_model, "n_features_in_") and tweedie_model.n_features_in_ == 11:
            direct_dollar_expenditure = float(max(0.0, tweedie_model.predict(patient_obs_df)[0]))
        else:
            direct_dollar_expenditure = float(max(0.0, tweedie_model.predict(patient_full_df)[0]))
    else:
        direct_dollar_expenditure = expected_log_cost_dollar

    # 3. High-Expenditure Classifier Probability
    high_cost_prob = None
    if cls_model is not None:
        try:
            if hasattr(cls_model, "n_features_in_") and cls_model.n_features_in_ == 11:
                prob = float(cls_model.predict_proba(patient_obs_df)[0, 1])
            else:
                prob = float(cls_model.predict_proba(patient_full_df)[0, 1])
            high_cost_prob = round(prob, 4)
        except Exception:
            high_cost_prob = None

    # 4. Percentile Ranking against Out-of-Fold Benchmark
    pred_benchmark = None
    obs_benchmark = None
    if isinstance(benchmark_bundle, dict):
        pred_benchmark = benchmark_bundle.get("predicted_costs_oof", None)
        obs_benchmark = benchmark_bundle.get("observed_costs_train", None)
    elif isinstance(benchmark_bundle, (np.ndarray, list)):
        pred_benchmark = benchmark_bundle

    if pred_benchmark is not None and len(pred_benchmark) > 0:
        pred_percentile = float(percentileofscore(pred_benchmark, expected_log_cost_dollar, kind='rank'))
        relative_expenditure_score = round(max(0.0, min(100.0, 100.0 - pred_percentile)), 2)
    else:
        pred_percentile = 50.0
        relative_expenditure_score = 50.0

    if obs_benchmark is not None and len(obs_benchmark) > 0:
        obs_percentile = float(percentileofscore(obs_benchmark, expected_log_cost_dollar, kind='rank'))
    else:
        obs_percentile = pred_percentile

    # 5. Monte Carlo Parametric VaR Heuristic Simulation
    target_premium, p5, p95 = monte_carlo_simulation(direct_dollar_expenditure)

    # 6. Attributed Indicators
    risk_factors = []
    if comorbidity_count > 0:
        risk_factors.append(f"{comorbidity_count} chronic condition cluster(s)")
    if age > 50:
        risk_factors.append(f"Age factor ({int(age)} yrs)")
    if frailty_index > 4:
        risk_factors.append(f"Elevated frailty composite ({round(frailty_index, 2)})")
    if cardio > 0:
        risk_factors.append("Cardiovascular indicators")
    if metabolic > 0:
        risk_factors.append("Metabolic indicators")
    if oncology > 0:
        risk_factors.append("Oncological history")
    if len(risk_factors) == 0:
        if parsed_conditions["input_status"] in ["missing_or_empty", "unparseable_or_unmentioned", "insufficient_input"]:
            risk_factors.append("Demographic baseline (clinical conditions unobserved/unmentioned; clinical absence unconfirmed)")
        elif parsed_conditions["input_status"] == "explicitly_negated_general":
            risk_factors.append("Explicitly reported absence of chronic medical conditions")
        else:
            risk_factors.append("Baseline demographic profile")

    return {
        "relative_expenditure_score": relative_expenditure_score,
        "health_score": relative_expenditure_score,  # Alias for backward compatibility
        "risk_score": round(direct_dollar_expenditure, 2),  # Expected dollar spending
        "expected_annual_dollar_expenditure": round(direct_dollar_expenditure, 2),
        "ranking_expenditure_expm1": round(expected_log_cost_dollar, 2),
        "premium": target_premium,
        "high_cost_probability": high_cost_prob,
        "simulated_loss_percentiles": {
            "p5": p5,
            "p95": p95,
            "p95_loss_heuristic": target_premium,
            "description": "Exploratory simulated loss percentiles from Gamma Monte Carlo heuristic, NOT an actuarial confidence interval."
        },
        "confidence_interval": {
            "p5": p5,
            "p95": p95,
            "status": "deprecated_alias_for_simulated_loss_percentiles",
            "qualification": "Describes empirical simulated loss percentiles (P5, P95) from exploratory heuristic, NOT an actuarial confidence interval for estimated VaR."
        },
        "top_risk_factors": risk_factors,
        "score_semantics": {
            "definition": (
                "relative_expenditure_score represents an inverse percentile rank of model-predicted expenditure "
                "relative to the MEPS training cohort expectations (100 = lowest predicted expenditure). "
                "It is an actuarial ranking metric, NOT a clinically validated measure of health status or clinical wellness, "
                "and does not imply causal risk reduction."
            ),
            "dollar_prediction_qualification": (
                "expected_annual_dollar_expenditure is a direct un-logged dollar prediction from Tweedie GLM. "
                "While tracking overall and top-decile spending well, group-level ratios vary across intermediate deciles; "
                "it represents the leading dollar regression candidate rather than a fully calibrated estimator."
            ),
            "parity_qualification": (
                "11-feature model achieves 'Input Availability Parity; Semantic Validation Pending'. "
                "Regex-derived condition flags are heuristic intake features and are not clinically equivalent to MEPS survey diagnoses."
            )
        },
        "data_parity_diagnostics": {
            "deployment_engine": model_used,
            "imputation_method": "conditional_expectation_by_age_and_comorbidity",
            "age_representation_parity": {
                "intake_age": age,
                "model_encoded_age": age_model,
                "is_top_coded_meps": bool(age > 85.0),
                "meps_training_upper_bound": 85.0,
                "note": "Age is top-coded at 85 for model covariates to align with MEPS training distribution bounds."
            },
            "features_observed": observed_features,
            "features_imputed": imputed_features,
            "percentile_model_prediction": round(pred_percentile, 2),
            "percentile_observed_meps_spending": round(obs_percentile, 2),
            "clinical_condition_parsing": {
                "intake_mode": intake_mode,
                "is_heuristic_proxy": is_heuristic_proxy,
                "input_status": parsed_conditions["input_status"],
                "explicitly_negated": parsed_conditions.get("explicitly_negated", parsed_conditions.get("conditions_negated", [])),
                "explicitly_present": parsed_conditions.get("explicitly_present", parsed_conditions.get("conditions_affirmed", [])),
                "unmentioned": parsed_conditions.get("unmentioned", parsed_conditions.get("unmentioned_clusters", [])),
                "conditions_affirmed_detail": parsed_conditions.get("conditions_affirmed_detail", parsed_conditions.get("conditions_affirmed", [])),
                "conditions_negated_detail": parsed_conditions.get("conditions_negated_detail", parsed_conditions.get("conditions_negated", [])),
                "conditions_historical": parsed_conditions.get("conditions_historical", []),
                "conditions_uncertain": parsed_conditions.get("conditions_uncertain", []),
                "conditions_inapplicable": parsed_conditions.get("conditions_inapplicable", []),
                "clinical_interpretation": parsed_conditions.get("clinical_interpretation", ""),
                "unresolved_semantic_limitations": parsed_conditions.get("unresolved_semantic_limitations", [])
            },
            "heuristic_proxy_notice": (
                "Free-text regex keyword parsing is an unvalidated heuristic proxy, NOT clinically validated extraction."
            ) if is_heuristic_proxy else None,
            "input_completeness_warning": (
                "Absence of condition mentions in input does not imply confirmed clinical absence. "
                "Zero comorbidity cluster scores were assigned as an uninformative numerical default for regression input, "
                "NOT a clinically confirmed healthy profile."
            ) if parsed_conditions["input_status"] in ["missing_or_empty", "unparseable_or_unmentioned", "insufficient_input"] else None,
            "note": "11 observable features used for primary ranking. SAQ variables used conditional population expectations for 14-feature models only when unobserved."
        }
    }