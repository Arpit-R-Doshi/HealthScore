"""
External Cross-Year Validation Script: MEPS HC-256 (2024 Full Year Consolidated)
Evaluates frozen 2023 Phase 1 models against 2024 external cross-sectional data.

Zero retraining or tuning. Locked 2023 thresholds:
  - Unweighted P90: $20,360.50
  - Survey-Weighted P90: $17,827.41
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
HC256_DIR = os.path.join(BASE_DIR, "validation", "hc256")
DATA_PATH = os.path.join(HC256_DIR, "data", "h256.dta")

OBSERVABLE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Age_x_Comorbidity'
]

LOCKED_UNWEIGHTED_P90 = 20360.50
LOCKED_WEIGHTED_P90 = 17827.41

# Locked training baseline prevalences from Phase 1 training metadata / evaluation metrics
# Target 1 unweighted sample P90 prevalence: 0.1000266 (~10%)
# Target 2 survey-weighted population P90 prevalence: 0.099888 (~9.99%)
TRAIN_UNWEIGHTED_PREV_P90 = 0.1000266
TRAIN_WEIGHTED_PREV_P90 = 0.099888


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
    # Logit transform with clipping
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
    print("MEPS HC-256 (2024) External Cross-Year Validation")
    print("=" * 80)

    # 1. Dataset verification
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"HC-256 data not found at {DATA_PATH}")

    data_hash = get_sha256(DATA_PATH)
    print(f"Data file: {DATA_PATH}")
    print(f"SHA-256: {data_hash}")

    # 2. Load and harmonize features
    raw_df = pd.read_stata(DATA_PATH, convert_categoricals=False)
    raw_count = len(raw_df)
    print(f"Raw 2024 records: {raw_count}")

    # Eligibility filter: AGE24X >= 0
    clean_df = raw_df[raw_df['AGE24X'] >= 0].copy()
    invalid_age_dropped = raw_count - len(clean_df)
    analysis_sample_size = len(clean_df)
    print(f"Dropped invalid age (<0): {invalid_age_dropped}")
    print(f"Eligible analysis cohort: {analysis_sample_size}")

    # Exact Phase 1 Training Feature Engineering Mapping
    clean_df['AGE23X'] = clean_df['AGE24X'].astype(float)
    clean_df['Gender_Male'] = (clean_df['SEX'] == 1).astype(int)

    # Binarize condition indicators: 1=Yes, 0=Otherwise (-1, 2, etc.)
    for col in ['HIBPDX', 'CHDDX', 'MIDX', 'STRKDX', 'DIABDX_M18', 'CHOLDX',
                'ASTHDX', 'EMPHDX', 'CHBRON31', 'CANCERDX', 'ARTHDX', 'JTPAIN31_M18', 'ADHDADDX']:
        clean_df[col] = (clean_df[col] == 1).astype(int)

    # ADDPRS42: Depression screener (values 1, 2, 3 indicate depressive symptoms past 2 weeks)
    clean_df['ADDPRS42'] = clean_df['ADDPRS42'].apply(lambda x: 1 if x in [1, 2, 3] else 0)

    # Exact Phase 1 Integer Cluster Formulas
    clean_df['Cardio_ACG'] = clean_df['HIBPDX'] + clean_df['CHDDX'] + clean_df['MIDX'] + clean_df['STRKDX']
    clean_df['Metabolic_ACG'] = clean_df['DIABDX_M18'] + clean_df['CHOLDX']
    clean_df['Respiratory_ACG'] = clean_df['ASTHDX'] + clean_df['EMPHDX'] + clean_df['CHBRON31']
    clean_df['Oncology_ACG'] = clean_df['CANCERDX']
    clean_df['Musculoskeletal_ACG'] = clean_df['ARTHDX'] + clean_df['JTPAIN31_M18']
    clean_df['Psychiatric_ACG'] = clean_df['ADDPRS42'] + clean_df['ADHDADDX']

    # Derived comorbidities
    cluster_cols = ['Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG']
    clean_df['Comorbidity_Count'] = (clean_df[cluster_cols] > 0).sum(axis=1)
    clean_df['Multimorbidity_Penalty'] = clean_df['Comorbidity_Count'] ** 2
    clean_df['Age_x_Comorbidity'] = clean_df['AGE23X'] * clean_df['Comorbidity_Count']

    X_val = clean_df[OBSERVABLE_COLS].copy()
    y_raw = clean_df['TOTEXP24'].values.astype(float)
    y_log = np.log1p(y_raw)
    weights = clean_df['PERWT24F'].values.astype(float)
    norm_weights = weights / np.mean(weights)

    # 3. Load Frozen Models
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

    print("Loaded frozen models successfully.")

    # 4. Generate Predictions
    # XGBoost regression
    xgb_pred_log = reg_model.predict(X_val)
    xgb_pred_dollar = np.maximum(0.0, np.expm1(xgb_pred_log))

    # Tweedie regression
    tweedie_pred_dollar = np.maximum(0.0, tweedie_model.predict(X_val))

    # Classifiers
    prob_unweighted_p90 = cls_unweighted_model.predict_proba(X_val)[:, 1]
    prob_weighted_p90 = cls_weighted_model.predict_proba(X_val)[:, 1]

    # Binary labels for locked thresholds
    y_unweighted_p90 = (y_raw >= LOCKED_UNWEIGHTED_P90).astype(int)
    y_weighted_p90 = (y_raw >= LOCKED_WEIGHTED_P90).astype(int)

    # 5. Evaluate Observable Regression (XGBoost & Tweedie)
    obs_mean_raw = float(np.mean(y_raw))
    obs_weighted_mean_raw = compute_weighted_mean(y_raw, weights)

    # XGBoost Dollar Metrics
    xgb_mean = float(np.mean(xgb_pred_dollar))
    xgb_weighted_mean = compute_weighted_mean(xgb_pred_dollar, weights)
    xgb_mae = float(mean_absolute_error(y_raw, xgb_pred_dollar))
    xgb_w_mae = compute_weighted_mae(y_raw, xgb_pred_dollar, weights)
    xgb_rmse = float(np.sqrt(mean_squared_error(y_raw, xgb_pred_dollar)))
    xgb_w_rmse = compute_weighted_rmse(y_raw, xgb_pred_dollar, weights)
    xgb_r2 = float(r2_score(y_raw, xgb_pred_dollar))
    xgb_w_r2 = compute_weighted_r2(y_raw, xgb_pred_dollar, weights)

    # Tweedie Dollar Metrics
    tw_mean = float(np.mean(tweedie_pred_dollar))
    tw_weighted_mean = compute_weighted_mean(tweedie_pred_dollar, weights)
    tw_mae = float(mean_absolute_error(y_raw, tweedie_pred_dollar))
    tw_w_mae = compute_weighted_mae(y_raw, tweedie_pred_dollar, weights)
    tw_rmse = float(np.sqrt(mean_squared_error(y_raw, tweedie_pred_dollar)))
    tw_w_rmse = compute_weighted_rmse(y_raw, tweedie_pred_dollar, weights)
    tw_r2 = float(r2_score(y_raw, tweedie_pred_dollar))
    tw_w_r2 = compute_weighted_r2(y_raw, tweedie_pred_dollar, weights)

    # 6. Decile Stratification (by Tweedie and XGBoost)
    # Tweedie deciles
    clean_df['tw_pred'] = tweedie_pred_dollar
    clean_df['tw_decile'] = pd.qcut(clean_df['tw_pred'], q=10, labels=False, duplicates='drop') + 1
    
    tw_deciles = []
    for d in range(1, 11):
        sub = clean_df[clean_df['tw_decile'] == d]
        cnt = len(sub)
        o_mean = float(sub['TOTEXP24'].mean())
        p_mean = float(sub['tw_pred'].mean())
        ratio = float(o_mean / p_mean) if p_mean > 0 else 0.0
        tw_deciles.append({
            "decile": d,
            "count": cnt,
            "observed_mean": round(o_mean, 2),
            "predicted_mean": round(p_mean, 2),
            "ratio_obs_to_pred": round(ratio, 4)
        })

    # XGBoost deciles
    clean_df['xgb_pred'] = xgb_pred_dollar
    clean_df['xgb_decile'] = pd.qcut(clean_df['xgb_pred'], q=10, labels=False, duplicates='drop') + 1
    xgb_deciles = []
    for d in range(1, 11):
        sub = clean_df[clean_df['xgb_decile'] == d]
        cnt = len(sub)
        o_mean = float(sub['TOTEXP24'].mean())
        p_mean = float(sub['xgb_pred'].mean())
        ratio = float(o_mean / p_mean) if p_mean > 0 else 0.0
        xgb_deciles.append({
            "decile": d,
            "count": cnt,
            "observed_mean": round(o_mean, 2),
            "predicted_mean": round(p_mean, 2),
            "ratio_obs_to_pred": round(ratio, 4)
        })

    # 7. Evaluate Classifiers
    # Unweighted P90 Classifier
    unw_prev = float(np.mean(y_unweighted_p90))
    unw_auc = float(roc_auc_score(y_unweighted_p90, prob_unweighted_p90))
    unw_prauc = float(average_precision_score(y_unweighted_p90, prob_unweighted_p90))
    unw_brier = float(brier_score_loss(y_unweighted_p90, prob_unweighted_p90))
    # Baseline constant brier using training baseline prevalence
    unw_base_brier = float(brier_score_loss(y_unweighted_p90, np.full_like(y_unweighted_p90, TRAIN_UNWEIGHTED_PREV_P90, dtype=float)))
    unw_bss = float(1.0 - (unw_brier / unw_base_brier)) if unw_base_brier > 0 else 0.0
    unw_cal_int, unw_cal_slope, unw_cal_method = compute_calibration(y_unweighted_p90, prob_unweighted_p90)

    # Weighted P90 Classifier
    w_prev = compute_weighted_mean(y_weighted_p90, weights)
    w_auc = float(roc_auc_score(y_weighted_p90, prob_weighted_p90, sample_weight=weights))
    w_prauc = float(average_precision_score(y_weighted_p90, prob_weighted_p90, sample_weight=weights))
    w_brier = compute_weighted_brier(y_weighted_p90, prob_weighted_p90, weights)
    w_base_brier = compute_weighted_brier(y_weighted_p90, np.full_like(y_weighted_p90, TRAIN_WEIGHTED_PREV_P90, dtype=float), weights)
    w_bss = float(1.0 - (w_brier / w_base_brier)) if w_base_brier > 0 else 0.0
    w_cal_int, w_cal_slope, w_cal_method = compute_calibration(y_weighted_p90, prob_weighted_p90, weights=weights)
    unw_w_cal_int, unw_w_cal_slope, unw_w_cal_method = compute_calibration(y_weighted_p90, prob_weighted_p90)

    # 8. Subgroup Analysis
    # By Age Group
    clean_df['age_group'] = pd.cut(
        clean_df['AGE23X'],
        bins=[-np.inf, 17, 44, 64, np.inf],
        labels=['<18', '18-44', '45-64', '65+']
    )
    subgroups = []
    for grp, df_g in clean_df.groupby('age_group', observed=True):
        cnt = len(df_g)
        o_m = float(df_g['TOTEXP24'].mean())
        tw_m = float(df_g['tw_pred'].mean())
        xgb_m = float(df_g['xgb_pred'].mean())
        tw_mae_g = float(mean_absolute_error(df_g['TOTEXP24'], df_g['tw_pred']))
        xgb_mae_g = float(mean_absolute_error(df_g['TOTEXP24'], df_g['xgb_pred']))
        subgroups.append({
            "dimension": "Age Group",
            "group": str(grp),
            "count": cnt,
            "observed_mean": round(o_m, 2),
            "tweedie_pred_mean": round(tw_m, 2),
            "xgb_pred_mean": round(xgb_m, 2),
            "tweedie_mae": round(tw_mae_g, 2),
            "xgb_mae": round(xgb_mae_g, 2),
            "ratio_obs_to_tweedie": round(o_m / tw_m, 4) if tw_m > 0 else 0.0
        })

    # By Gender
    for grp, df_g in clean_df.groupby('Gender_Male'):
        cnt = len(df_g)
        o_m = float(df_g['TOTEXP24'].mean())
        tw_m = float(df_g['tw_pred'].mean())
        xgb_m = float(df_g['xgb_pred'].mean())
        tw_mae_g = float(mean_absolute_error(df_g['TOTEXP24'], df_g['tw_pred']))
        xgb_mae_g = float(mean_absolute_error(df_g['TOTEXP24'], df_g['xgb_pred']))
        subgroups.append({
            "dimension": "Gender",
            "group": "Male" if grp == 1 else "Female",
            "count": cnt,
            "observed_mean": round(o_m, 2),
            "tweedie_pred_mean": round(tw_m, 2),
            "xgb_pred_mean": round(xgb_m, 2),
            "tweedie_mae": round(tw_mae_g, 2),
            "xgb_mae": round(xgb_mae_g, 2),
            "ratio_obs_to_tweedie": round(o_m / tw_m, 4) if tw_m > 0 else 0.0
        })

    # By Comorbidity Count (0, 1, 2, 3+)
    clean_df['comorb_cat'] = clean_df['Comorbidity_Count'].apply(lambda c: '0' if c == 0 else ('1' if c == 1 else ('2' if c == 2 else '3+')))
    for grp in ['0', '1', '2', '3+']:
        df_g = clean_df[clean_df['comorb_cat'] == grp]
        cnt = len(df_g)
        o_m = float(df_g['TOTEXP24'].mean())
        tw_m = float(df_g['tw_pred'].mean())
        xgb_m = float(df_g['xgb_pred'].mean())
        tw_mae_g = float(mean_absolute_error(df_g['TOTEXP24'], df_g['tw_pred']))
        xgb_mae_g = float(mean_absolute_error(df_g['TOTEXP24'], df_g['xgb_pred']))
        subgroups.append({
            "dimension": "Comorbidity Count",
            "group": grp,
            "count": cnt,
            "observed_mean": round(o_m, 2),
            "tweedie_pred_mean": round(tw_m, 2),
            "xgb_pred_mean": round(xgb_m, 2),
            "tweedie_mae": round(tw_mae_g, 2),
            "xgb_mae": round(xgb_mae_g, 2),
            "ratio_obs_to_tweedie": round(o_m / tw_m, 4) if tw_m > 0 else 0.0
        })

    # 9. Temporal Drift Indicators (2023 vs 2024 target and feature distribution)
    # 2024 specific P90 thresholds
    unw_p90_2024 = float(np.percentile(y_raw, 90))
    # Survey-weighted P90 in 2024
    sorted_idx = np.argsort(y_raw)
    cum_w = np.cumsum(weights[sorted_idx]) / np.sum(weights)
    w_p90_2024 = float(y_raw[sorted_idx][np.searchsorted(cum_w, 0.90)])

    results = {
        "metadata": {
            "validation_dataset": "MEPS HC-256 (2024 Full Year Consolidated)",
            "data_file_sha256": data_hash,
            "raw_record_count": raw_count,
            "invalid_age_dropped": invalid_age_dropped,
            "eligible_analysis_sample_size": analysis_sample_size,
            "zero_expenditure_count": int((y_raw == 0).sum()),
            "zero_expenditure_pct": round(float((y_raw == 0).sum() / analysis_sample_size * 100), 2),
            "locked_2023_unweighted_p90": LOCKED_UNWEIGHTED_P90,
            "locked_2023_weighted_p90": LOCKED_WEIGHTED_P90,
            "temporal_2024_unweighted_p90": round(unw_p90_2024, 2),
            "temporal_2024_weighted_p90": round(w_p90_2024, 2)
        },
        "target_distribution_2024": {
            "observed_mean_unweighted": round(obs_mean_raw, 2),
            "observed_mean_survey_weighted": round(obs_weighted_mean_raw, 2),
            "observed_median": round(float(np.median(y_raw)), 2),
            "observed_std": round(float(np.std(y_raw)), 2),
            "observed_p95": round(float(np.percentile(y_raw, 95)), 2),
            "observed_p99": round(float(np.percentile(y_raw, 99)), 2),
            "observed_max": round(float(np.max(y_raw)), 2)
        },
        "observable_tweedie_regression": {
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
        "observable_xgboost_regression": {
            "predicted_mean_unweighted": round(xgb_mean, 2),
            "predicted_mean_survey_weighted": round(xgb_weighted_mean, 2),
            "unweighted_mae": round(xgb_mae, 2),
            "survey_weighted_mae": round(xgb_w_mae, 2),
            "unweighted_rmse": round(xgb_rmse, 2),
            "survey_weighted_rmse": round(xgb_w_rmse, 2),
            "unweighted_r2": round(xgb_r2, 4),
            "survey_weighted_r2": round(xgb_w_r2, 4),
            "decile_stratification": xgb_deciles
        },
        "observable_classifier_unweighted_p90": {
            "locked_target_definition": f"TOTEXP24 >= ${LOCKED_UNWEIGHTED_P90:,.2f}",
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
        "observable_classifier_weighted_p90": {
            "locked_target_definition": f"TOTEXP24 >= ${LOCKED_WEIGHTED_P90:,.2f} (Survey-Weighted)",
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

    # Save metrics JSON
    metrics_out = os.path.join(HC256_DIR, "metrics_hc256.json")
    with open(metrics_out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved validation metrics to {metrics_out}")

    # Save deciles CSV
    deciles_df = pd.DataFrame(tw_deciles)
    deciles_csv = os.path.join(HC256_DIR, "deciles_hc256.csv")
    deciles_df.to_csv(deciles_csv, index=False)
    print(f"Saved decile breakdown to {deciles_csv}")

    # Save subgroups CSV
    subgroups_df = pd.DataFrame(subgroups)
    subgroups_csv = os.path.join(HC256_DIR, "subgroups_hc256.csv")
    subgroups_df.to_csv(subgroups_csv, index=False)
    print(f"Saved subgroup breakdown to {subgroups_csv}")

    print("\nHC-256 Validation Complete.")
    print(f"Tweedie 2024 Observed vs Pred Mean: ${obs_mean_raw:,.2f} vs ${tw_mean:,.2f} (MAE: ${tw_mae:,.2f})")
    print(f"XGBoost 2024 Observed vs Pred Mean: ${obs_mean_raw:,.2f} vs ${xgb_mean:,.2f} (MAE: ${xgb_mae:,.2f})")
    print(f"Weighted P90 Classifier ROC-AUC: {w_auc:.4f}, BSS: {w_bss:.4f}")


if __name__ == "__main__":
    main()
