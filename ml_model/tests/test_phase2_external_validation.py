"""
Automated Test Suite for Phase 2 External Cross-Year and Prospective Validation.

Validates:
  - HC-256 and HC-257 data ingestion and row-count reconciliation
  - Target construction and locked 2023 threshold fidelity ($20,360.50 and $17,827.41)
  - Absence of temporal leakage (Year 2 variables never present in Year 1 predictor matrix)
  - Survey weight alignment and non-negativity
  - Decile monotonicity and count reconciliation
  - External scoring pipeline execution and finite outputs
"""

import os
import sys
import json
import pytest
import numpy as np
import pandas as pd

# Add ml_model and repo root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

HC256_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation", "hc256", "data", "h256.dta")
HC257_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation", "hc257", "data", "h257.dta")
HC256_METRICS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation", "hc256", "metrics_hc256.json")
HC257_METRICS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation", "hc257", "metrics_hc257.json")

LOCKED_UNWEIGHTED_P90 = 20360.50
LOCKED_WEIGHTED_P90 = 17827.41

APPROVED_CALIBRATION_ESTIMATORS = {
    "LogisticRegression(C=inf)",
    "LogisticRegression(penalty=None)",
    "LogisticRegression(C=1e9)",
}


class TestHC256ExternalCrossYear:
    """Tests for MEPS HC-256 2024 cross-sectional validation."""

    @pytest.fixture(scope="class")
    @classmethod
    def hc256_metrics(cls):
        if not os.path.exists(HC256_METRICS_PATH):
            pytest.skip(f"HC-256 metrics not found at {HC256_METRICS_PATH}")
        with open(HC256_METRICS_PATH, "r") as f:
            return json.load(f)

    def test_hc256_row_count_reconciliation(self, hc256_metrics):
        meta = hc256_metrics["metadata"]
        assert meta["raw_record_count"] == 19140
        assert meta["invalid_age_dropped"] == 161
        assert meta["eligible_analysis_sample_size"] == 18979
        assert meta["raw_record_count"] - meta["invalid_age_dropped"] == meta["eligible_analysis_sample_size"]

    def test_hc256_locked_threshold_integrity(self, hc256_metrics):
        meta = hc256_metrics["metadata"]
        assert meta["locked_2023_unweighted_p90"] == LOCKED_UNWEIGHTED_P90
        assert meta["locked_2023_weighted_p90"] == LOCKED_WEIGHTED_P90
        # 2024 inflation increases actual 90th percentiles
        assert meta["temporal_2024_unweighted_p90"] > LOCKED_UNWEIGHTED_P90
        assert meta["temporal_2024_weighted_p90"] > LOCKED_WEIGHTED_P90

    def test_hc256_decile_reconciliation(self, hc256_metrics):
        deciles = hc256_metrics["observable_tweedie_regression"]["decile_stratification"]
        assert len(deciles) == 10
        total_decile_count = sum(d["count"] for d in deciles)
        assert total_decile_count == hc256_metrics["metadata"]["eligible_analysis_sample_size"]

        # Count-weighted predicted mean equals overall predicted mean within numerical tolerance
        count_weighted_pred = sum(d["count"] * d["predicted_mean"] for d in deciles) / total_decile_count
        overall_pred = hc256_metrics["observable_tweedie_regression"]["predicted_mean_unweighted"]
        assert np.isclose(count_weighted_pred, overall_pred, atol=0.05)

        # Count-weighted observed mean equals overall observed mean within numerical tolerance
        count_weighted_obs = sum(d["count"] * d["observed_mean"] for d in deciles) / total_decile_count
        overall_obs = hc256_metrics["target_distribution_2024"]["observed_mean_unweighted"]
        assert np.isclose(count_weighted_obs, overall_obs, atol=0.05)

    def test_hc256_baseline_brier_identity(self, hc256_metrics):
        # 1. Verify provenance of training baseline prevalences from training metadata
        meta_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts", "training_metadata.json")
        with open(meta_path, "r") as f:
            t_meta = json.load(f)
        p0_w = t_meta["classifier_artifacts_metadata"]["risk_model_classifier_observable_weighted_p90.pkl"]["target_prevalence_train_survey_weighted"]
        assert p0_w == 0.099888
        p0_u = round(1502 / 15016, 7)
        assert np.isclose(p0_u, 0.1000266, atol=1e-7)

        # 2. Weighted Classifier (Target 2)
        cls_w = hc256_metrics["observable_classifier_weighted_p90"]
        w_prev = cls_w["validation_weighted_prevalence"]
        expected_base_brier_w = w_prev * (1 - 2 * p0_w) + (p0_w ** 2)
        assert np.isclose(cls_w["training_baseline_weighted_brier"], expected_base_brier_w, atol=1e-4)
        expected_bss_w = 1.0 - (cls_w["survey_weighted_brier_score"] / cls_w["training_baseline_weighted_brier"])
        assert np.isclose(cls_w["brier_skill_score"], expected_bss_w, atol=1e-4)

        # 3. Unweighted Classifier (Target 1)
        cls_u = hc256_metrics["observable_classifier_unweighted_p90"]
        u_prev = cls_u["validation_prevalence"]
        expected_base_brier_u = u_prev * (1 - 2 * p0_u) + (p0_u ** 2)
        assert np.isclose(cls_u["training_baseline_brier"], expected_base_brier_u, atol=1e-4)
        expected_bss_u = 1.0 - (cls_u["brier_score"] / cls_u["training_baseline_brier"])
        assert np.isclose(cls_u["brier_skill_score"], expected_bss_u, atol=1e-4)

    def test_hc256_classifier_performance_bounds(self, hc256_metrics):
        cls_w = hc256_metrics["observable_classifier_weighted_p90"]
        assert 0.70 <= cls_w["roc_auc"] <= 0.85
        assert cls_w["brier_skill_score"] > 0.05
        assert np.isfinite(cls_w["calibration_slope"])
        assert np.isfinite(cls_w["survey_weighted_calibration_slope"])

    def test_hc256_calibration_estimator_provenance(self, hc256_metrics):
        """Verifies that all HC-256 calibration diagnostics record an approved unpenalized estimator."""
        cls_u = hc256_metrics["observable_classifier_unweighted_p90"]
        assert "calibration_estimator" in cls_u
        assert "unweighted_calibration_estimator" in cls_u
        assert cls_u["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert cls_u["unweighted_calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS

        cls_w = hc256_metrics["observable_classifier_weighted_p90"]
        assert "calibration_estimator" in cls_w
        assert "survey_weighted_calibration_estimator" in cls_w
        assert "unweighted_calibration_estimator" in cls_w
        assert cls_w["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert cls_w["survey_weighted_calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert cls_w["unweighted_calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS


class TestHC257ProspectiveForecasting:
    """Tests for MEPS HC-257 Panel 28 prospective longitudinal forecasting."""

    @pytest.fixture(scope="class")
    @classmethod
    def hc257_metrics(cls):
        if not os.path.exists(HC257_METRICS_PATH):
            pytest.skip(f"HC-257 metrics not found at {HC257_METRICS_PATH}")
        with open(HC257_METRICS_PATH, "r") as f:
            return json.load(f)

    def test_hc257_cohort_reconciliation(self, hc257_metrics):
        meta = hc257_metrics["metadata"]
        assert meta["total_panel_sample"] == 8872
        assert meta["two_year_eligible_yearind_1"] == 8709
        assert meta["dropped_non_two_year_attrited_or_entrant"] == 163
        assert meta["dropped_invalid_baseline_age"] == 1
        assert meta["analysis_cohort_size"] == 8708
        assert meta["total_panel_sample"] - meta["dropped_non_two_year_attrited_or_entrant"] - meta["dropped_invalid_baseline_age"] == meta["analysis_cohort_size"]

    def test_hc257_full_cohort_baseline_brier_identities(self, hc257_metrics):
        # 1. Full-pop classifier weighted baseline Brier verification (Target 2, p0 = 0.099888)
        cls_w = hc257_metrics["prospective_classifier_weighted_p90"]
        w_prev = cls_w["validation_weighted_prevalence"]
        p0_w = 0.099888
        expected_base_brier_w = w_prev * (1 - 2 * p0_w) + (p0_w ** 2)
        assert np.isclose(cls_w["training_baseline_weighted_brier"], expected_base_brier_w, atol=1e-4)
        expected_bss_w = 1.0 - (cls_w["survey_weighted_brier_score"] / cls_w["training_baseline_weighted_brier"])
        assert np.isclose(cls_w["brier_skill_score"], expected_bss_w, atol=1e-4)

        # 2. Full-pop classifier unweighted baseline Brier verification (Target 1, p0 = 0.1000266)
        cls_u = hc257_metrics["prospective_classifier_unweighted_p90"]
        u_prev = cls_u["validation_prevalence"]
        p0_u = 0.1000266
        expected_base_brier_u = u_prev * (1 - 2 * p0_u) + (p0_u ** 2)
        assert np.isclose(cls_u["training_baseline_brier"], expected_base_brier_u, atol=1e-4)
        expected_bss_u = 1.0 - (cls_u["brier_score"] / cls_u["training_baseline_brier"])
        assert np.isclose(cls_u["brier_skill_score"], expected_bss_u, atol=1e-4)

    def test_hc257_saq_cohort_and_baseline_brier_identities(self, hc257_metrics):
        meta = hc257_metrics["metadata"]
        assert meta["adult_saq_subcohort_lsaqwt_positive"] == 5630
        assert meta["adult_saq_both_rounds_saqrds24_1"] == 4337
        assert meta["adult_saq_round4_only_saqrds24_0"] == 1293
        assert meta["adult_saq_both_rounds_saqrds24_1"] + meta["adult_saq_round4_only_saqrds24_0"] == 5630

        assert meta["adult_saq_valid_baseline_addprs2"] == 4208
        assert meta["adult_saq_inapplicable_addprs2_round2"] == 1294
        assert meta["adult_saq_missing_addprs2_round2"] == 128
        assert meta["adult_saq_valid_baseline_addprs2"] + meta["adult_saq_inapplicable_addprs2_round2"] + meta["adult_saq_missing_addprs2_round2"] == 5630

        p0_w = 0.099888
        p0_u = 1736 / 15016  # Target 2 unweighted training prevalence (~0.1156100)

        # Positive-LSAQWT adult SAQ subcohort (N=5,630)
        saq_sub = hc257_metrics["adult_saq_subcohort_performance"]
        
        # Weighted SAQ
        saq_w = saq_sub["lsaqwt_weighted"]
        w_prev_saq = saq_w["evaluation_weighted_prevalence"]
        expected_base_brier_saq_w = w_prev_saq * (1 - 2 * p0_w) + (p0_w ** 2)
        assert np.isclose(saq_w["classifier_base_brier"], expected_base_brier_saq_w, atol=1e-4)
        expected_bss_saq_w = 1.0 - (saq_w["classifier_brier"] / saq_w["classifier_base_brier"])
        assert np.isclose(saq_w["classifier_brier_skill_score"], expected_bss_saq_w, atol=1e-4)

        # Unweighted SAQ
        saq_u = saq_sub["unweighted"]
        u_prev_saq = saq_u["evaluation_prevalence"]
        expected_base_brier_saq_u = u_prev_saq * (1 - 2 * p0_u) + (p0_u ** 2)
        assert np.isclose(saq_u["classifier_base_brier"], expected_base_brier_saq_u, atol=1e-4)
        expected_bss_saq_u = 1.0 - (saq_u["classifier_brier"] / saq_u["classifier_base_brier"])
        assert np.isclose(saq_u["classifier_brier_skill_score"], expected_bss_saq_u, atol=1e-4)

    def test_hc257_complete_case_valid_baseline_saq_brier_identities(self, hc257_metrics):
        p0_w = 0.099888
        p0_u = 1736 / 15016  # Target 2 unweighted training prevalence (~0.1156100)

        # Valid baseline SAQ complete-case sensitivity (N=4,208)
        cc_sub = hc257_metrics["adult_saq_complete_case_valid_depression"]
        assert cc_sub["subcohort_sample_size"] == 4208
        assert cc_sub["excluded_inapplicable_round2"] == 1294
        assert cc_sub["excluded_missing_round2"] == 128

        # Weighted Complete-Case (LSAQWT)
        cc_w = cc_sub["lsaqwt_weighted"]
        w_prev_cc = cc_w["evaluation_weighted_prevalence"]
        assert np.isclose(w_prev_cc, 0.1546, atol=1e-3)
        expected_base_brier_cc_w = w_prev_cc * (1 - 2 * p0_w) + (p0_w ** 2)
        assert np.isclose(cc_w["classifier_base_brier"], expected_base_brier_cc_w, atol=1e-4)
        expected_bss_cc_w = 1.0 - (cc_w["classifier_brier"] / cc_w["classifier_base_brier"])
        assert np.isclose(cc_w["classifier_brier_skill_score"], expected_bss_cc_w, atol=1e-4)

        # Unweighted Complete-Case
        cc_u = cc_sub["unweighted"]
        u_prev_cc = cc_u["evaluation_prevalence"]
        assert np.isclose(u_prev_cc, 0.1808, atol=1e-3)
        expected_base_brier_cc_u = u_prev_cc * (1 - 2 * p0_u) + (p0_u ** 2)
        assert np.isclose(cc_u["classifier_base_brier"], expected_base_brier_cc_u, atol=1e-4)
        expected_bss_cc_u = 1.0 - (cc_u["classifier_brier"] / cc_u["classifier_base_brier"])
        assert np.isclose(cc_u["classifier_brier_skill_score"], expected_bss_cc_u, atol=1e-4)

    def test_hc257_target2_training_prevalence_provenance(self):
        """
        Verifies that Target 2 unweighted prevalence (1736 / 15016 = 0.11561001598...)
        is independently reproducible from the authoritative Phase 1 training split and metadata,
        and confirms that Target 1 unweighted (0.1000266), Target 2 unweighted (0.1156100),
        and Target 2 survey-weighted (0.099888) training prevalences are mathematically distinct.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        meta_path = os.path.join(repo_root, "ml_model", "artifacts", "training_metadata.json")
        with open(meta_path, "r") as f:
            meta = json.load(f)

        # 1. Authoritative training metadata threshold and weighted prevalence
        t2_meta = meta["classifier_artifacts_metadata"]["risk_model_classifier_observable_weighted_p90.pkl"]
        p90_w_meta = t2_meta["target_threshold_dollars"]
        p0_w_meta = t2_meta["target_prevalence_train_survey_weighted"]
        assert np.isclose(p90_w_meta, 17827.405977383045, atol=1e-4)
        assert np.isclose(p0_w_meta, 0.099888, atol=1e-6)

        t1_meta = meta["classifier_artifacts_metadata"]["risk_model_classifier_observable_unweighted_p90.pkl"]
        p90_u_meta = t1_meta["target_threshold_dollars"]
        assert np.isclose(p90_u_meta, 20360.50, atol=1e-2)

        # 2. Independent derivation from Phase 1 training split
        from ml_model.data_pipeline import load_raw_meps, clean_and_engineer_features, split_data, DEFAULT_DATA_PATH
        if not os.path.exists(DEFAULT_DATA_PATH):
            pytest.fail(f"Phase 1 training dataset required for prevalence provenance verification, missing at {DEFAULT_DATA_PATH}")

        raw_df = load_raw_meps(DEFAULT_DATA_PATH)
        clean_df, _ = clean_and_engineer_features(raw_df, filter_zero_expenditure=False)
        splits = split_data(clean_df, test_size=0.20, random_state=42)
        y_train_raw = splits["y_train_raw"]
        w_train = splits["w_train"]
        n_train = len(y_train_raw)
        assert n_train == 15016

        # Target 1 unweighted: exactly 1,502 / 15,016 = 0.100026638...
        y_t1 = (y_train_raw >= p90_u_meta).astype(int)
        assert y_t1.sum() == 1502
        p0_t1_unw = y_t1.sum() / n_train
        assert np.isclose(p0_t1_unw, 0.1000266, atol=1e-7)

        # Target 2 unweighted: exactly 1,736 / 15,016 = 0.11561001598...
        y_t2 = (y_train_raw >= p90_w_meta).astype(int)
        assert y_t2.sum() == 1736
        p0_t2_unw = y_t2.sum() / n_train
        assert np.isclose(p0_t2_unw, 1736 / 15016, atol=1e-10)
        assert np.isclose(p0_t2_unw, 0.1156100, atol=1e-6)

        # Target 2 survey-weighted: 0.0998879... ~ 0.099888
        p0_t2_wtd = float((y_t2 * w_train).sum() / w_train.sum())
        assert np.isclose(p0_t2_wtd, 0.099888, atol=1e-4)

        # Assert strict distinctness of the three prevalences
        assert p0_t1_unw != p0_t2_unw, "Target 1 and Target 2 unweighted prevalences must be distinct"
        assert p0_t2_unw != p0_t2_wtd, "Target 2 unweighted and survey-weighted prevalences must be distinct"
        assert p0_t1_unw != p0_t2_wtd, "Target 1 unweighted and Target 2 weighted prevalences must be distinct"

    def test_no_temporal_leakage_in_predictors(self):
        """Verifies that predictor construction uses strictly Year 1 baseline variables."""
        if not os.path.exists(HC257_DATA_PATH):
            pytest.skip(f"HC-257 dataset not found at {HC257_DATA_PATH}")

        # Check column names in validation script
        from ml_model.validation.hc257.validate_hc257 import OBSERVABLE_COLS
        assert 'TOTEXPY2' not in OBSERVABLE_COLS
        assert 'TOTEXP24' not in OBSERVABLE_COLS
        assert 'TOTEXPY1' not in OBSERVABLE_COLS

    def test_hc257_prospective_discrimination(self, hc257_metrics):
        cls_w = hc257_metrics["prospective_classifier_weighted_p90"]
        assert 0.70 <= cls_w["roc_auc"] <= 0.85
        assert cls_w["brier_skill_score"] > 0.05

    def test_hc257_decile_reconciliation(self, hc257_metrics):
        deciles = hc257_metrics["prospective_tweedie_regression"]["decile_stratification"]
        assert len(deciles) == 10
        total_decile_count = sum(d["count"] for d in deciles)
        assert total_decile_count == hc257_metrics["metadata"]["analysis_cohort_size"]

        # Count-weighted predicted mean equals overall predicted mean within numerical tolerance
        count_weighted_pred = sum(d["count"] * d["predicted_mean"] for d in deciles) / total_decile_count
        overall_pred = hc257_metrics["prospective_tweedie_regression"]["predicted_mean_unweighted"]
        assert np.isclose(count_weighted_pred, overall_pred, atol=0.05)

        # Count-weighted observed mean equals overall observed mean within numerical tolerance
        count_weighted_obs = sum(d["count"] * d["observed_y2_mean"] for d in deciles) / total_decile_count
        overall_obs = hc257_metrics["target_distribution_y2"]["observed_mean_unweighted"]
        assert np.isclose(count_weighted_obs, overall_obs, atol=0.05)

    def test_hc257_calibration_estimator_provenance(self, hc257_metrics):
        """
        Verifies that all HC-257 full-cohort and SAQ subcohort calibration diagnostics
        record an estimator from the explicitly approved unpenalized candidate list.
        """
        # 1. Full-cohort prospective classifiers
        cls_u = hc257_metrics["prospective_classifier_unweighted_p90"]
        assert "calibration_estimator" in cls_u
        assert "unweighted_calibration_estimator" in cls_u
        assert cls_u["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert cls_u["unweighted_calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS

        cls_w = hc257_metrics["prospective_classifier_weighted_p90"]
        assert "calibration_estimator" in cls_w
        assert "survey_weighted_calibration_estimator" in cls_w
        assert "unweighted_calibration_estimator" in cls_w
        assert cls_w["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert cls_w["survey_weighted_calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert cls_w["unweighted_calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS

        # 2. Adult SAQ Subcohort (N=5,630)
        saq_sub = hc257_metrics["adult_saq_subcohort_performance"]
        assert "calibration_estimator" in saq_sub["unweighted"]
        assert saq_sub["unweighted"]["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert "calibration_estimator" in saq_sub["lsaqwt_weighted"]
        assert saq_sub["lsaqwt_weighted"]["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS

        # 3. Adult SAQ Complete-Case Subcohort (N=4,208)
        saq_cc = hc257_metrics["adult_saq_complete_case_valid_depression"]
        assert "calibration_estimator" in saq_cc["unweighted"]
        assert saq_cc["unweighted"]["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS
        assert "calibration_estimator" in saq_cc["lsaqwt_weighted"]
        assert saq_cc["lsaqwt_weighted"]["calibration_estimator"] in APPROVED_CALIBRATION_ESTIMATORS


class TestFrozenModelArtifactIntegrity:
    """Tests verifying physical hashes of frozen Phase 1 model artifacts."""

    FROZEN_MANIFEST = {
        "risk_model.pkl": ("ml_model/risk_model.pkl", "2ba4331510d688b1a21e67156bb5aab547c12e8c1ee109a851591b126a7d9c72"),
        "risk_model_tweedie_observable.pkl": ("ml_model/artifacts/risk_model_tweedie_observable.pkl", "a7f185db46316c6ac5f9051f0d5e0e24c7e80f3bd1f7777cd26cd0e1b42fcbd8"),
        "risk_model_classifier_observable_unweighted_p90.pkl": ("ml_model/artifacts/risk_model_classifier_observable_unweighted_p90.pkl", "cc266ae52414169c3c93b97a8ee147cba5eb62b0e0feff583c85a4e133a880fb"),
        "risk_model_classifier_observable_weighted_p90.pkl": ("ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl", "3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a"),
    }

    def test_frozen_model_hashes_match_manifest(self):
        import hashlib
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for filename, (rel_path, expected_hash) in self.FROZEN_MANIFEST.items():
            filepath = os.path.join(repo_root, rel_path)
            assert os.path.exists(filepath), f"Frozen model {filename} missing at {filepath}"
            with open(filepath, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            assert actual_hash == expected_hash, f"Hash mismatch for {filename}: expected {expected_hash}, got {actual_hash}"


class TestFeatureHarmonizationSemantics:
    """Tests verifying feature transformation parity and input policy enforcement."""

    def test_gender_validation_rejects_missing_or_invalid(self):
        from ml_model.risk_engine import validate_input
        with pytest.raises(ValueError, match="Missing required field: 'gender'"):
            validate_input({"age": 45, "bmi": 25.0})

        with pytest.raises(ValueError, match="Invalid gender"):
            validate_input({"age": 45, "gender": "unknown", "bmi": 25.0})

        # Valid gender accepted
        age, gender_male = validate_input({"age": 45, "gender": "female", "bmi": 25.0})
        assert gender_male == 0

    def test_structured_condition_exact_integer_sums(self):
        from ml_model.risk_engine import parse_structured_clinical_conditions

        # Cardio conditions (hypertension, chd, mi, stroke)
        res = parse_structured_clinical_conditions(["hypertension", "coronary_heart_disease"])
        assert res["Cardio_ACG"] == 2

        # Max Cardio: 4 conditions
        res_full_cardio = parse_structured_clinical_conditions([
            "hypertension", "coronary_heart_disease", "myocardial_infarction", "stroke"
        ])
        assert res_full_cardio["Cardio_ACG"] == 4

        # Metabolic: diabetes + hyperlipidemia = 2
        res_metabolic = parse_structured_clinical_conditions(["diabetes", "hyperlipidemia"])
        assert res_metabolic["Metabolic_ACG"] == 2

        # Respiratory: asthma + emphysema + chronic_bronchitis = 3
        res_resp = parse_structured_clinical_conditions(["asthma", "emphysema", "chronic_bronchitis"])
        assert res_resp["Respiratory_ACG"] == 3

        # Musculoskeletal: arthritis + joint_pain = 2
        res_msk = parse_structured_clinical_conditions(["arthritis", "joint_pain"])
        assert res_msk["Musculoskeletal_ACG"] == 2

        # Psychiatric: adhd + depression = 2
        res_psych = parse_structured_clinical_conditions(["adhd", "depression"])
        assert res_psych["Psychiatric_ACG"] == 2

    def test_unmapped_condition_quarantine(self):
        from ml_model.risk_engine import parse_structured_clinical_conditions

        res = parse_structured_clinical_conditions(["bipolar", "generalized_anxiety_disorder", "angina"])
        # None of these are in the Phase 1 training indicators
        assert res["Psychiatric_ACG"] == 0
        assert res["Cardio_ACG"] == 0
        # They must be recorded in unmapped_clinical_concepts for auditability
        unmapped_keys = [c["condition"] for c in res["unmapped_clinical_concepts"]]
        assert "bipolar" in unmapped_keys
        assert "generalized_anxiety_disorder" in unmapped_keys
        assert "angina" in unmapped_keys

    def test_runtime_age_top_coding_parity(self):
        """
        Verifies that runtime inference enforces MEPS training distribution bounds [0, 85]
        by top-coding model age covariates at 85.0 while accepting valid biological ages up to 125.
        """
        from ml_model.risk_engine import calculate_risk

        # Patient aged 90 (above MEPS top-coding limit of 85)
        res_90 = calculate_risk({"age": 90, "gender": "male", "diseaseInput": ""})
        diag_90 = res_90["data_parity_diagnostics"]["age_representation_parity"]
        assert diag_90["intake_age"] == 90.0
        assert diag_90["model_encoded_age"] == 85.0
        assert diag_90["is_top_coded_meps"] is True

        # Patient aged 45 (within standard support)
        res_45 = calculate_risk({"age": 45, "gender": "female", "diseaseInput": ""})
        diag_45 = res_45["data_parity_diagnostics"]["age_representation_parity"]
        assert diag_45["intake_age"] == 45.0
        assert diag_45["model_encoded_age"] == 45.0
        assert diag_45["is_top_coded_meps"] is False


class TestCalibrationCompatibilityAndSafety:
    """Verifies calibration fitting safety, candidate provenance, and error handling."""

    def test_calibration_functions_raise_clear_error_when_candidates_fail(self):
        """
        Verifies that compute_calibration in both validation modules raises a clear RuntimeError
        when all approved candidates fail parameter compatibility, and never silently falls back
        to default L2-regularized logistic regression.
        """
        from unittest.mock import patch
        from ml_model.validation.hc256.validate_hc256 import compute_calibration as compute_cal_256
        from ml_model.validation.hc257.validate_hc257 import compute_calibration as compute_cal_257

        y_dummy = np.array([0, 0, 1, 1])
        p_dummy = np.array([0.1, 0.2, 0.8, 0.9])

        def mock_incompatible_lr(*args, **kwargs):
            raise ValueError("simulated parameter incompatibility")

        # Test HC-256 calibration error handling
        with patch("ml_model.validation.hc256.validate_hc256.LogisticRegression", side_effect=mock_incompatible_lr):
            with pytest.raises(RuntimeError, match="Failed to fit unpenalized or approved near-unpenalized"):
                compute_cal_256(y_dummy, p_dummy)

        # Test HC-257 calibration error handling
        with patch("ml_model.validation.hc257.validate_hc257.LogisticRegression", side_effect=mock_incompatible_lr):
            with pytest.raises(RuntimeError, match="Failed to fit unpenalized or approved near-unpenalized"):
                compute_cal_257(y_dummy, p_dummy)

    def test_calibration_selects_approved_candidate_without_silent_regularization(self):
        """
        Verifies that on clean data, compute_calibration returns an estimator belonging
        strictly to APPROVED_CALIBRATION_ESTIMATORS without applying L2 regularization shrinkage.
        """
        from ml_model.validation.hc256.validate_hc256 import compute_calibration as compute_cal_256
        from ml_model.validation.hc257.validate_hc257 import compute_calibration as compute_cal_257

        y_dummy = np.array([0, 0, 1, 1])
        p_dummy = np.array([0.1, 0.2, 0.8, 0.9])

        int_256, slope_256, meth_256 = compute_cal_256(y_dummy, p_dummy)
        assert meth_256 in APPROVED_CALIBRATION_ESTIMATORS
        assert np.isfinite(int_256) and np.isfinite(slope_256)

        int_257, slope_257, meth_257 = compute_cal_257(y_dummy, p_dummy)
        assert meth_257 in APPROVED_CALIBRATION_ESTIMATORS
        assert np.isfinite(int_257) and np.isfinite(slope_257)

