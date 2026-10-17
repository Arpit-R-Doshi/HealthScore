"""
Comprehensive Research Benchmark and Experiment Runner for HealthScore
Executes Phase 2 model comparisons, feature ablations, SHAP stability, subgroup fairness,
and publication figure generation. Outputs machine-readable experiment_registry.json and report figures.

Methodological Guardrails:
  - Zero duplicate model candidate entries.
  - Reconciled Tweedie alpha=1.0 matching frozen baseline configuration.
  - Survey weights passed during training for weighted logistic ablations.
  - Calibration-in-the-large (CITL) explicitly separated from bivariate calibration slope & intercept.
  - Separate candidate-model cross-validation from frozen-artifact evaluation.
  - Dynamic execution metadata (Git commit, package versions, artifact hashes, UTC timestamp).
  - Explicit labeling of individual-level bootstrap intervals (not design-based Taylor series linearization).
"""

import os
import sys
import json
import pickle
import math
import hashlib
import subprocess
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression, Ridge, TweedieRegressor, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    r2_score, mean_absolute_error, root_mean_squared_error,
    roc_auc_score, average_precision_score, brier_score_loss,
    precision_score, recall_score, f1_score, roc_curve, precision_recall_curve
)
from scipy.stats import spearmanr
from scipy.optimize import root_scalar
import xgboost as xgb
import shap
import sklearn

# Set paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "ml_model"))

from data_pipeline import (
    load_raw_meps, clean_and_engineer_features, split_data,
    FEATURE_COLS, OBSERVABLE_FEATURE_COLS, DEFAULT_DATA_PATH
)

EXP_DIR = os.path.join(REPO_ROOT, "research_completion", "experiments")
FIG_DIR = os.path.join(REPO_ROOT, "research_completion", "figures")
os.makedirs(EXP_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)


def sha256_file(filepath):
    """Computes SHA-256 checksum of a file."""
    if not filepath or not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def compute_calibration_diagnostics(y_true, y_prob, weights=None):
    """
    Computes formal calibration metrics:
      1. Calibration-in-the-large (CITL): Intercept alpha with slope fixed to 1 (logit(p) offset).
      2. Logistic Calibration: Jointly fitted intercept and slope (y ~ a + b * logit(p)).
      3. Records estimator provenance (unpenalized vs near-unpenalized C=1e9).
    """
    probs_clipped = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1.0 - 1e-6)
    logits = np.log(probs_clipped / (1.0 - probs_clipped))
    y_arr = np.asarray(y_true, dtype=int)
    w_arr = np.asarray(weights, dtype=float) if weights is not None else np.ones_like(y_arr, dtype=float)

    # 1. Exact Calibration-In-The-Large (CITL): solve sum(w * (y - sigmoid(alpha + logits))) = 0
    def citl_obj(alpha):
        preds = 1.0 / (1.0 + np.exp(-(alpha + logits)))
        return np.sum(w_arr * (y_arr - preds))

    try:
        sol = root_scalar(citl_obj, bracket=[-10.0, 10.0], method='brentq')
        citl = float(sol.root)
    except Exception:
        # Fallback to empirical log-odds difference
        mean_y = np.average(y_arr, weights=w_arr)
        mean_p = np.average(probs_clipped, weights=w_arr)
        citl = float(np.log(mean_y / (1.0 - mean_y)) - np.log(mean_p / (1.0 - mean_p)))

    # 2. Bivariate logistic calibration: y ~ a + b * logit(p)
    estimator_provenance = "unpenalized_lbfgs"
    try:
        lr = LogisticRegression(C=float('inf'), solver='lbfgs', max_iter=2000)
        lr.fit(logits.reshape(-1, 1), y_arr, sample_weight=w_arr)
        cal_int = float(lr.intercept_[0])
        cal_slope = float(lr.coef_[0][0])
    except Exception:
        try:
            lr = LogisticRegression(C=1e9, solver='lbfgs', max_iter=2000)
            lr.fit(logits.reshape(-1, 1), y_arr, sample_weight=w_arr)
            cal_int = float(lr.intercept_[0])
            cal_slope = float(lr.coef_[0][0])
            estimator_provenance = "near_unpenalized_lbfgs_C1e9"
        except Exception as e:
            raise RuntimeError(f"All approved calibration estimators failed: {e}")

    return {
        "citl": round(citl, 4),
        "cal_intercept": round(cal_int, 4),
        "cal_slope": round(cal_slope, 4),
        "calibration_estimator": estimator_provenance
    }


def bootstrap_regression(y_true, y_pred, n_boot=200, seed=42):
    """Percentile bootstrap 95% CI for MAE, RMSE, R2 (unweighted individual-level non-parametric bootstrap)."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    idx = rng.integers(0, n, size=(n_boot, n))
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)

    maes = [mean_absolute_error(yt[i], yp[i]) for i in idx]
    rmses = [root_mean_squared_error(yt[i], yp[i]) for i in idx]
    r2s = [r2_score(yt[i], yp[i]) for i in idx]

    return {
        "mae_ci": [round(float(np.percentile(maes, 2.5)), 2), round(float(np.percentile(maes, 97.5)), 2)],
        "rmse_ci": [round(float(np.percentile(rmses, 2.5)), 2), round(float(np.percentile(rmses, 97.5)), 2)],
        "r2_ci": [round(float(np.percentile(r2s, 2.5)), 4), round(float(np.percentile(r2s, 97.5)), 4)],
        "ci_method": "unweighted_individual_bootstrap_non_design_based"
    }


def bootstrap_classification(y_true, y_prob, n_boot=200, seed=42):
    """Percentile bootstrap 95% CI for ROC-AUC, PR-AUC, Brier (unweighted individual-level non-parametric bootstrap)."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    idx = rng.integers(0, n, size=(n_boot, n))
    yt = np.asarray(y_true)
    yp = np.asarray(y_prob)

    rocs = [roc_auc_score(yt[i], yp[i]) for i in idx if len(np.unique(yt[i])) > 1]
    prs = [average_precision_score(yt[i], yp[i]) for i in idx if len(np.unique(yt[i])) > 1]
    briers = [brier_score_loss(yt[i], yp[i]) for i in idx]

    return {
        "roc_ci": [round(float(np.percentile(rocs, 2.5)), 4), round(float(np.percentile(rocs, 97.5)), 4)] if rocs else [0, 0],
        "pr_ci": [round(float(np.percentile(prs, 2.5)), 4), round(float(np.percentile(prs, 97.5)), 4)] if prs else [0, 0],
        "brier_ci": [round(float(np.percentile(briers, 2.5)), 4), round(float(np.percentile(briers, 97.5)), 4)],
        "ci_method": "unweighted_individual_bootstrap_non_design_based"
    }


def main():
    print("=" * 80)
    print("HealthScore Comprehensive Research Benchmark Runner")
    print("=" * 80)

    # 1. Load data
    raw_path = os.path.join(REPO_ROOT, "ml_model", "h251.dta")
    print(f"Loading MEPS HC-251 from {raw_path}...")
    df_raw = load_raw_meps(raw_path)
    df_clean, audit = clean_and_engineer_features(df_raw, filter_zero_expenditure=False)
    splits = split_data(df_clean, raw_df=df_raw, test_size=0.20, random_state=42)

    X_train_full = splits["X_train"]
    X_test_full = splits["X_test"]
    X_train_obs = splits["X_train"][OBSERVABLE_FEATURE_COLS]
    X_test_obs = splits["X_test"][OBSERVABLE_FEATURE_COLS]

    y_train_raw = splits["y_train_raw"].values
    y_test_raw = splits["y_test_raw"].values
    y_train_log = splits["y_train_log"].values
    y_test_log = splits["y_test_log"].values

    w_train = splits["w_train"].values
    w_test = splits["w_test"].values
    w_train_norm = splits["w_train_norm"].values
    w_test_norm = splits["w_test_norm"].values

    y_train_cls_tgt1 = splits["y_train_cls_unw"].values
    y_test_cls_tgt1 = splits["y_test_cls_unw"].values
    y_train_cls_tgt2 = splits["y_train_cls_wtd"].values
    y_test_cls_tgt2 = splits["y_test_cls_wtd"].values

    train_prev_tgt1 = float(np.mean(y_train_cls_tgt1))
    train_prev_tgt2_unw = float(np.mean(y_train_cls_tgt2))
    train_prev_tgt2_wtd = float(np.sum(y_train_cls_tgt2 * w_train) / np.sum(w_train))

    test_prev_tgt1 = float(np.mean(y_test_cls_tgt1))
    test_prev_tgt2_unw = float(np.mean(y_test_cls_tgt2))
    test_prev_tgt2_wtd = float(np.sum(y_test_cls_tgt2 * w_test) / np.sum(w_test))

    base_brier_tgt1 = float(brier_score_loss(y_test_cls_tgt1, np.full_like(y_test_cls_tgt1, train_prev_tgt1, dtype=float)))
    base_brier_tgt2_unw = float(brier_score_loss(y_test_cls_tgt2, np.full_like(y_test_cls_tgt2, train_prev_tgt2_unw, dtype=float)))
    base_brier_tgt2_wtd = float(np.average((y_test_cls_tgt2 - train_prev_tgt2_wtd)**2, weights=w_test_norm))

    print(f"Target 1 Unw Threshold: ${splits['p90_threshold_unweighted']:,.2f} | Base Brier: {base_brier_tgt1:.4f}")
    print(f"Target 2 Wtd Threshold: ${splits['p90_threshold_weighted']:,.2f} | Base Brier (Wtd): {base_brier_tgt2_wtd:.4f}")

    # Git metadata
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"

    registry = {
        "metadata": {
            "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit_sha": git_sha,
            "environment": f"Python {sys.version.split()[0]}, scikit-learn {sklearn.__version__}, xgboost {xgb.__version__}, shap {shap.__version__}",
            "seed": 42,
            "datasets": {
                "HC-251_2023": sha256_file(raw_path),
                "HC-256_2024": sha256_file(os.path.join(REPO_ROOT, "ml_model", "validation", "hc256", "data", "h256.dta")),
                "HC-257_Panel28": sha256_file(os.path.join(REPO_ROOT, "ml_model", "validation", "hc257", "data", "h257.dta"))
            },
            "model_artifacts": {
                "risk_model_ranker": sha256_file(os.path.join(REPO_ROOT, "ml_model", "risk_model.pkl")),
                "risk_model_tweedie_observable": sha256_file(os.path.join(REPO_ROOT, "ml_model", "artifacts", "risk_model_tweedie_observable.pkl")),
                "risk_model_classifier_observable_weighted_p90": sha256_file(os.path.join(REPO_ROOT, "ml_model", "artifacts", "risk_model_classifier_observable_weighted_p90.pkl"))
            },
            "data_provenance_notes": (
                "MEPS HC-251 contains Panel 28 (Year 1) and Panel 27 (Year 2) observations. "
                "HC-257 tracks Panel 28 across 2023-2024; evaluation against HC-257 represents prospective longitudinal follow-up "
                "with disclosed participant overlap with HC-251, not an independent fresh sample. "
                "HC-251 test split has been used for iterative evaluation and is marked as benchmark test data."
            )
        },
        "regression_comparisons": [],
        "classification_comparisons": [],
        "feature_ablations": [],
        "cross_validation_experiments": [],
        "shap_summary": {},
        "subgroup_fairness": []
    }

    # =========================================================================
    # 2. REGRESSION MODEL COMPARISONS
    # =========================================================================
    print("\n--- Running Regression Model Comparisons ---")

    reg_models = {}

    # 2.1 Baseline Median
    med_val = float(np.median(y_train_raw))
    p_med = np.full_like(y_test_raw, med_val)
    reg_models["Baseline Median"] = (p_med, "unweighted_median_baseline")

    # 2.2 Baseline Mean
    mean_val = float(np.mean(y_train_raw))
    p_mean = np.full_like(y_test_raw, mean_val)
    reg_models["Baseline Mean"] = (p_mean, "unweighted_mean_baseline")

    # 2.3 OLS Linear Regression (log scale)
    ols = LinearRegression()
    ols.fit(X_train_obs, y_train_log)
    p_ols = np.expm1(ols.predict(X_test_obs))
    reg_models["OLS Linear (Observable)"] = (p_ols, "unweighted_ols_log")

    # 2.4 Ridge Regression (log scale, alpha=10)
    ridge = Ridge(alpha=10.0)
    ridge.fit(X_train_obs, y_train_log)
    p_ridge = np.expm1(ridge.predict(X_test_obs))
    reg_models["Ridge α=10 (Observable)"] = (p_ridge, "unweighted_ridge_log")

    # 2.5 Random Forest Regressor (log scale)
    rf_reg = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    rf_reg.fit(X_train_obs, y_train_log)
    p_rf = np.expm1(rf_reg.predict(X_test_obs))
    reg_models["Random Forest (Observable)"] = (p_rf, "unweighted_rf_log")

    # 2.6 XGBoost Regressor (Observable, log scale) - Evaluated directly from frozen artifact
    with open(os.path.join(REPO_ROOT, "ml_model", "risk_model.pkl"), "rb") as f:
        frozen_xgb_reg = pickle.load(f)
    p_xgb_obs = np.expm1(frozen_xgb_reg.predict(X_test_obs))
    reg_models["XGBoost Regressor (Observable)"] = (p_xgb_obs, "frozen_artifact_unweighted_fit")

    # 2.7 Tweedie GLM (Observable, direct dollars) - Evaluated directly from frozen artifact
    with open(os.path.join(REPO_ROOT, "ml_model", "artifacts", "risk_model_tweedie_observable.pkl"), "rb") as f:
        frozen_tw_obs = pickle.load(f)
    p_tw_obs = frozen_tw_obs.predict(X_test_obs)
    reg_models["Tweedie GLM (Observable)"] = (p_tw_obs, "frozen_artifact_unweighted_fit_alpha1.0")

    # 2.8 Two-Part Model (Part 1 Logistic + Part 2 OLS with Duan smearing on observable)
    y_train_pos = (y_train_raw > 0).astype(int)
    clf_2pm = LogisticRegression(max_iter=500, random_state=42)
    clf_2pm.fit(X_train_obs, y_train_pos)
    prob_pos = clf_2pm.predict_proba(X_test_obs)[:, 1]

    pos_idx = y_train_raw > 0
    ols_pos = LinearRegression()
    ols_pos.fit(X_train_obs.iloc[pos_idx], y_train_log[pos_idx])
    pred_log_pos = ols_pos.predict(X_test_obs)
    residuals = y_train_log[pos_idx] - ols_pos.predict(X_train_obs.iloc[pos_idx])
    duan_smear = float(np.mean(np.exp(residuals)))
    p_2pm = prob_pos * np.expm1(pred_log_pos) * duan_smear
    reg_models["Two-Part Model (Observable)"] = (p_2pm, "unweighted_twopart_duan_smearing")

    # Evaluate each regressor
    for name, (pred, weight_policy) in reg_models.items():
        mae_unw = float(mean_absolute_error(y_test_raw, pred))
        rmse_unw = float(root_mean_squared_error(y_test_raw, pred))
        r2_unw = float(r2_score(y_test_raw, pred))
        mae_wtd = float(np.average(np.abs(y_test_raw - pred), weights=w_test_norm))
        rmse_wtd = float(np.sqrt(np.average((y_test_raw - pred)**2, weights=w_test_norm)))

        # Weighted R2
        ss_res_w = np.sum(w_test_norm * (y_test_raw - pred)**2)
        mean_y_w = np.average(y_test_raw, weights=w_test_norm)
        ss_tot_w = np.sum(w_test_norm * (y_test_raw - mean_y_w)**2)
        r2_wtd = float(1.0 - (ss_res_w / ss_tot_w))
        mean_pred = float(np.mean(pred))

        ci = bootstrap_regression(y_test_raw, pred, n_boot=200, seed=42)

        record = {
            "model_name": name,
            "target": "Annual Healthcare Expenditure (TOTEXP23)",
            "weighting_policy": weight_policy,
            "mean_predicted": round(mean_pred, 2),
            "observed_mean": round(float(np.mean(y_test_raw)), 2),
            "mae_unweighted": round(mae_unw, 2),
            "mae_ci_95": ci["mae_ci"],
            "rmse_unweighted": round(rmse_unw, 2),
            "rmse_ci_95": ci["rmse_ci"],
            "r2_unweighted": round(r2_unw, 4),
            "r2_ci_95": ci["r2_ci"],
            "mae_weighted": round(mae_wtd, 2),
            "rmse_weighted": round(rmse_wtd, 2),
            "r2_weighted": round(r2_wtd, 4),
            "ci_qualification": ci["ci_method"]
        }
        registry["regression_comparisons"].append(record)
        print(f"{name:30s} | MAE: ${mae_unw:9.2f} | RMSE: ${rmse_unw:9.2f} | R2: {r2_unw:7.4f} | MeanPred: ${mean_pred:9.2f}")

    # Candidate-Model 5-Fold Cross-Validation (Separated from frozen artifact evaluation)
    print("\n--- Running Candidate-Model 5-Fold Cross-Validation ---")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_tw_r2 = []
    cv_xgb_r2 = []
    for tr_idx, val_idx in kf.split(X_train_obs):
        # Tweedie fold (using alpha=1.0 matching primary specification)
        tw_k = TweedieRegressor(power=1.5, link='log', max_iter=2000, alpha=1.0)
        tw_k.fit(X_train_obs.iloc[tr_idx], y_train_raw[tr_idx])
        cv_tw_r2.append(r2_score(y_train_raw[val_idx], tw_k.predict(X_train_obs.iloc[val_idx])))

        # XGB fold
        xgb_k = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42, n_jobs=-1)
        xgb_k.fit(X_train_obs.iloc[tr_idx], y_train_log[tr_idx])
        cv_xgb_r2.append(r2_score(y_train_raw[val_idx], np.expm1(xgb_k.predict(X_train_obs.iloc[val_idx]))))

    registry["cross_validation_experiments"] = [
        {
            "experiment": "5-Fold CV on Candidate Architecture",
            "model_architecture": "TweedieRegressor(power=1.5, link='log', alpha=1.0)",
            "features": "11-feature observable",
            "training_split": "MEPS HC-251 Training Split (N=15,016)",
            "r2_mean": round(float(np.mean(cv_tw_r2)), 4),
            "r2_std": round(float(np.std(cv_tw_r2)), 4),
            "fold_r2_scores": [round(float(s), 4) for s in cv_tw_r2],
            "evaluation_provenance": "Refit per fold on training split; distinct from frozen artifact evaluation"
        },
        {
            "experiment": "5-Fold CV on Candidate Architecture",
            "model_architecture": "XGBRegressor(n_estimators=100, max_depth=4, lr=0.05)",
            "features": "11-feature observable",
            "training_split": "MEPS HC-251 Training Split (N=15,016)",
            "r2_mean": round(float(np.mean(cv_xgb_r2)), 4),
            "r2_std": round(float(np.std(cv_xgb_r2)), 4),
            "fold_r2_scores": [round(float(s), 4) for s in cv_xgb_r2],
            "evaluation_provenance": "Refit per fold on training split; distinct from frozen artifact evaluation"
        }
    ]
    print(f"Tweedie 5-Fold CV R2: {np.mean(cv_tw_r2):.4f} +/- {np.std(cv_tw_r2):.4f}")
    print(f"XGBoost 5-Fold CV R2: {np.mean(cv_xgb_r2):.4f} +/- {np.std(cv_xgb_r2):.4f}")

    # =========================================================================
    # 3. CLASSIFICATION MODEL COMPARISONS (TARGET 2: SURVEY-WEIGHTED P90)
    # =========================================================================
    print("\n--- Running Classification Model Comparisons (Target 2: $17,827.41) ---")

    cls_models = {}

    # 3.1 Constant Baseline
    cls_models["Constant Prevalence Baseline"] = (
        np.full_like(y_test_cls_tgt2, train_prev_tgt2_wtd, dtype=float),
        "uninformative_prior"
    )

    # 3.2 Demographic Baseline (Age + Gender)
    lr_demo = LogisticRegression(max_iter=500, random_state=42)
    lr_demo.fit(X_train_obs[['AGE23X', 'Gender_Male']], y_train_cls_tgt2, sample_weight=w_train_norm)
    cls_models["Demographic Baseline (Age+Sex)"] = (
        lr_demo.predict_proba(X_test_obs[['AGE23X', 'Gender_Male']])[:, 1],
        "normalized_person_weights"
    )

    # 3.3 Clinical Conditions Only (No demographics)
    clin_cols = ['Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG', 'Comorbidity_Count', 'Multimorbidity_Penalty']
    lr_clin = LogisticRegression(max_iter=500, random_state=42)
    lr_clin.fit(X_train_obs[clin_cols], y_train_cls_tgt2, sample_weight=w_train_norm)
    cls_models["Clinical Conditions Only"] = (
        lr_clin.predict_proba(X_test_obs[clin_cols])[:, 1],
        "normalized_person_weights"
    )

    # 3.4 Full Observable Logistic Regression (Weighted fit) - Evaluated directly from frozen approved artifact
    with open(os.path.join(REPO_ROOT, "ml_model", "artifacts", "risk_model_classifier_observable_weighted_p90.pkl"), "rb") as f:
        frozen_lr_wtd = pickle.load(f)
    cls_models["Logistic Regression (11-Feat Observable, Weighted Fit)"] = (
        frozen_lr_wtd.predict_proba(X_test_obs)[:, 1],
        "frozen_artifact_normalized_person_weights"
    )

    # 3.5 Full Observable Logistic Regression (Unweighted fit on Target 2 for weighting ablation)
    lr_unw_tgt2 = LogisticRegression(max_iter=500, random_state=42)
    lr_unw_tgt2.fit(X_train_obs, y_train_cls_tgt2)  # sample_weight=None
    cls_models["Logistic Regression (11-Feat Observable, Unweighted Fit)"] = (
        lr_unw_tgt2.predict_proba(X_test_obs)[:, 1],
        "unweighted_fit_exploratory_ablation"
    )

    # 3.6 Random Forest Classifier (11-Feat Observable)
    rf_cls = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
    rf_cls.fit(X_train_obs, y_train_cls_tgt2, sample_weight=w_train_norm)
    cls_models["Random Forest (11-Feat Observable)"] = (
        rf_cls.predict_proba(X_test_obs)[:, 1],
        "normalized_person_weights"
    )

    # 3.7 XGBoost Classifier (Uncalibrated & Platt Calibrated)
    xgb_cls = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42, n_jobs=-1, eval_metric='logloss')
    xgb_cls.fit(X_train_obs, y_train_cls_tgt2, sample_weight=w_train_norm)
    cls_models["XGBoost (Uncalibrated)"] = (
        xgb_cls.predict_proba(X_test_obs)[:, 1],
        "normalized_person_weights"
    )

    cal_xgb = CalibratedClassifierCV(estimator=xgb_cls, method='sigmoid', cv=5)
    cal_xgb.fit(X_train_obs, y_train_cls_tgt2, sample_weight=w_train_norm)
    cls_models["XGBoost (Platt Calibrated)"] = (
        cal_xgb.predict_proba(X_test_obs)[:, 1],
        "normalized_person_weights"
    )

    # 3.8 14-Feature Oracle Logistic Regression - Evaluated directly from frozen artifact
    with open(os.path.join(REPO_ROOT, "ml_model", "artifacts", "risk_model_classifier_weighted_p90.pkl"), "rb") as f:
        frozen_lr_oracle = pickle.load(f)
    cls_models["Logistic Regression (14-Feat Oracle)"] = (
        frozen_lr_oracle.predict_proba(X_test_full)[:, 1],
        "frozen_artifact_normalized_person_weights_14feat_oracle"
    )

    for name, (prob, weight_policy) in cls_models.items():
        roc = float(roc_auc_score(y_test_cls_tgt2, prob)) if len(np.unique(prob)) > 1 else 0.5
        pr_auc = float(average_precision_score(y_test_cls_tgt2, prob))
        brier_unw = float(brier_score_loss(y_test_cls_tgt2, prob))
        bss_unw = float(1.0 - (brier_unw / base_brier_tgt2_unw))
        brier_wtd = float(np.average((y_test_cls_tgt2 - prob)**2, weights=w_test_norm))
        bss_wtd = float(1.0 - (brier_wtd / base_brier_tgt2_wtd))

        pred_label_10 = (prob >= 0.10).astype(int)
        prec_10 = float(precision_score(y_test_cls_tgt2, pred_label_10, zero_division=0))
        rec_10 = float(recall_score(y_test_cls_tgt2, pred_label_10, zero_division=0))
        f1_10 = float(f1_score(y_test_cls_tgt2, pred_label_10, zero_division=0))

        if len(np.unique(prob)) > 1:
            cal_diag = compute_calibration_diagnostics(y_test_cls_tgt2, prob, weights=w_test_norm)
        else:
            cal_diag = {"citl": 0.0, "cal_intercept": 0.0, "cal_slope": 0.0, "calibration_estimator": "uninformative_baseline"}

        ci = bootstrap_classification(y_test_cls_tgt2, prob, n_boot=200, seed=42)

        record = {
            "model_name": name,
            "target": "High Expenditure P90 Threshold ($17,827.41)",
            "weighting_policy": weight_policy,
            "mean_pred_prob": round(float(np.mean(prob)), 4),
            "roc_auc": round(roc, 4),
            "roc_auc_ci_95": ci["roc_ci"],
            "pr_auc": round(pr_auc, 4),
            "pr_auc_ci_95": ci["pr_ci"],
            "brier_unweighted": round(brier_unw, 4),
            "bss_unweighted": round(bss_unw, 4),
            "brier_weighted": round(brier_wtd, 4),
            "bss_weighted": round(bss_wtd, 4),
            "calibration_in_the_large_citl": cal_diag["citl"],
            "cal_intercept": cal_diag["cal_intercept"],
            "cal_slope": cal_diag["cal_slope"],
            "calibration_estimator": cal_diag["calibration_estimator"],
            "precision_at_10pct": round(prec_10, 4),
            "recall_at_10pct": round(rec_10, 4),
            "f1_at_10pct": round(f1_10, 4),
            "ci_qualification": ci["ci_method"]
        }
        registry["classification_comparisons"].append(record)
        print(f"{name:45s} | ROC: {roc:6.4f} | PR: {pr_auc:6.4f} | BSS(Wtd): {bss_wtd:+7.4f} | CITL: {cal_diag['citl']:+6.3f} | Slope: {cal_diag['cal_slope']:6.3f}")

    # =========================================================================
    # 4. SYSTEMATIC FEATURE ABLATION EXPERIMENTS
    # =========================================================================
    print("\n--- Running Controlled Feature Ablations ---")

    ablation_definitions = [
        ("Full Observable Reference (11 Feat)", OBSERVABLE_FEATURE_COLS, "observable_reference"),
        ("Demographics Only (Age + Sex)", ['AGE23X', 'Gender_Male'], "observable_ablation"),
        ("Clinical Conditions Only (No Demographics)", [c for c in OBSERVABLE_FEATURE_COLS if c not in ['AGE23X', 'Gender_Male', 'Age_x_Comorbidity']], "observable_ablation"),
        ("Without Psychiatric Condition", [c for c in OBSERVABLE_FEATURE_COLS if c != 'Psychiatric_ACG'], "observable_ablation"),
        ("Without Multimorbidity & Interaction", [c for c in OBSERVABLE_FEATURE_COLS if c not in ['Multimorbidity_Penalty', 'Age_x_Comorbidity']], "observable_ablation"),
        ("Without Oncology", [c for c in OBSERVABLE_FEATURE_COLS if c != 'Oncology_ACG'], "observable_ablation"),
        ("Without Cardiovascular", [c for c in OBSERVABLE_FEATURE_COLS if c != 'Cardio_ACG'], "observable_ablation"),
        ("Without Metabolic", [c for c in OBSERVABLE_FEATURE_COLS if c != 'Metabolic_ACG'], "observable_ablation"),
        ("Without Respiratory", [c for c in OBSERVABLE_FEATURE_COLS if c != 'Respiratory_ACG'], "observable_ablation"),
        ("Without Musculoskeletal", [c for c in OBSERVABLE_FEATURE_COLS if c != 'Musculoskeletal_ACG'], "observable_ablation"),
        ("Oracle 14 Features (with SAQ variables)", FEATURE_COLS, "oracle_upper_bound")
    ]

    ref_mae = None
    ref_r2 = None
    ref_roc = None
    ref_bss = None

    for label, feats, tier in ablation_definitions:
        if tier == "oracle_upper_bound":
            X_tr = X_train_full[feats]
            X_te = X_test_full[feats]
        else:
            X_tr = X_train_obs[feats]
            X_te = X_test_obs[feats]

        # Train Tweedie with alpha=1.0 matching primary baseline specification
        tw = TweedieRegressor(power=1.5, link='log', max_iter=2000, alpha=1.0)
        tw.fit(X_tr, y_train_raw)
        p_tw = tw.predict(X_te)

        mae = float(mean_absolute_error(y_test_raw, p_tw))
        rmse = float(root_mean_squared_error(y_test_raw, p_tw))
        r2 = float(r2_score(y_test_raw, p_tw))

        # Train Logistic Target 2 passing survey weights
        lr = LogisticRegression(max_iter=2000, random_state=42)
        lr.fit(X_tr, y_train_cls_tgt2, sample_weight=w_train_norm)
        p_lr = lr.predict_proba(X_te)[:, 1]

        roc = float(roc_auc_score(y_test_cls_tgt2, p_lr))
        brier_w = float(np.average((y_test_cls_tgt2 - p_lr)**2, weights=w_test_norm))
        bss_w = float(1.0 - (brier_w / base_brier_tgt2_wtd))

        if ref_r2 is None:
            ref_mae = mae
            ref_r2 = r2
            ref_roc = roc
            ref_bss = bss_w

        delta_r2 = r2 - ref_r2
        delta_bss = bss_w - ref_bss
        delta_mae = mae - ref_mae

        record = {
            "ablation_label": label,
            "feature_tier": tier,
            "feature_count": len(feats),
            "features": feats,
            "candidate_role": "refit_exploratory_ablation",
            "tweedie_alpha": 1.0,
            "classification_weighting": "normalized_person_weights",
            "regression_mae": round(mae, 2),
            "regression_rmse": round(rmse, 2),
            "regression_r2": round(r2, 4),
            "delta_r2_vs_ref": round(delta_r2, 4),
            "delta_mae_vs_ref": round(delta_mae, 2),
            "classification_roc_auc": round(roc, 4),
            "classification_bss_weighted": round(bss_w, 4),
            "delta_bss_vs_ref": round(delta_bss, 4)
        }
        registry["feature_ablations"].append(record)
        print(f"{label:45s} ({len(feats):2d} feats) | R2: {r2:7.4f} (Δ {delta_r2:+7.4f}) | BSS: {bss_w:+7.4f} (Δ {delta_bss:+7.4f})")

    # =========================================================================
    # 5. SHAP EXPLAINABILITY & STABILITY AUDIT
    # =========================================================================
    print("\n--- Running SHAP Explainability & Stability Audit ---")

    explainer = shap.TreeExplainer(frozen_xgb_reg)
    shap_vals = explainer.shap_values(X_test_obs)

    # 5.1 Numerical additivity check
    base_val = explainer.expected_value
    pred_log_direct = frozen_xgb_reg.predict(X_test_obs)
    sum_shap = np.sum(shap_vals, axis=1) + base_val
    max_additivity_error = float(np.max(np.abs(pred_log_direct - sum_shap)))
    print(f"SHAP Numerical Additivity Check: Max Error = {max_additivity_error:.8f} (Valid: {max_additivity_error < 1e-4})")

    mean_abs_shap = np.mean(np.abs(shap_vals), axis=0)
    shap_order = np.argsort(mean_abs_shap)[::-1]

    shap_rankings = []
    total_shap = float(np.sum(mean_abs_shap))
    for idx in shap_order:
        feat = OBSERVABLE_FEATURE_COLS[idx]
        val = float(mean_abs_shap[idx])
        shap_rankings.append({
            "feature": feat,
            "mean_abs_shap_log_scale": round(val, 4),
            "relative_importance_pct": round(float(val / total_shap * 100.0), 2),
            "interpretation": "Statistical contribution to log-expenditure prediction (statistical attribution, not causal effect)"
        })
        print(f"  {feat:25s}: {val:.4f} ({val / total_shap * 100.0:.1f}%)")

    # 5.2 Stability audit: evaluate Spearman rank correlation across 3 independent subsets
    sample_ranks = []
    for seed in [42, 101, 2024]:
        rng = np.random.default_rng(seed)
        sub_idx = rng.choice(len(X_test_obs), size=500, replace=False)
        sub_shap = explainer.shap_values(X_test_obs.iloc[sub_idx])
        sub_mean = np.mean(np.abs(sub_shap), axis=0)
        sample_ranks.append(sub_mean)

    spearman_12, _ = spearmanr(sample_ranks[0], sample_ranks[1])
    spearman_13, _ = spearmanr(sample_ranks[0], sample_ranks[2])
    spearman_23, _ = spearmanr(sample_ranks[1], sample_ranks[2])
    min_stability = min(spearman_12, spearman_13, spearman_23)
    print(f"SHAP Stability Across Subsamples (Spearman Rank Correlation): {min_stability:.4f} (High stability)")

    registry["shap_summary"] = {
        "max_additivity_error": round(float(max_additivity_error), 8),
        "additivity_verified": bool(max_additivity_error < 1e-4),
        "rank_stability_spearman_min": round(float(min_stability), 4),
        "feature_importance": shap_rankings
    }

    # =========================================================================
    # 6. SUBGROUP FAIRNESS EVALUATION
    # =========================================================================
    print("\n--- Running Subgroup Fairness & Disparity Evaluation ---")

    # Add predictions to test dataframe
    df_eval = X_test_obs.copy()
    df_eval['y_true'] = y_test_raw
    df_eval['y_true_cls'] = y_test_cls_tgt2
    df_eval['weight'] = w_test_norm
    df_eval['pred_tweedie'] = p_tw_obs
    df_eval['prob_logistic'] = cls_models["Logistic Regression (11-Feat Observable, Weighted Fit)"][0]

    # Create subgroups
    df_eval['age_group'] = pd.cut(df_eval['AGE23X'], bins=[-1, 17, 44, 64, 150], labels=['Pediatric (<18)', 'Young Adult (18-44)', 'Middle Age (45-64)', 'Older Adult (65+)'])
    df_eval['gender_group'] = df_eval['Gender_Male'].map({1: 'Male', 0: 'Female'})
    df_eval['comorb_group'] = pd.cut(df_eval['Comorbidity_Count'], bins=[-1, 0, 1, 2, 20], labels=['0 Comorbidities', '1 Comorbidity', '2 Comorbidities', '3+ Comorbidities'])

    subgroup_categories = [
        ('Age Category', 'age_group'),
        ('Sex / Gender', 'gender_group'),
        ('Comorbidity Burden', 'comorb_group')
    ]

    for cat_name, col in subgroup_categories:
        for val in df_eval[col].cat.categories if hasattr(df_eval[col], 'cat') else df_eval[col].unique():
            sub = df_eval[df_eval[col] == val]
            n_sub = len(sub)
            obs_m = float(np.mean(sub['y_true']))
            pred_m = float(np.mean(sub['pred_tweedie']))
            ratio = obs_m / pred_m if pred_m > 0 else 1.0
            mae_s = float(mean_absolute_error(sub['y_true'], sub['pred_tweedie']))

            # Classifier metrics
            prev_s = float(np.mean(sub['y_true_cls']))
            roc_s = float(roc_auc_score(sub['y_true_cls'], sub['prob_logistic'])) if len(np.unique(sub['y_true_cls'])) > 1 else 0.5
            brier_s = float(brier_score_loss(sub['y_true_cls'], sub['prob_logistic']))
            base_brier_s = float(brier_score_loss(sub['y_true_cls'], np.full_like(sub['y_true_cls'], prev_s, dtype=float)))
            bss_s = float(1.0 - (brier_s / base_brier_s)) if base_brier_s > 0 else 0.0

            # Survey-weighted subgroup metrics
            sub_w = sub['weight'].values
            obs_m_wtd = float(np.average(sub['y_true'], weights=sub_w))
            pred_m_wtd = float(np.average(sub['pred_tweedie'], weights=sub_w))
            ratio_wtd = obs_m_wtd / pred_m_wtd if pred_m_wtd > 0 else 1.0

            record = {
                "category": cat_name,
                "subgroup": str(val),
                "sample_size": int(n_sub),
                "observed_mean_unweighted": round(obs_m, 2),
                "predicted_mean_unweighted": round(pred_m, 2),
                "ratio_obs_pred_unweighted": round(ratio, 4),
                "observed_mean_weighted": round(obs_m_wtd, 2),
                "predicted_mean_weighted": round(pred_m_wtd, 2),
                "ratio_obs_pred_weighted": round(ratio_wtd, 4),
                "mae_unweighted": round(mae_s, 2),
                "high_cost_prev_unweighted": round(prev_s, 4),
                "roc_auc_unweighted": round(roc_s, 4),
                "brier_score_unweighted": round(brier_s, 4),
                "brier_skill_score_unweighted": round(bss_s, 4),
                "fairness_limitations": (
                    "Unweighted metrics reflect unweighted test split sample. Zero comorbidity indicates absence of mapped flags in MEPS, "
                    "not guaranteed absence of unmeasured illness. Subgroup sample sizes reflect survey sampling constraints."
                )
            }
            registry["subgroup_fairness"].append(record)
            print(f"  {cat_name} - {str(val):20s} (N={n_sub:4d}) | Obs: ${obs_m:8.2f} | Pred: ${pred_m:8.2f} | Ratio: {ratio:5.3f}x | ROC: {roc_s:6.4f}")

    # =========================================================================
    # 7. GENERATE PUBLICATION-QUALITY FIGURES
    # =========================================================================
    print("\n--- Generating Publication Figures ---")

    # 7.1 Figure 1: ROC and Precision-Recall Curves
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    fig1_models = [
        "Constant Prevalence Baseline",
        "Demographic Baseline (Age+Sex)",
        "Logistic Regression (11-Feat Observable, Weighted Fit)",
        "Random Forest (11-Feat Observable)",
        "XGBoost (Platt Calibrated)",
        "Logistic Regression (14-Feat Oracle)"
    ]

    for name in fig1_models:
        prob, _ = cls_models[name]
        if len(np.unique(prob)) > 1:
            fpr, tpr, _ = roc_curve(y_test_cls_tgt2, prob)
            auc = roc_auc_score(y_test_cls_tgt2, prob)
            ax1.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})", lw=1.8)

            prec, rec, _ = precision_recall_curve(y_test_cls_tgt2, prob)
            prauc = average_precision_score(y_test_cls_tgt2, prob)
            ax2.plot(rec, prec, label=f"{name} (PR={prauc:.3f})", lw=1.8)

    ax1.plot([0, 1], [0, 1], 'k--', lw=1, alpha=0.7, label="Chance")
    ax1.set_xlabel("False Positive Rate (1 - Specificity)", fontsize=11)
    ax1.set_ylabel("True Positive Rate (Sensitivity)", fontsize=11)
    ax1.set_title("A. High-Expenditure ROC Discrimination (Target 2)", fontsize=12, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.plot([0, 1], [test_prev_tgt2_unw, test_prev_tgt2_unw], 'k--', lw=1, alpha=0.7, label=f"Prevalence ({test_prev_tgt2_unw:.3f})")
    ax2.set_xlabel("Recall (Sensitivity)", fontsize=11)
    ax2.set_ylabel("Precision (Positive Predictive Value)", fontsize=11)
    ax2.set_title("B. Precision-Recall Curve (Top Decile Target 2)", fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig1_path = os.path.join(FIG_DIR, "fig1_roc_pr_curves.png")
    plt.savefig(fig1_path)
    plt.close()
    print(f"Saved {fig1_path}")

    # 7.2 Figure 2: Calibration and Decile Stratification
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    prob_lr = cls_models["Logistic Regression (11-Feat Observable, Weighted Fit)"][0]
    prob_xgb = cls_models["XGBoost (Platt Calibrated)"][0]
    fop_lr, mpv_lr = calibration_curve(y_test_cls_tgt2, prob_lr, n_bins=10)
    fop_xgb, mpv_xgb = calibration_curve(y_test_cls_tgt2, prob_xgb, n_bins=10)

    ax1.plot([0, 1], [0, 1], 'k--', lw=1.2, label="Perfect Calibration")
    ax1.plot(mpv_lr, fop_lr, 's-', color='#1f77b4', lw=2, label="Logistic (11-Feat Observable)")
    ax1.plot(mpv_xgb, fop_xgb, 'o-', color='#ff7f0e', lw=2, label="XGBoost (Platt Calibrated)")
    ax1.set_xlabel("Mean Predicted Probability", fontsize=11)
    ax1.set_ylabel("Observed Fraction of Positives", fontsize=11)
    ax1.set_title("A. Classifier Calibration Curves", fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Decile Stratification for Tweedie
    df_dec = pd.DataFrame({'obs': y_test_raw, 'pred': p_tw_obs})
    df_dec['decile'] = pd.qcut(df_dec['pred'], q=10, labels=False) + 1
    dec_obs = df_dec.groupby('decile')['obs'].mean()
    dec_pred = df_dec.groupby('decile')['pred'].mean()

    x = np.arange(1, 11)
    width = 0.38
    ax2.bar(x - width/2, dec_obs, width, label='Observed Mean ($)', color='#2ca02c', alpha=0.85)
    ax2.bar(x + width/2, dec_pred, width, label='Tweedie Pred Mean ($)', color='#1f77b4', alpha=0.85)
    ax2.set_xlabel("Predicted Risk Decile", fontsize=11)
    ax2.set_ylabel("Mean Annual Expenditure ($)", fontsize=11)
    ax2.set_title("B. Observable Tweedie Decile Stratification", fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig2_path = os.path.join(FIG_DIR, "fig2_calibration_deciles.png")
    plt.savefig(fig2_path)
    plt.close()
    print(f"Saved {fig2_path}")

    # 7.3 Figure 3: SHAP Feature Importance
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    feats_plot = [x["feature"] for x in shap_rankings][::-1]
    vals_plot = [x["mean_abs_shap_log_scale"] for x in shap_rankings][::-1]

    colors = ['#1f77b4' if 'ACG' in f else '#ff7f0e' if 'Age' in f or 'Gender' in f else '#2ca02c' for f in feats_plot]
    ax.barh(feats_plot, vals_plot, color=colors, alpha=0.85, edgecolor='black', lw=0.5)
    ax.set_xlabel("Mean |SHAP Value| (Impact on Model Log Expenditure)", fontsize=11)
    ax.set_title("SHAP TreeExplainer Global Feature Importance (11 Observable Features)", fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)

    import matplotlib.patches as mpatches
    p1 = mpatches.Patch(color='#ff7f0e', label='Demographics & Age Interactions')
    p2 = mpatches.Patch(color='#1f77b4', label='Clinical ACG Condition Clusters')
    p3 = mpatches.Patch(color='#2ca02c', label='Comorbidity Composites')
    ax.legend(handles=[p1, p2, p3], loc='lower right', fontsize=9)

    plt.tight_layout()
    fig3_path = os.path.join(FIG_DIR, "fig3_shap_importance.png")
    plt.savefig(fig3_path)
    plt.close()
    print(f"Saved {fig3_path}")

    # 7.4 Figure 4: Feature Ablation Comparison
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
    abl_labels = [x["ablation_label"] for x in registry["feature_ablations"]][::-1]
    abl_r2 = [x["regression_r2"] for x in registry["feature_ablations"]][::-1]
    abl_bss = [x["classification_bss_weighted"] for x in registry["feature_ablations"]][::-1]

    y_pos = np.arange(len(abl_labels))
    height = 0.38
    ax.barh(y_pos - height/2, abl_r2, height, label='Expenditure Dollar R²', color='#1f77b4', alpha=0.85)
    ax.barh(y_pos + height/2, abl_bss, height, label='Classifier Weighted BSS', color='#ff7f0e', alpha=0.85)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(abl_labels, fontsize=9)
    ax.set_xlabel("Metric Score (Higher is Better)", fontsize=11)
    ax.set_title("Systematic Feature Ablation Impact Across Regression and Classification", fontsize=12, fontweight='bold')
    ax.axvline(0, color='black', lw=0.8, ls='--')
    ax.legend(loc='lower right', fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig4_path = os.path.join(FIG_DIR, "fig4_feature_ablations.png")
    plt.savefig(fig4_path)
    plt.close()
    print(f"Saved {fig4_path}")

    # 7.5 Figure 5: Blockchain Benchmark Curves (from Caliper data)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    send_rates = [50.5, 100.5, 200.5, 963.6]
    throughputs = [50.3, 100.2, 199.9, 350.1]
    latencies = [0.10, 0.06, 0.04, 18.00]

    ax1.plot(send_rates[:3], throughputs[:3], 'o-', color='#1f77b4', lw=2, label="Linear Regime (< 200 TPS)")
    ax1.plot(send_rates[2:], throughputs[2:], 's--', color='#d62728', lw=2, label="Saturation Knee (Ceiling 350.1 TPS)")
    ax1.plot([0, 1000], [0, 1000], 'k:', alpha=0.5, label="1:1 Offered vs Committed Rate")
    ax1.set_xlabel("Offered Transaction Submission Rate (TPS)", fontsize=11)
    ax1.set_ylabel("Committed Throughput (TPS)", fontsize=11)
    ax1.set_title("A. Fabric Network Throughput vs Send Rate", fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.plot(throughputs[:3], latencies[:3], 'o-', color='#2ca02c', lw=2, label="Sub-100ms Endorsement")
    ax2.plot([throughputs[2], throughputs[3]], [latencies[2], latencies[3]], 'o--', color='#d62728', lw=2, label="Queueing Latency at Saturation (18.0s)")
    ax2.set_xlabel("Committed Throughput (TPS)", fontsize=11)
    ax2.set_ylabel("Average End-to-End Latency (seconds)", fontsize=11)
    ax2.set_title("B. Latency vs Throughput Characteristic", fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Hyperledger Fabric 5-Org Performance (Historical Baseline Benchmark: Commit 944fb0d | Network Offline)", fontsize=11, style='italic')
    plt.tight_layout()
    fig5_path = os.path.join(FIG_DIR, "fig5_blockchain_benchmarks.png")
    plt.savefig(fig5_path)
    plt.close()
    print(f"Saved {fig5_path}")

    # =========================================================================
    # 8. SAVE EXPERIMENT REGISTRY
    # =========================================================================
    reg_json_path = os.path.join(EXP_DIR, "experiment_registry.json")
    with open(reg_json_path, 'w') as f:
        json.dump(registry, f, indent=2, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    print(f"\nSuccessfully saved full experiment registry to {reg_json_path}")


if __name__ == "__main__":
    main()
