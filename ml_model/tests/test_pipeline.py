"""
Automated Test Suite for HealthScore Data Pipeline, ML Models, and Inference Engine.
All tests function as software integrity and smoke tests, not clinical validations.
"""

import os
import sys
import json
import pickle
import pytest
import numpy as np
import pandas as pd

# Add ml_model to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline import (
    load_raw_meps, clean_and_engineer_features, split_data,
    FEATURE_COLS, OBSERVABLE_FEATURE_COLS, DEFAULT_DATA_PATH
)
from risk_engine import calculate_risk, validate_input, parse_clinical_conditions, get_models


class TestDataPipeline:
    """Tests for raw data integrity, schema, and cleaning behavior."""

    @pytest.fixture(scope="class")
    @classmethod
    def raw_data(cls):
        if not os.path.exists(DEFAULT_DATA_PATH):
            pytest.skip(f"Dataset not found at {DEFAULT_DATA_PATH}")
        return load_raw_meps(DEFAULT_DATA_PATH)

    def test_raw_dataset_dimensions_and_uniqueness(self, raw_data):
        assert len(raw_data) == 18919, f"Expected 18,919 rows, got {len(raw_data)}"
        assert 'TOTEXP23' in raw_data.columns
        assert 'AGE23X' in raw_data.columns
        assert 'PERWT23F' in raw_data.columns

    def test_cleaning_and_row_count_flow(self, raw_data):
        clean_df, audit = clean_and_engineer_features(raw_data, filter_zero_expenditure=False)
        assert audit["raw_records"] == 18919
        assert audit["dropped_invalid_age"] == 148
        assert audit["zero_expenditure_records"] == 2611
        assert audit["final_records"] == 18771
        assert len(clean_df) == 18771

    def test_depression_variable_fix(self, raw_data):
        """Verifies that severe depression (ADDPRS42 in [2, 3]) is NOT mapped to 0."""
        clean_df, _ = clean_and_engineer_features(raw_data, filter_zero_expenditure=False)
        raw_mask = raw_data['AGE23X'] >= 0
        raw_subset = raw_data[raw_mask]
        severe_depression_idx = raw_subset[raw_subset['ADDPRS42'].isin([2, 3])].index
        
        # In cleaned df, these must be 1 (presence of past-2-week depressive symptoms)
        assert (clean_df.loc[severe_depression_idx, 'ADDPRS42'] == 1).all()

    def test_feature_columns_exist_and_finite(self, raw_data):
        clean_df, _ = clean_and_engineer_features(raw_data, filter_zero_expenditure=False)
        for col in FEATURE_COLS:
            assert col in clean_df.columns, f"Missing feature: {col}"
            assert not clean_df[col].isna().any(), f"NaNs found in feature: {col}"
            assert np.isfinite(clean_df[col]).all(), f"Non-finite values found in feature: {col}"


class TestSplittingAndLeakage:
    """Tests for train/test segregation, data leakage, and reproducibility."""

    @pytest.fixture(scope="class")
    @classmethod
    def cleaned_data(cls):
        if not os.path.exists(DEFAULT_DATA_PATH):
            pytest.skip(f"Dataset not found at {DEFAULT_DATA_PATH}")
        raw_df = load_raw_meps(DEFAULT_DATA_PATH)
        df, _ = clean_and_engineer_features(raw_df, filter_zero_expenditure=False)
        return df

    def test_train_test_split_sizes_and_disjointness(self, cleaned_data):
        splits = split_data(cleaned_data, test_size=0.20, random_state=42)
        X_train, X_test = splits["X_train"], splits["X_test"]

        assert len(X_train) == 15016
        assert len(X_test) == 3755
        assert len(set(X_train.index).intersection(set(X_test.index))) == 0, "Train and Test sets overlap!"

    def test_split_reproducibility(self, cleaned_data):
        splits_1 = split_data(cleaned_data, test_size=0.20, random_state=42)
        splits_2 = split_data(cleaned_data, test_size=0.20, random_state=42)
        assert splits_1["X_train"].index.equals(splits_2["X_train"].index)
        assert splits_1["X_test"].index.equals(splits_2["X_test"].index)

    def test_target_transformations(self, cleaned_data):
        splits = split_data(cleaned_data, test_size=0.20, random_state=42)
        y_raw = splits["y_test_raw"].values
        y_log = splits["y_test_log"].values
        reconstructed = np.expm1(y_log)
        np.testing.assert_allclose(reconstructed, y_raw, rtol=1e-5)

    def test_normalized_weights_scale(self, cleaned_data):
        splits = split_data(cleaned_data, test_size=0.20, random_state=42)
        w_norm = splits["w_train_norm"]
        assert len(w_norm) == len(splits["X_train"])
        np.testing.assert_allclose(w_norm.mean(), 1.0, rtol=1e-4)
        assert w_norm.min() >= 0.0


class TestModelArtifactsAndParity:
    """Tests for artifact loading, training-serving parity, and OOF benchmark validity."""

    def test_model_artifacts_exist(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assert os.path.exists(os.path.join(base_dir, "risk_model.pkl"))
        assert os.path.exists(os.path.join(base_dir, "benchmark_costs.pkl"))
        assert os.path.exists(os.path.join(base_dir, "artifacts", "feature_schema.json"))
        assert os.path.exists(os.path.join(base_dir, "artifacts", "training_metadata.json"))
        assert os.path.exists(os.path.join(base_dir, "artifacts", "evaluation_metrics.json"))

    def test_benchmark_costs_are_out_of_fold(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_dir, "benchmark_costs.pkl"), "rb") as f:
            bench = pickle.load(f)
        if isinstance(bench, dict):
            oof_costs = bench["predicted_costs_oof"]
        else:
            oof_costs = bench
        assert len(oof_costs) == 15016
        assert (oof_costs >= 0).all()
        assert np.isfinite(oof_costs).all()

    def test_feature_schema_parity(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_dir, "artifacts", "feature_schema.json"), "r") as f:
            schema = json.load(f)
        assert schema["features"] == FEATURE_COLS
        assert schema["observable_features"] == OBSERVABLE_FEATURE_COLS

    def test_decile_reconciliation_and_count_weighted_means(self):
        """Asserts that decile counts sum to test set size and count-weighted means equal overall test means."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        metrics_file = os.path.join(base_dir, "artifacts", "evaluation_metrics.json")
        with open(metrics_file, "r") as f:
            data = json.load(f)

        strat = data["stratification_and_ranking_analysis"]
        recon = data["reconciliation_summary"]
        overall = data["metadata"]["overall_test_metrics"]

        # 1. Assert decile counts sum to exact test size
        total_count = sum(d["count"] for d in strat)
        assert total_count == recon["test_sample_size"] == 3755

        # 2. Assert count-weighted decile means equal overall test means within 0.05
        assert abs(recon["overall_observed_mean"] - recon["count_weighted_observed_mean"]) <= 0.05
        assert abs(recon["overall_pred_xgb_obs_mean"] - recon["count_weighted_pred_xgb_obs_mean"]) <= 0.05
        assert abs(recon["overall_pred_tweedie_mean"] - recon["count_weighted_pred_tweedie_mean"]) <= 0.05
        assert abs(recon["overall_pred_twopart_mean"] - recon["count_weighted_pred_twopart_mean"]) <= 0.05
        assert recon["reconciled"] is True

        # 3. Assert metadata overall test metrics match reconciliation summary
        assert overall["overall_observed_mean"] == recon["overall_observed_mean"] == 8764.62
        assert overall["overall_pred_xgb_obs_mean"] == recon["overall_pred_xgb_obs_mean"] == 2384.13
        assert overall["overall_pred_tweedie_mean"] == recon["overall_pred_tweedie_mean"] == 8216.41
        assert overall["overall_pred_twopart_mean"] == recon["overall_pred_twopart_mean"] == 9781.06

        # 4. Assert Tweedie Observable Decile Reconciliation (Group-level observed-vs-predicted)
        strat_tw = data["stratification_analysis_tweedie_observable"]
        recon_tw = data["reconciliation_summary_tweedie_observable"]
        total_tw_count = sum(d["count"] for d in strat_tw)
        assert total_tw_count == recon_tw["test_sample_size"] == 3755
        assert abs(recon_tw["overall_observed_mean"] - recon_tw["count_weighted_observed_mean"]) <= 0.05
        assert abs(recon_tw["overall_pred_tweedie_obs_mean"] - recon_tw["count_weighted_pred_tweedie_obs_mean"]) <= 0.05
        assert recon_tw["overall_pred_tweedie_obs_mean"] == 8177.92
        assert recon_tw["reconciled"] is True

    def test_variance_convention_and_r2_identity(self):
        """
        Verifies variance conventions: population variance (ddof=0) vs sample variance (ddof=1)
        and asserts the mathematical identity R2 = 1 - SS_res / SS_tot = 1 - RMSE^2 / Var_pop (ddof=0).
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        metrics_file = os.path.join(base_dir, "artifacts", "evaluation_metrics.json")
        with open(metrics_file, "r") as f:
            data = json.load(f)

        meta = data["metadata"]
        var_pop = meta["test_population_variance_ddof0"]
        var_sample = meta["test_sample_variance_ddof1"]

        assert var_pop == 602354051.95
        assert var_sample == 602514508.54
        assert meta["test_variance_raw_dollars"] == 602354051.95

        # Check that reported R2 for XGBoost Observable model strictly matches population variance identity
        reg_obs = data["regressors"]["XGBoost_ObservableOnly_Unweighted"]
        rmse = reg_obs["rmse_unweighted"]
        r2_reported = reg_obs["r2_unweighted"]

        r2_from_pop_var = 1.0 - (rmse**2 / var_pop)
        r2_from_sample_var = 1.0 - (rmse**2 / var_sample)

        # Strictly agrees with population variance (ddof=0)
        assert abs(r2_reported - round(r2_from_pop_var, 4)) <= 0.0001
        # Confirms discrepancy if sample variance (ddof=1) were mistakenly used
        assert round(r2_from_pop_var, 4) != round(r2_from_sample_var, 4)

    def test_classifier_deployment_parity_and_imputed_comparison(self):
        """
        Verifies that 11-feature observable classifier matches or beats 14-feature
        deployment-imputed classifier on Brier Skill Score, confirming deployment recommendation.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        metrics_file = os.path.join(base_dir, "artifacts", "evaluation_metrics.json")
        with open(metrics_file, "r") as f:
            data = json.load(f)

        tgt2 = data["classifiers"]["target_weighted_p90"]
        lr_obs = tgt2["Logistic_Regression_ObservableOnly"]
        lr_imp = tgt2["Logistic_Regression_14Feat_DeploymentImputed"]
        lr_oracle = tgt2["Logistic_Regression_14Feat_ActualMEPS_Oracle"]

        # Observable model achieves positive skill score and beats imputed model
        assert lr_obs["survey_weighted_brier_skill_score"] > 0
        assert lr_obs["survey_weighted_brier_skill_score"] >= lr_imp["survey_weighted_brier_skill_score"]
        # Oracle survey features yield higher skill but are not available at frontend inference time
        assert lr_oracle["survey_weighted_brier_skill_score"] > lr_obs["survey_weighted_brier_skill_score"]

    def test_deployed_artifact_feature_schemas_and_counts(self):
        """Verifies exact feature counts for every deployed model artifact."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        art_dir = os.path.join(base_dir, "artifacts")

        # Observable 11-feature artifacts
        with open(os.path.join(base_dir, "risk_model.pkl"), "rb") as f:
            m_primary = pickle.load(f)
        assert m_primary.n_features_in_ == 11

        with open(os.path.join(art_dir, "risk_model_observable.pkl"), "rb") as f:
            m_obs = pickle.load(f)
        assert m_obs.n_features_in_ == 11

        with open(os.path.join(art_dir, "risk_model_tweedie_observable.pkl"), "rb") as f:
            tw_obs = pickle.load(f)
        assert tw_obs.n_features_in_ == 11

        with open(os.path.join(art_dir, "risk_model_classifier_observable.pkl"), "rb") as f:
            cls_obs = pickle.load(f)
        assert cls_obs.n_features_in_ == 11

        # 14-feature canonical models (with documented conditional expectation imputation paths)
        with open(os.path.join(art_dir, "risk_model_14feat_full.pkl"), "rb") as f:
            m_14 = pickle.load(f)
        assert m_14.n_features_in_ == 14

        with open(os.path.join(art_dir, "risk_model_tweedie.pkl"), "rb") as f:
            tw_14 = pickle.load(f)
        assert tw_14.n_features_in_ == 14

        with open(os.path.join(art_dir, "risk_model_classifier.pkl"), "rb") as f:
            cls_14 = pickle.load(f)
        assert cls_14.n_features_in_ == 14

    def test_target2_classifier_survey_weighted_estimands(self):
        """
        Verifies Target 2 reports both unweighted and survey-weighted Brier scores & skill scores.
        Asserts exact arithmetic reconciliation between prevalence, baseline probability, and Brier score.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        metrics_file = os.path.join(base_dir, "artifacts", "evaluation_metrics.json")
        with open(metrics_file, "r") as f:
            data = json.load(f)

        tgt2 = data["classifiers"]["target_weighted_p90"]
        base = tgt2["Constant_Prevalence_Baseline"]
        lr_w = tgt2["Logistic_Regression_WeightedFit"]

        # Baseline estimands
        assert base["brier_score"] == 0.1059
        assert base["survey_weighted_brier"] == 0.0941
        assert base["mean_predicted_prob"] == 0.0999

        # Exact arithmetic audit reconciliation:
        audit = base["exact_arithmetic_audit"]
        p_hat = audit["constant_baseline_prediction"]  # ~0.099888
        y_bar_w = audit["test_survey_weighted_outcome_prevalence"]  # ~0.105134
        brier_recomputed = y_bar_w * (1.0 - 2.0 * p_hat) + (p_hat ** 2)
        assert abs(brier_recomputed - audit["test_survey_weighted_baseline_brier"]) < 1e-6
        assert round(brier_recomputed, 4) == base["survey_weighted_brier"] == 0.0941

        # Weighted logistic regression estimands
        assert lr_w["brier_score"] == 0.0901
        assert lr_w["brier_skill_score"] == 0.1491
        assert lr_w["survey_weighted_brier"] == 0.0817
        assert lr_w["survey_weighted_brier_skill_score"] == 0.1314


class TestInferenceEngineSmokeTests:
    """
    Software smoke tests for inference execution, validation, and error handling.
    NOTE: These verify software execution integrity and input/output contracts, NOT clinical validity.
    """

    def test_smoke_inference_healthy_profile(self):
        res = calculate_risk({"age": 25, "gender": "female", "diseaseInput": ""})
        assert "risk_score" in res
        assert "health_score" in res
        assert "premium" in res
        assert "high_cost_probability" in res
        assert "data_parity_diagnostics" in res
        assert res["risk_score"] > 0
        assert 0 <= res["health_score"] <= 100
        # Check that unobserved SAQ variables were imputed via conditional expectations
        diag = res["data_parity_diagnostics"]
        assert "perceived_health" in diag["features_imputed"]
        assert "k6_distress" in diag["features_imputed"]
        assert diag["imputation_method"] == "conditional_expectation_by_age_and_comorbidity"

    def test_smoke_inference_multimorbid_profile(self):
        res_healthy = calculate_risk({"age": 25, "gender": "female", "diseaseInput": ""})
        res_sick = calculate_risk({"age": 70, "gender": "male", "diseaseInput": "Heart attack, Diabetes, Stroke, Cancer"})
        assert res_sick["risk_score"] > 1500
        assert res_sick["health_score"] < res_healthy["health_score"]
        assert res_sick["high_cost_probability"] > res_healthy["high_cost_probability"]

    def test_unobserved_vs_explicit_input_handling(self):
        # Case 1: unobserved distress
        res_default = calculate_risk({"age": 30, "gender": "male", "diseaseInput": ""})
        # Case 2: explicit high distress (tracks in diagnostics)
        res_explicit = calculate_risk({"age": 30, "gender": "male", "diseaseInput": "", "k6_distress": 20})
        # Explicit high distress is reported as observed vs imputed in diagnostics
        assert "k6_distress" in res_explicit["data_parity_diagnostics"]["features_observed"]
        assert "k6_distress" in res_default["data_parity_diagnostics"]["features_imputed"]

        # Case 3: observable condition affects 11-feature deployment predictions
        res_condition = calculate_risk({"age": 30, "gender": "male", "diseaseInput": "hypertension"})
        assert res_condition["risk_score"] > res_default["risk_score"]
        assert res_condition["health_score"] < res_default["health_score"]

    def test_input_validation_errors(self):
        with pytest.raises(ValueError, match="Missing required field"):
            calculate_risk({})

        with pytest.raises(ValueError, match="Age out of plausible range"):
            calculate_risk({"age": -10})

        with pytest.raises(ValueError, match="Age out of plausible range"):
            calculate_risk({"age": 150})

        with pytest.raises(ValueError, match="must be a positive number"):
            calculate_risk({"age": "not-a-number"})

    def test_nlp_condition_parser(self):
        cardio, metabolic, resp, onco, msk, psych = parse_clinical_conditions("Asthma and high cholesterol")
        assert resp == 1
        assert metabolic == 1
        assert cardio == 0

    def test_nlp_condition_parser_ambiguity_and_missing_handling(self):
        """Verifies that missing or ambiguous symptoms do not silently invent diagnoses."""
        # Case 1: Empty text produces all zeroes
        assert parse_clinical_conditions("") == (0, 0, 0, 0, 0, 0)
        assert parse_clinical_conditions(None) == (0, 0, 0, 0, 0, 0)

        # Case 2: Ambiguous or acute non-chronic symptoms produce all zeroes
        ambiguous = parse_clinical_conditions("Mild headache, occasional fatigue, nausea")
        assert ambiguous == (0, 0, 0, 0, 0, 0)

    def test_nlp_condition_parser_explicit_negations(self):
        """
        Explicit tests asserting negative statements NEVER trigger positive condition flags.
        Distinguishes explicitly reported absence of a condition from missing or unmentioned input.
        """
        from risk_engine import parse_clinical_conditions_detailed

        # Negative statements must NOT turn into positive condition flags
        assert parse_clinical_conditions("no history of hypertension")[0] == 0
        assert parse_clinical_conditions("patient denies hypertension")[0] == 0
        assert parse_clinical_conditions("no diabetes")[1] == 0
        assert parse_clinical_conditions("denies diabetes, has asthma") == (0, 0, 1, 0, 0, 0)
        assert parse_clinical_conditions("without asthma")[2] == 0
        assert parse_clinical_conditions("negative for cancer")[3] == 0
        assert parse_clinical_conditions("no arthritis or joint pain")[4] == 0
        assert parse_clinical_conditions("denies depression or anxiety")[5] == 0
        assert parse_clinical_conditions("no history of hypertension, diagnosed with type 2 diabetes") == (0, 1, 0, 0, 0, 0)

        # Distinguish explicit absence from missing/unmentioned input
        detailed = parse_clinical_conditions_detailed("no history of hypertension")
        assert "cardio" in detailed["explicitly_negated"]
        assert len(detailed["explicitly_present"]) == 0
        assert "cardio" not in detailed["unmentioned"]
        assert "metabolic" in detailed["unmentioned"]
        assert len(detailed["unresolved_semantic_limitations"]) > 0

    def test_nlp_condition_parser_same_cluster_negation_and_affirmation(self):
        """
        Tests that negating one condition in a cluster does NOT suppress an affirmed condition in that same cluster.
        Condition-level negation/affirmation must be preserved until cluster features are constructed.
        """
        from risk_engine import parse_clinical_conditions_detailed, parse_clinical_conditions

        # Test Case 1: "no hypertension, but prior stroke" -> stroke affirmed (cardio=2), hypertension negated
        cardio, metabolic, resp, onco, msk, psych = parse_clinical_conditions("no hypertension, but prior stroke")
        assert cardio == 2, f"Cardio should be 2 (stroke affirmed), got {cardio}"
        det_cardio = parse_clinical_conditions_detailed("no hypertension, but prior stroke")
        assert "cardio" in det_cardio["explicitly_present"]
        assert "cardio:stroke" in det_cardio["conditions_affirmed_detail"]
        assert "cardio:hypertension" in det_cardio["conditions_negated_detail"]

        # Test Case 2: "no asthma, but COPD" -> COPD affirmed (resp=2), asthma negated
        cardio, metabolic, resp, onco, msk, psych = parse_clinical_conditions("no asthma, but COPD")
        assert resp == 2, f"Respiratory should be 2 (COPD affirmed), got {resp}"
        det_resp = parse_clinical_conditions_detailed("no asthma, but COPD")
        assert "respiratory" in det_resp["explicitly_present"]
        assert "respiratory:copd" in det_resp["conditions_affirmed_detail"]
        assert "respiratory:asthma" in det_resp["conditions_negated_detail"]

        # Test Case 3: "no diabetes, but high cholesterol" -> metabolic=1 (cholesterol affirmed), diabetes negated
        cardio, metabolic, resp, onco, msk, psych = parse_clinical_conditions("no diabetes, but high cholesterol")
        assert metabolic == 1, f"Metabolic should be 1 (cholesterol affirmed), got {metabolic}"
        det_met = parse_clinical_conditions_detailed("no diabetes, but high cholesterol")
        assert "metabolic" in det_met["explicitly_present"]
        assert "metabolic:hyperlipidemia" in det_met["conditions_affirmed_detail"]
        assert "metabolic:diabetes" in det_met["conditions_negated_detail"]

    def test_missing_vs_negative_condition_and_insufficient_input_handling(self):
        """
        Verifies that absent or unparseable input is distinguished from confirmed absence of disease.
        Asserts insufficient-input response when structured inputs are required.
        """
        from risk_engine import parse_clinical_conditions_detailed, calculate_risk

        # 1. Missing / empty text
        det_empty = parse_clinical_conditions_detailed("")
        assert det_empty["input_status"] == "missing_or_empty"
        assert len(det_empty["explicitly_present"]) == 0
        assert len(det_empty["explicitly_negated"]) == 0
        assert len(det_empty["unmentioned"]) == 6

        # 2. Unparseable text (non-clinical words)
        det_unparse = parse_clinical_conditions_detailed("Patient likes apples and walks in the park")
        assert det_unparse["input_status"] == "unparseable_or_unmentioned"
        assert len(det_unparse["explicitly_present"]) == 0
        assert len(det_unparse["unmentioned"]) == 6

        # 3. Explicit general negation of all conditions
        det_healthy = parse_clinical_conditions_detailed("Healthy patient, no chronic medical conditions")
        assert det_healthy["input_status"] == "explicitly_negated_general"
        assert len(det_healthy["explicitly_negated"]) == 6
        assert len(det_healthy["unmentioned"]) == 0

        # 4. Strict structured input requirement returns insufficient_input response when unmentioned
        res_insufficient = calculate_risk({"age": 35, "gender": "male", "diseaseInput": ""}, require_structured_inputs=True)
        assert res_insufficient["status"] == "insufficient_input"
        assert "unmentioned_clusters" in res_insufficient
        assert len(res_insufficient["unmentioned_clusters"]) == 6

        # 5. Default baseline calculation warns that absence of mention is NOT confirmed absence
        res_default = calculate_risk({"age": 35, "gender": "male", "diseaseInput": ""}, require_structured_inputs=False)
        diag = res_default["data_parity_diagnostics"]
        assert diag["clinical_condition_parsing"]["input_status"] == "missing_or_empty"
        assert diag["input_completeness_warning"] is not None
        assert "NOT a clinically confirmed healthy profile" in diag["input_completeness_warning"]
        assert "clinical absence unconfirmed" in res_default["top_risk_factors"][0]

    def test_classifier_target_declarations_and_artifacts(self):
        """
        Verifies that every serialized classifier artifact has an explicitly declared target in training_metadata.json
        and that target definitions, thresholds, and feature schemas reconcile.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        art_dir = os.path.join(base_dir, "artifacts")
        meta_file = os.path.join(art_dir, "training_metadata.json")
        with open(meta_file, "r") as f:
            metadata = json.load(f)

        assert "classifier_artifacts_metadata" in metadata
        cls_meta = metadata["classifier_artifacts_metadata"]

        # Target 2 observable classifier (11 features, threshold ~17,827.41)
        assert "risk_model_classifier_observable_weighted_p90.pkl" in cls_meta
        tgt2_obs = cls_meta["risk_model_classifier_observable_weighted_p90.pkl"]
        assert tgt2_obs["target_name"] == "Target 2: Survey-Weighted Population Top Decile"
        assert tgt2_obs["feature_count"] == 11
        assert abs(tgt2_obs["target_threshold_dollars"] - 17827.41) < 1.0

        # Target 1 observable classifier (11 features, threshold $20,360.50)
        assert "risk_model_classifier_observable_unweighted_p90.pkl" in cls_meta
        tgt1_obs = cls_meta["risk_model_classifier_observable_unweighted_p90.pkl"]
        assert tgt1_obs["target_name"] == "Target 1: Unweighted Sample Top Decile"
        assert tgt1_obs["feature_count"] == 11
        assert tgt1_obs["target_threshold_dollars"] == 20360.50

        # Target 1 14-feature benchmark (14 features, threshold $20,360.50)
        assert "risk_model_classifier.pkl" in cls_meta
        tgt1_14 = cls_meta["risk_model_classifier.pkl"]
        assert tgt1_14["target_name"] == "Target 1: Unweighted Sample Top Decile"
        assert tgt1_14["feature_count"] == 14

        # Verify all serialized files exist and feature counts match
        for art_name, info in cls_meta.items():
            fpath = os.path.join(art_dir, art_name)
            assert os.path.exists(fpath), f"Missing artifact {art_name}"
            with open(fpath, "rb") as f:
                model = pickle.load(f)
            if hasattr(model, "n_features_in_"):
                assert model.n_features_in_ == info["feature_count"]
            elif hasattr(model, "calibrated_classifiers_"):
                # CalibratedClassifierCV
                assert model.calibrated_classifiers_[0].estimator.n_features_in_ == info["feature_count"]

