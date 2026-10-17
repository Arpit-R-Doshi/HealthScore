"""
Prospective Forecasting Validation Script: MEPS HC-257 (2023-2024 Panel 28 Longitudinal)
Evaluates frozen 2023 Phase 1 models for prospective healthcare expenditure prediction in 2024.

Strict prospective protocol:
  - Predictors: Strictly baseline Year 1 (2023) information (AGEY1X, SEX, HIBPDXY1, etc.).
  - Target: Annual healthcare expenditure in Year 2 (2024) (TOTEXPY2).
  - Weights: Official Panel 28 longitudinal weight (LONGWT).
  - Zero retraining, zero feature tuning, zero post-baseline leakage.
"""

import os
import sys
import json
import pickle
import hashlib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    roc_auc_score, average_precision_score, brier_score_loss
)
from sklearn.linear_model import LogisticRegression

# Set directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HC257_DIR = os.path.join(BASE_DIR, "validation", "hc257")
DATA_PATH = os.path.join(HC257_DIR, "data", "h257.dta")

OBSERVABLE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Age_x_Comorbidity'
]

LOCKED_UNWEIGHTED_P90 = 20360.50
LOCKED_WEIGHTED_P90 = 17827.41

TRAIN_UNWEIGHTED_PREV_P90 = 0.1000266
TRAIN_WEIGHTED_PREV_P90 = 0.099888
TRAIN_UNWEIGHTED_PREV_TARGET2 = 1736 / 15016  # 0.11561001598295152 (unweighted training prevalence for Target 2: y >= $17,827.41)


def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def compute_weighted_mean(values, weights):
    return float(np.sum(values * weights) / np.sum(weights))


def compute_weighted_mae(y_true, y_pred, weights):
    return float(np.sum(weights * np.abs(y_true - y_pred)) / np.sum(weights))


def compute_weighted_rmse(y_true, y_pred, weights):
    return float(np.sqrt(np.sum(weights * ((y_true - y_pred) ** 2)) / np.sum(weights)))


def compute_weighted_r2(y_true, y_pred, weights):
    y_bar = compute_weighted_mean(y_true, weights)
    ss_res = np.sum(weights * ((y_true - y_pred) ** 2))
    ss_tot = np.sum(weights * ((y_true - y_bar) ** 2))
    return float(1.0 - (ss_res / ss_tot))


def compute_weighted_brier(y_true, y_prob, weights):
    return float(np.sum(weights * ((y_prob - y_true) ** 2)) / np.sum(weights))


def compute_calibration(y_true, y_prob, weights=None):
    eps = 1e-6
    probs_clipped = np.clip(y_prob, eps, 1.0 - eps)
    logits = np.log(probs_clipped / (1.0 - probs_clipped)).reshape(-1, 1)
    # Unpenalized logistic calibration fit to eliminate L2 shrinkage on slope.
    # We test unpenalized candidates in order of preference, catching only expected
    # parameter-compatibility errors (ValueError, TypeError).
    # Silent fallback to default L2 regularized regression is forbidden.
    candidates = [
        ("LogisticRegression(C=inf)", lambda: LogisticRegression(C=np.inf, solver='lbfgs', max_iter=1000)),
        ("LogisticRegression(penalty=None)", lambda: LogisticRegression(penalty=None, solver='lbfgs', max_iter=1000)),
        ("LogisticRegression(C=1e9)", lambda: LogisticRegression(C=1e9, solver='lbfgs', max_iter=1000)),
    ]
    fitted_model = None
    selected_method = None
    errors = []

    for name, factory in candidates:
        try:
            cand = factory()
            if weights is not None:
                cand.fit(logits, y_true, sample_weight=weights)
            else:
                cand.fit(logits, y_true)
            fitted_model = cand
            selected_method = name
            break
        except (ValueError, TypeError) as e:
            errors.append(f"{name}: {e}")
            continue

    if fitted_model is None:
        raise RuntimeError(
            f"Failed to fit unpenalized or approved near-unpenalized logistic calibration estimator. "
            f"Errors encountered: {'; '.join(errors)}"
        )

    intercept = float(fitted_model.intercept_[0])
    slope = float(fitted_model.coef_[0][0])
    return intercept, slope, selected_method


def main():
    print("=" * 80)
    print("MEPS HC-257 (2023-2024 Panel 28) Prospective Forecasting Validation")
    print("=" * 80)

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"HC-257 data not found at {DATA_PATH}")

    data_hash = get_sha256(DATA_PATH)
    print(f"Data file: {DATA_PATH}")
    print(f"SHA-256: {data_hash}")

    raw_df = pd.read_stata(DATA_PATH, convert_categoricals=False)
    raw_count = len(raw_df)
    print(f"Total Panel 28 sample: {raw_count}")

    # Cohort Flow Reconciliation per AHRQ MEPS HC-257 Documentation:
    # 1. Total panel 28 records: 8,872
    # 2. In-scope across both years (YEARIND == 1): 8,709
    # 3. Valid baseline age (AGEY1X >= 0) among two-year persons: 8,708 (1 dropped with AGEY1X == -1)
    # 4. Out-of-scope in Year 1 or Year 2 (YEARIND in [2, 3]): 163 dropped (106 attrited/died in Y2, 57 Y2-only)
    # 5. In-scope and data collected all 5 rounds (ALL5RDS == 1): 8,389
    # 6. Adult SAQ longitudinal respondents with positive LSAQWT: 5,643 (raw file), 5,630 (two-year cohort)
    two_year_mask = raw_df['YEARIND'] == 1
    valid_baseline_age_mask = raw_df['AGEY1X'] >= 0
    clean_df = raw_df[two_year_mask & valid_baseline_age_mask].copy()
    analysis_sample_size = len(clean_df)

    dropped_non_two_year = int((~two_year_mask).sum())
    dropped_invalid_baseline_age = int((two_year_mask & (~valid_baseline_age_mask)).sum())

    print(f"Total Panel 28 sample: {raw_count}")
    print(f"Two-year eligible (YEARIND == 1): {two_year_mask.sum()}")
    print(f"Dropped non-two-year respondents (died, out of scope, or Y2 entrant): {dropped_non_two_year}")
    print(f"Dropped invalid baseline age (AGEY1X < 0): {dropped_invalid_baseline_age}")
    print(f"Final prospective analysis cohort: {analysis_sample_size}")

    # Exact Phase 1 Training Feature Engineering Mapping (strictly Year 1 baseline)
    clean_df['AGE23X'] = clean_df['AGEY1X'].astype(float)
    clean_df['Gender_Male'] = (clean_df['SEX'] == 1).astype(int)

    # Binarize condition indicators: 1=Yes, 0=Otherwise (-1, 2, etc.)
    for col in ['HIBPDXY1', 'CHDDXY1', 'MIDXY1', 'STRKDXY1', 'DIABDXY1_M18', 'CHOLDXY1',
                'ASTHDXY1', 'EMPHDXY1', 'CHBRON1', 'CANCERY1', 'ARTHDXY1', 'JTPAIN1_M18', 'ADHDADY1']:
        clean_df[col] = (clean_df[col] == 1).astype(int)

    # Preserve raw ADDPRS2 before binarization to audit SAQ item missingness and skip patterns
    clean_df['ADDPRS2_raw'] = clean_df['ADDPRS2'].copy()
    # ADDPRS2: Depression screener from Round 2 SAQ (values 1, 2, 3 indicate depressive symptoms)
    clean_df['ADDPRS2'] = clean_df['ADDPRS2'].apply(lambda x: 1 if x in [1, 2, 3] else 0)

    # Exact Phase 1 Integer Cluster Formulas
    clean_df['Cardio_ACG'] = clean_df['HIBPDXY1'] + clean_df['CHDDXY1'] + clean_df['MIDXY1'] + clean_df['STRKDXY1']
    clean_df['Metabolic_ACG'] = clean_df['DIABDXY1_M18'] + clean_df['CHOLDXY1']
    clean_df['Respiratory_ACG'] = clean_df['ASTHDXY1'] + clean_df['EMPHDXY1'] + clean_df['CHBRON1']
    clean_df['Oncology_ACG'] = clean_df['CANCERY1']
    clean_df['Musculoskeletal_ACG'] = clean_df['ARTHDXY1'] + clean_df['JTPAIN1_M18']
    clean_df['Psychiatric_ACG'] = clean_df['ADDPRS2'] + clean_df['ADHDADY1']

    # Derived comorbidities
    cluster_cols = ['Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG']
    clean_df['Comorbidity_Count'] = (clean_df[cluster_cols] > 0).sum(axis=1)
    clean_df['Multimorbidity_Penalty'] = clean_df['Comorbidity_Count'] ** 2
    clean_df['Age_x_Comorbidity'] = clean_df['AGE23X'] * clean_df['Comorbidity_Count']

    X_val = clean_df[OBSERVABLE_COLS].copy()
    y2_raw = clean_df['TOTEXPY2'].values.astype(float)
    y1_raw = clean_df['TOTEXPY1'].values.astype(float)
    weights = clean_df['LONGWT'].values.astype(float)

    # Load Frozen Models
    reg_path = os.path.join(BASE_DIR, "risk_model.pkl")
    tweedie_path = os.path.join(BASE_DIR, "artifacts", "risk_model_tweedie_observable.pkl")
    cls_unweighted_path = os.path.join(BASE_DIR, "artifacts", "risk_model_classifier_observable_unweighted_p90.pkl")
    cls_weighted_path = os.path.join(BASE_DIR, "artifacts", "risk_model_classifier_observable_weighted_p90.pkl")

    with open(reg_path, "rb") as f:
        reg_model = pickle.load(f)
    with open(tweedie_path, "rb") as f:
        tweedie_model = pickle.load(f)
    with open(cls_unweighted_path, "rb") as f:
        cls_unweighted_model = pickle.load(f)
    with open(cls_weighted_path, "rb") as f:
        cls_weighted_model = pickle.load(f)

    # Predictions
    xgb_pred_log = reg_model.predict(X_val)
    xgb_pred_dollar = np.maximum(0.0, np.expm1(xgb_pred_log))
    tweedie_pred_dollar = np.maximum(0.0, tweedie_model.predict(X_val))

    prob_unweighted_p90 = cls_unweighted_model.predict_proba(X_val)[:, 1]
    prob_weighted_p90 = cls_weighted_model.predict_proba(X_val)[:, 1]

    # Binary labels for locked thresholds on Year 2 outcome
    y2_unweighted_p90 = (y2_raw >= LOCKED_UNWEIGHTED_P90).astype(int)
    y2_weighted_p90 = (y2_raw >= LOCKED_WEIGHTED_P90).astype(int)

    # Prospective Regression Metrics
    obs_mean_raw = float(np.mean(y2_raw))
    obs_weighted_mean_raw = compute_weighted_mean(y2_raw, weights)

    # Tweedie Prospective
    tw_mean = float(np.mean(tweedie_pred_dollar))
    tw_weighted_mean = compute_weighted_mean(tweedie_pred_dollar, weights)
    tw_mae = float(mean_absolute_error(y2_raw, tweedie_pred_dollar))
    tw_w_mae = compute_weighted_mae(y2_raw, tweedie_pred_dollar, weights)
    tw_rmse = float(np.sqrt(mean_squared_error(y2_raw, tweedie_pred_dollar)))
    tw_w_rmse = compute_weighted_rmse(y2_raw, tweedie_pred_dollar, weights)
    tw_r2 = float(r2_score(y2_raw, tweedie_pred_dollar))
    tw_w_r2 = compute_weighted_r2(y2_raw, tweedie_pred_dollar, weights)

    # XGBoost Prospective
    xgb_mean = float(np.mean(xgb_pred_dollar))
    xgb_weighted_mean = compute_weighted_mean(xgb_pred_dollar, weights)
    xgb_mae = float(mean_absolute_error(y2_raw, xgb_pred_dollar))
    xgb_w_mae = compute_weighted_mae(y2_raw, xgb_pred_dollar, weights)
    xgb_rmse = float(np.sqrt(mean_squared_error(y2_raw, xgb_pred_dollar)))
    xgb_w_rmse = compute_weighted_rmse(y2_raw, xgb_pred_dollar, weights)
    xgb_r2 = float(r2_score(y2_raw, xgb_pred_dollar))
    xgb_w_r2 = compute_weighted_r2(y2_raw, xgb_pred_dollar, weights)

    # Econometric Benchmark: Year 1 Lagged Spending Persistence
    lag_mae = float(mean_absolute_error(y2_raw, y1_raw))
    lag_w_mae = compute_weighted_mae(y2_raw, y1_raw, weights)
    lag_rmse = float(np.sqrt(mean_squared_error(y2_raw, y1_raw)))
    lag_w_rmse = compute_weighted_rmse(y2_raw, y1_raw, weights)
    lag_r2 = float(r2_score(y2_raw, y1_raw))
    lag_w_r2 = compute_weighted_r2(y2_raw, y1_raw, weights)

    # Decile Stratification (by Tweedie)
    clean_df['tw_pred'] = tweedie_pred_dollar
    clean_df['tw_decile'] = pd.qcut(clean_df['tw_pred'], q=10, labels=False, duplicates='drop') + 1

    tw_deciles = []
    for d in range(1, 11):
        sub = clean_df[clean_df['tw_decile'] == d]
        cnt = len(sub)
        o_mean = float(sub['TOTEXPY2'].mean())
        p_mean = float(sub['tw_pred'].mean())
        ratio = float(o_mean / p_mean) if p_mean > 0 else 0.0
        tw_deciles.append({
            "decile": d,
            "count": cnt,
            "observed_y2_mean": round(o_mean, 2),
            "predicted_mean": round(p_mean, 2),
            "ratio_obs_to_pred": round(ratio, 4)
        })

    # Classifiers Prospective
    unw_prev = float(np.mean(y2_unweighted_p90))
    unw_auc = float(roc_auc_score(y2_unweighted_p90, prob_unweighted_p90))
    unw_prauc = float(average_precision_score(y2_unweighted_p90, prob_unweighted_p90))
    unw_brier = float(brier_score_loss(y2_unweighted_p90, prob_unweighted_p90))
    unw_base_brier = float(brier_score_loss(y2_unweighted_p90, np.full_like(y2_unweighted_p90, TRAIN_UNWEIGHTED_PREV_P90, dtype=float)))
    unw_bss = float(1.0 - (unw_brier / unw_base_brier)) if unw_base_brier > 0 else 0.0
    unw_cal_int, unw_cal_slope, unw_cal_method = compute_calibration(y2_unweighted_p90, prob_unweighted_p90)

    w_prev = compute_weighted_mean(y2_weighted_p90, weights)
    w_auc = float(roc_auc_score(y2_weighted_p90, prob_weighted_p90, sample_weight=weights))
    w_prauc = float(average_precision_score(y2_weighted_p90, prob_weighted_p90, sample_weight=weights))
    w_brier = compute_weighted_brier(y2_weighted_p90, prob_weighted_p90, weights)
    w_base_brier = compute_weighted_brier(y2_weighted_p90, np.full_like(y2_weighted_p90, TRAIN_WEIGHTED_PREV_P90, dtype=float), weights)
    w_bss = float(1.0 - (w_brier / w_base_brier)) if w_base_brier > 0 else 0.0
    w_cal_int, w_cal_slope, w_cal_method = compute_calibration(y2_weighted_p90, prob_weighted_p90, weights=weights)
    unw_w_cal_int, unw_w_cal_slope, unw_w_cal_method = compute_calibration(y2_weighted_p90, prob_weighted_p90)

    # Subgroups
    clean_df['age_group'] = pd.cut(
        clean_df['AGE23X'],
        bins=[-np.inf, 17, 44, 64, np.inf],
        labels=['<18', '18-44', '45-64', '65+']
    )
    subgroups = []
    for grp, df_g in clean_df.groupby('age_group', observed=True):
        cnt = len(df_g)
        o_m = float(df_g['TOTEXPY2'].mean())
        tw_m = float(df_g['tw_pred'].mean())
        tw_mae_g = float(mean_absolute_error(df_g['TOTEXPY2'], df_g['tw_pred']))
        subgroups.append({
            "dimension": "Age Group",
            "group": str(grp),
            "count": cnt,
            "observed_y2_mean": round(o_m, 2),
            "tweedie_pred_mean": round(tw_m, 2),
            "tweedie_mae": round(tw_mae_g, 2),
            "ratio_obs_to_tweedie": round(o_m / tw_m, 4) if tw_m > 0 else 0.0
        })

    for grp, df_g in clean_df.groupby('Gender_Male'):
        cnt = len(df_g)
        o_m = float(df_g['TOTEXPY2'].mean())
        tw_m = float(df_g['tw_pred'].mean())
        tw_mae_g = float(mean_absolute_error(df_g['TOTEXPY2'], df_g['tw_pred']))
        subgroups.append({
            "dimension": "Gender",
            "group": "Male" if grp == 1 else "Female",
            "count": cnt,
            "observed_y2_mean": round(o_m, 2),
            "tweedie_pred_mean": round(tw_m, 2),
            "tweedie_mae": round(tw_mae_g, 2),
            "ratio_obs_to_tweedie": round(o_m / tw_m, 4) if tw_m > 0 else 0.0
        })

    # Temporal Drift & Thresholds
    unw_p90_y2 = float(np.percentile(y2_raw, 90))
    sorted_idx = np.argsort(y2_raw)
    cum_w = np.cumsum(weights[sorted_idx]) / np.sum(weights)
    w_p90_y2 = float(y2_raw[sorted_idx][np.searchsorted(cum_w, 0.90)])

    # SAQ Sub-cohort Evaluation with LSAQWT (Adults completing SAQ)
    saq_sub = clean_df[clean_df['LSAQWT'] > 0]
    saq_weights = saq_sub['LSAQWT'].values.astype(float)
    saq_y2 = saq_sub['TOTEXPY2'].values.astype(float)
    saq_tw_pred = saq_sub['tw_pred'].values.astype(float)
    saq_y2_w_p90 = (saq_y2 >= LOCKED_WEIGHTED_P90).astype(int)
    saq_prob_w_p90 = cls_weighted_model.predict_proba(saq_sub[OBSERVABLE_COLS])[:, 1]

    # Weighted SAQ Metrics (Adult SAQ Cohort N=5,630)
    saq_w_obs = compute_weighted_mean(saq_y2, saq_weights)
    saq_w_pred = compute_weighted_mean(saq_tw_pred, saq_weights)
    saq_w_mae = compute_weighted_mae(saq_y2, saq_tw_pred, saq_weights)
    saq_w_r2 = compute_weighted_r2(saq_y2, saq_tw_pred, saq_weights)
    saq_w_prev = compute_weighted_mean(saq_y2_w_p90, saq_weights)
    saq_w_auc = float(roc_auc_score(saq_y2_w_p90, saq_prob_w_p90, sample_weight=saq_weights))
    saq_w_brier = compute_weighted_brier(saq_y2_w_p90, saq_prob_w_p90, saq_weights)
    saq_w_base_brier = compute_weighted_brier(saq_y2_w_p90, np.full_like(saq_y2_w_p90, TRAIN_WEIGHTED_PREV_P90, dtype=float), saq_weights)
    saq_w_bss = float(1.0 - (saq_w_brier / saq_w_base_brier)) if saq_w_base_brier > 0 else 0.0
    saq_w_cal_int, saq_w_cal_slope, saq_w_cal_method = compute_calibration(saq_y2_w_p90, saq_prob_w_p90, weights=saq_weights)

    # Unweighted SAQ Metrics (Adult SAQ Cohort N=5,630)
    saq_unw_prev = float(np.mean(saq_y2_w_p90))
    saq_unw_obs = float(np.mean(saq_y2))
    saq_unw_pred = float(np.mean(saq_tw_pred))
    saq_unw_mae = float(mean_absolute_error(saq_y2, saq_tw_pred))
    saq_unw_r2 = float(r2_score(saq_y2, saq_tw_pred))
    saq_unw_auc = float(roc_auc_score(saq_y2_w_p90, saq_prob_w_p90))
    saq_unw_brier = float(brier_score_loss(saq_y2_w_p90, saq_prob_w_p90))
    saq_unw_base_brier = float(brier_score_loss(saq_y2_w_p90, np.full_like(saq_y2_w_p90, TRAIN_UNWEIGHTED_PREV_TARGET2, dtype=float)))
    saq_unw_bss = float(1.0 - (saq_unw_brier / saq_unw_base_brier)) if saq_unw_base_brier > 0 else 0.0
    saq_unw_cal_int, saq_unw_cal_slope, saq_unw_cal_method = compute_calibration(saq_y2_w_p90, saq_prob_w_p90)

    saq_metrics = {
        "subcohort_sample_size": len(saq_sub),
        "unweighted": {
            "evaluation_prevalence": round(saq_unw_prev, 4),
            "observed_mean": round(saq_unw_obs, 2),
            "predicted_mean": round(saq_unw_pred, 2),
            "tweedie_mae": round(saq_unw_mae, 2),
            "tweedie_r2": round(saq_unw_r2, 4),
            "classifier_roc_auc": round(saq_unw_auc, 4),
            "classifier_brier": round(saq_unw_brier, 5),
            "classifier_base_brier": round(saq_unw_base_brier, 5),
            "classifier_brier_skill_score": round(saq_unw_bss, 4),
            "calibration_intercept": round(saq_unw_cal_int, 4),
            "calibration_slope": round(saq_unw_cal_slope, 4),
            "calibration_estimator": saq_unw_cal_method
        },
        "lsaqwt_weighted": {
            "evaluation_weighted_prevalence": round(saq_w_prev, 4),
            "observed_mean": round(saq_w_obs, 2),
            "predicted_mean": round(saq_w_pred, 2),
            "tweedie_mae": round(saq_w_mae, 2),
            "tweedie_r2": round(saq_w_r2, 4),
            "classifier_roc_auc": round(saq_w_auc, 4),
            "classifier_brier": round(saq_w_brier, 5),
            "classifier_base_brier": round(saq_w_base_brier, 5),
            "classifier_brier_skill_score": round(saq_w_bss, 4),
            "calibration_intercept": round(saq_w_cal_int, 4),
            "calibration_slope": round(saq_w_cal_slope, 4),
            "calibration_estimator": saq_w_cal_method
        },
        "observed_mean_lsaqwt_weighted": round(saq_w_obs, 2),
        "predicted_mean_lsaqwt_weighted": round(saq_w_pred, 2),
        "tweedie_lsaqwt_weighted_mae": round(saq_w_mae, 2),
        "tweedie_lsaqwt_weighted_r2": round(saq_w_r2, 4),
        "classifier_lsaqwt_weighted_roc_auc": round(saq_w_auc, 4),
        "classifier_lsaqwt_weighted_brier": round(saq_w_brier, 5),
        "classifier_lsaqwt_weighted_base_brier": round(saq_w_base_brier, 5),
        "classifier_lsaqwt_weighted_brier_skill_score": round(saq_w_bss, 4)
    }

    # Complete-case baseline SAQ respondents: N = 4,208 (LSAQWT > 0 and raw ADDPRS2 >= 0)
    # Audits the estimand restricted to individuals with an observed, non-negative baseline depression score
    # (Excludes 1,294 ADDPRS2 == -1 and 128 ADDPRS2 == -15 cases)
    saq_valid_sub = clean_df[(clean_df['LSAQWT'] > 0) & (clean_df['ADDPRS2_raw'] >= 0)]
    saq_valid_w = saq_valid_sub['LSAQWT'].values.astype(float)
    saq_valid_y2 = saq_valid_sub['TOTEXPY2'].values.astype(float)
    saq_valid_pred = saq_valid_sub['tw_pred'].values.astype(float)
    saq_valid_label = (saq_valid_y2 >= LOCKED_WEIGHTED_P90).astype(int)
    saq_valid_prob = cls_weighted_model.predict_proba(saq_valid_sub[OBSERVABLE_COLS])[:, 1]

    # Weighted Valid SAQ Metrics
    v_w_prev = compute_weighted_mean(saq_valid_label, saq_valid_w)
    v_w_obs = compute_weighted_mean(saq_valid_y2, saq_valid_w)
    v_w_pred = compute_weighted_mean(saq_valid_pred, saq_valid_w)
    v_w_mae = compute_weighted_mae(saq_valid_y2, saq_valid_pred, saq_valid_w)
    v_w_r2 = compute_weighted_r2(saq_valid_y2, saq_valid_pred, saq_valid_w)
    v_w_auc = float(roc_auc_score(saq_valid_label, saq_valid_prob, sample_weight=saq_valid_w))
    v_w_brier = compute_weighted_brier(saq_valid_label, saq_valid_prob, saq_valid_w)
    v_w_base_brier = compute_weighted_brier(saq_valid_label, np.full_like(saq_valid_label, TRAIN_WEIGHTED_PREV_P90, dtype=float), saq_valid_w)
    v_w_bss = float(1.0 - (v_w_brier / v_w_base_brier)) if v_w_base_brier > 0 else 0.0
    v_w_cal_int, v_w_cal_slope, v_w_cal_method = compute_calibration(saq_valid_label, saq_valid_prob, weights=saq_valid_w)

    # Unweighted Valid SAQ Metrics
    v_unw_prev = float(np.mean(saq_valid_label))
    v_unw_obs = float(np.mean(saq_valid_y2))
    v_unw_pred = float(np.mean(saq_valid_pred))
    v_unw_mae = float(mean_absolute_error(saq_valid_y2, saq_valid_pred))
    v_unw_r2 = float(r2_score(saq_valid_y2, saq_valid_pred))
    v_unw_auc = float(roc_auc_score(saq_valid_label, saq_valid_prob))
    v_unw_brier = float(brier_score_loss(saq_valid_label, saq_valid_prob))
    v_unw_base_brier = float(brier_score_loss(saq_valid_label, np.full_like(saq_valid_label, TRAIN_UNWEIGHTED_PREV_TARGET2, dtype=float)))
    v_unw_bss = float(1.0 - (v_unw_brier / v_unw_base_brier)) if v_unw_base_brier > 0 else 0.0
    v_unw_cal_int, v_unw_cal_slope, v_unw_cal_method = compute_calibration(saq_valid_label, saq_valid_prob)

    saq_valid_metrics = {
        "subcohort_sample_size": len(saq_valid_sub),
        "excluded_inapplicable_round2": int(((clean_df['LSAQWT'] > 0) & (clean_df['ADDPRS2_raw'] == -1)).sum()),
        "excluded_missing_round2": int(((clean_df['LSAQWT'] > 0) & (clean_df['ADDPRS2_raw'] == -15)).sum()),
        "unweighted": {
            "evaluation_prevalence": round(v_unw_prev, 4),
            "observed_mean": round(v_unw_obs, 2),
            "predicted_mean": round(v_unw_pred, 2),
            "tweedie_mae": round(v_unw_mae, 2),
            "tweedie_r2": round(v_unw_r2, 4),
            "classifier_roc_auc": round(v_unw_auc, 4),
            "classifier_brier": round(v_unw_brier, 5),
            "classifier_base_brier": round(v_unw_base_brier, 5),
            "classifier_brier_skill_score": round(v_unw_bss, 4),
            "calibration_intercept": round(v_unw_cal_int, 4),
            "calibration_slope": round(v_unw_cal_slope, 4),
            "calibration_estimator": v_unw_cal_method
        },
        "lsaqwt_weighted": {
            "evaluation_weighted_prevalence": round(v_w_prev, 4),
            "observed_mean": round(v_w_obs, 2),
            "predicted_mean": round(v_w_pred, 2),
            "tweedie_mae": round(v_w_mae, 2),
            "tweedie_r2": round(v_w_r2, 4),
            "classifier_roc_auc": round(v_w_auc, 4),
            "classifier_brier": round(v_w_brier, 5),
            "classifier_base_brier": round(v_w_base_brier, 5),
            "classifier_brier_skill_score": round(v_w_bss, 4),
            "calibration_intercept": round(v_w_cal_int, 4),
            "calibration_slope": round(v_w_cal_slope, 4),
            "calibration_estimator": v_w_cal_method
        }
    }

    results = {
        "metadata": {
            "validation_dataset": "MEPS HC-257 (2023-2024 Panel 28 Longitudinal)",
            "data_file_sha256": data_hash,
            "total_panel_sample": raw_count,
            "two_year_eligible_yearind_1": int(two_year_mask.sum()),
            "dropped_invalid_baseline_age": dropped_invalid_baseline_age,
            "dropped_non_two_year_attrited_or_entrant": dropped_non_two_year,
            "analysis_cohort_size": analysis_sample_size,
            "all_five_rounds_in_scope_all5rds": int((clean_df['ALL5RDS'] == 1).sum()),
            "adult_saq_subcohort_lsaqwt_positive": int((clean_df['LSAQWT'] > 0).sum()),
            "adult_saq_both_rounds_saqrds24_1": int(((clean_df['LSAQWT'] > 0) & (clean_df['SAQRDS24'] == 1)).sum()),
            "adult_saq_round4_only_saqrds24_0": int(((clean_df['LSAQWT'] > 0) & (clean_df['SAQRDS24'] == 0)).sum()),
            "adult_saq_valid_baseline_addprs2": len(saq_valid_sub),
            "adult_saq_inapplicable_addprs2_round2": int(((clean_df['LSAQWT'] > 0) & (clean_df['ADDPRS2_raw'] == -1)).sum()),
            "adult_saq_missing_addprs2_round2": int(((clean_df['LSAQWT'] > 0) & (clean_df['ADDPRS2_raw'] == -15)).sum()),
            "locked_2023_unweighted_p90": LOCKED_UNWEIGHTED_P90,
            "locked_2023_weighted_p90": LOCKED_WEIGHTED_P90,
            "observed_y2_unweighted_p90": round(unw_p90_y2, 2),
            "observed_y2_weighted_p90": round(w_p90_y2, 2)
        },
        "adult_saq_subcohort_performance": saq_metrics,
        "adult_saq_complete_case_valid_depression": saq_valid_metrics,
        "target_distribution_y2": {
            "observed_mean_unweighted": round(obs_mean_raw, 2),
            "observed_mean_survey_weighted": round(obs_weighted_mean_raw, 2),
            "observed_median": round(float(np.median(y2_raw)), 2),
            "observed_std": round(float(np.std(y2_raw)), 2),
            "observed_p95": round(float(np.percentile(y2_raw, 95)), 2),
            "observed_max": round(float(np.max(y2_raw)), 2)
        },
        "prospective_tweedie_regression": {
            "predicted_mean_unweighted": round(tw_mean, 2),
            "predicted_mean_survey_weighted": round(tw_weighted_mean, 2),
            "unweighted_mae": round(tw_mae, 2),
            "survey_weighted_mae": round(tw_w_mae, 2),
            "unweighted_rmse": round(tw_rmse, 2),
            "survey_weighted_rmse": round(tw_w_rmse, 2),
            "unweighted_r2": round(tw_r2, 4),
            "survey_weighted_r2": round(tw_w_r2, 4),
            "decile_stratification": tw_deciles
        },
        "prospective_xgboost_regression": {
            "predicted_mean_unweighted": round(xgb_mean, 2),
            "predicted_mean_survey_weighted": round(xgb_weighted_mean, 2),
            "unweighted_mae": round(xgb_mae, 2),
            "survey_weighted_mae": round(xgb_w_mae, 2),
            "unweighted_rmse": round(xgb_rmse, 2),
            "survey_weighted_rmse": round(xgb_w_rmse, 2),
            "unweighted_r2": round(xgb_r2, 4),
            "survey_weighted_r2": round(xgb_w_r2, 4)
        },
        "lagged_expenditure_baseline": {
            "description": "Predicting 2024 spend directly with 2023 spend (TOTEXPY1)",
            "unweighted_mae": round(lag_mae, 2),
            "survey_weighted_mae": round(lag_w_mae, 2),
            "unweighted_rmse": round(lag_rmse, 2),
            "survey_weighted_rmse": round(lag_w_rmse, 2),
            "unweighted_r2": round(lag_r2, 4),
            "survey_weighted_r2": round(lag_w_r2, 4)
        },
        "prospective_classifier_unweighted_p90": {
            "locked_target_definition": f"TOTEXPY2 >= ${LOCKED_UNWEIGHTED_P90:,.2f}",
            "validation_prevalence": round(unw_prev, 4),
            "roc_auc": round(unw_auc, 4),
            "pr_auc": round(unw_prauc, 4),
            "brier_score": round(unw_brier, 5),
            "training_baseline_brier": round(unw_base_brier, 5),
            "brier_skill_score": round(unw_bss, 4),
            "calibration_intercept": round(unw_cal_int, 4),
            "calibration_slope": round(unw_cal_slope, 4),
            "unweighted_calibration_intercept": round(unw_cal_int, 4),
            "unweighted_calibration_slope": round(unw_cal_slope, 4),
            "calibration_estimator": unw_cal_method,
            "unweighted_calibration_estimator": unw_cal_method
        },
        "prospective_classifier_weighted_p90": {
            "locked_target_definition": f"TOTEXPY2 >= ${LOCKED_WEIGHTED_P90:,.2f} (Survey-Weighted)",
            "validation_weighted_prevalence": round(w_prev, 4),
            "roc_auc": round(w_auc, 4),
            "pr_auc": round(w_prauc, 4),
            "survey_weighted_brier_score": round(w_brier, 5),
            "training_baseline_weighted_brier": round(w_base_brier, 5),
            "brier_skill_score": round(w_bss, 4),
            "calibration_intercept": round(w_cal_int, 4),
            "calibration_slope": round(w_cal_slope, 4),
            "survey_weighted_calibration_intercept": round(w_cal_int, 4),
            "survey_weighted_calibration_slope": round(w_cal_slope, 4),
            "unweighted_calibration_intercept": round(unw_w_cal_int, 4),
            "unweighted_calibration_slope": round(unw_w_cal_slope, 4),
            "calibration_estimator": w_cal_method,
            "survey_weighted_calibration_estimator": w_cal_method,
            "unweighted_calibration_estimator": unw_w_cal_method
        },
        "subgroup_performance": subgroups
    }

    metrics_out = os.path.join(HC257_DIR, "metrics_hc257.json")
    with open(metrics_out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved prospective validation metrics to {metrics_out}")

    deciles_df = pd.DataFrame(tw_deciles)
    deciles_csv = os.path.join(HC257_DIR, "deciles_hc257.csv")
    deciles_df.to_csv(deciles_csv, index=False)
    print(f"Saved decile breakdown to {deciles_csv}")

    subgroups_df = pd.DataFrame(subgroups)
    subgroups_csv = os.path.join(HC257_DIR, "subgroups_hc257.csv")
    subgroups_df.to_csv(subgroups_csv, index=False)
    print(f"Saved subgroup breakdown to {subgroups_csv}")

    print("\nHC-257 Prospective Validation Complete.")
    print(f"Prospective Tweedie Observed vs Pred Mean: ${obs_mean_raw:,.2f} vs ${tw_mean:,.2f} (MAE: ${tw_mae:,.2f}, R2: {tw_r2:.4f})")
    print(f"Lagged Year 1 Expenditure Baseline MAE: ${lag_mae:,.2f}, R2: {lag_r2:.4f}")
    print(f"Weighted P90 Classifier Prospective ROC-AUC: {w_auc:.4f}, BSS: {w_bss:.4f}")


if __name__ == "__main__":
    main()
