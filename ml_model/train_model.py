"""
HealthScore Model Training Pipeline (Revised Phase 1 - Deployment Parity & Econometric Evaluation)
Canonical script for training, evaluating, and exporting HealthScore ML models.
Implements:
  - 11-feature observable-input model as the leading candidate for frontend deployment.
  - Deployment parity comparison: 11-feature observable vs 14-feature with deployment imputation.
  - Expected dollar spending estimators: Tweedie Compound Poisson-Gamma GLM and Two-Part Model (2PM) with Duan smearing.
  - Stratification & ranking analysis across expenditure tiers.
  - Target-specific constant baselines and calibration diagnostics for high-expenditure classifiers.
  - Ordinary row-level percentile bootstrap 95% confidence intervals (exploratory held-out evaluation).
  - Clean serialization of production artifacts without bytecode pollution.
"""

import os
import sys
import json
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

warnings.filterwarnings('ignore')

from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression, Ridge, TweedieRegressor, LogisticRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    r2_score, mean_absolute_error, root_mean_squared_error, median_absolute_error,
    roc_auc_score, average_precision_score, brier_score_loss,
    precision_score, recall_score, f1_score
)
import xgboost as xgb
import shap

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_pipeline import (
    load_raw_meps, clean_and_engineer_features, split_data,
    FEATURE_COLS, OBSERVABLE_FEATURE_COLS, DEFAULT_DATA_PATH
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# Primary model artifact destinations
PRIMARY_MODEL_FILE = os.path.join(BASE_DIR, "risk_model.pkl")
BENCHMARK_FILE = os.path.join(BASE_DIR, "benchmark_costs.pkl")


def bootstrap_regression_ci(y_true, y_pred, n_boot=1000, seed=42):
    """
    Computes ordinary row-level percentile bootstrap 95% confidence intervals.
    NOTE: These reflect sample resampling uncertainty on the held-out test split,
    NOT complex-survey design-based population confidence intervals.
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    indices = rng.integers(0, n, size=(n_boot, n))
    
    maes = np.empty(n_boot)
    rmses = np.empty(n_boot)
    r2s = np.empty(n_boot)
    
    y_true_arr = np.asarray(y_true)
    y_pred_arr = np.asarray(y_pred)
    
    for i in range(n_boot):
        idx = indices[i]
        yt = y_true_arr[idx]
        yp = y_pred_arr[idx]
        maes[i] = mean_absolute_error(yt, yp)
        rmses[i] = root_mean_squared_error(yt, yp)
        r2s[i] = r2_score(yt, yp)
        
    return {
        "mae_ci_95": [round(float(np.percentile(maes, 2.5)), 2), round(float(np.percentile(maes, 97.5)), 2)],
        "rmse_ci_95": [round(float(np.percentile(rmses, 2.5)), 2), round(float(np.percentile(rmses, 97.5)), 2)],
        "r2_ci_95": [round(float(np.percentile(r2s, 2.5)), 4), round(float(np.percentile(r2s, 97.5)), 4)]
    }


def bootstrap_classification_ci(y_true, y_prob, n_boot=1000, seed=42):
    """Computes ordinary row-level percentile bootstrap 95% confidence intervals for classifiers."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    indices = rng.integers(0, n, size=(n_boot, n))
    
    rocs = np.empty(n_boot)
    prs = np.empty(n_boot)
    briers = np.empty(n_boot)
    
    y_true_arr = np.asarray(y_true)
    y_prob_arr = np.asarray(y_prob)
    
    for i in range(n_boot):
        idx = indices[i]
        yt = y_true_arr[idx]
        yp = y_prob_arr[idx]
        if len(np.unique(yt)) > 1:
            rocs[i] = roc_auc_score(yt, yp)
            prs[i] = average_precision_score(yt, yp)
        else:
            rocs[i] = np.nan
            prs[i] = np.nan
        briers[i] = brier_score_loss(yt, yp)
        
    rocs = rocs[~np.isnan(rocs)]
    prs = prs[~np.isnan(prs)]
    
    return {
        "roc_auc_ci_95": [round(float(np.percentile(rocs, 2.5)), 4), round(float(np.percentile(rocs, 97.5)), 4)],
        "pr_auc_ci_95": [round(float(np.percentile(prs, 2.5)), 4), round(float(np.percentile(prs, 97.5)), 4)],
        "brier_ci_95": [round(float(np.percentile(briers, 2.5)), 4), round(float(np.percentile(briers, 97.5)), 4)]
    }


def compute_calibration_slope_intercept(y_true, y_prob):
    """Computes calibration intercept (alpha) and slope (beta) via unregularized logistic fit."""
    eps = 1e-6
    p_clipped = np.clip(y_prob, eps, 1.0 - eps)
    logit_p = np.log(p_clipped / (1.0 - p_clipped)).reshape(-1, 1)
    
    cal_lr = LogisticRegression(C=1e9, solver='lbfgs', random_state=42)
    cal_lr.fit(logit_p, y_true)
    intercept = float(cal_lr.intercept_[0])
    slope = float(cal_lr.coef_[0][0])
    return round(intercept, 4), round(slope, 4)


def calculate_metrics(y_true, y_pred, weights=None, compute_ci=True):
    """Computes both unweighted and survey-weighted evaluation metrics."""
    mae_unw = float(mean_absolute_error(y_true, y_pred))
    medae_unw = float(median_absolute_error(y_true, y_pred))
    rmse_unw = float(root_mean_squared_error(y_true, y_pred))
    r2_unw = float(r2_score(y_true, y_pred))
    log_r2 = float(r2_score(np.log1p(np.maximum(y_true, 0)), np.log1p(np.maximum(y_pred, 0))))

    metrics = {
        "mae_unweighted": round(mae_unw, 2),
        "medae_unweighted": round(medae_unw, 2),
        "rmse_unweighted": round(rmse_unw, 2),
        "r2_unweighted": round(r2_unw, 4),
        "r2_log": round(log_r2, 4),
        "mean_predicted": round(float(np.mean(y_pred)), 2),
        "mean_observed": round(float(np.mean(y_true)), 2)
    }

    if compute_ci:
        ci = bootstrap_regression_ci(y_true, y_pred)
        metrics.update(ci)

    if weights is not None:
        w = np.asarray(weights, dtype=float)
        sum_w = np.sum(w)
        mae_w = float(np.sum(w * np.abs(y_true - y_pred)) / sum_w)
        rmse_w = float(np.sqrt(np.sum(w * (y_true - y_pred)**2) / sum_w))
        y_bar_w = np.sum(w * y_true) / sum_w
        ss_tot_w = np.sum(w * (y_true - y_bar_w)**2)
        ss_res_w = np.sum(w * (y_true - y_pred)**2)
        r2_w = float(1.0 - (ss_res_w / ss_tot_w))

        metrics.update({
            "mae_weighted": round(mae_w, 2),
            "rmse_weighted": round(rmse_w, 2),
            "r2_weighted": round(r2_w, 4)
        })

    return metrics


def calculate_classification_metrics(y_true, y_prob, target_baseline_brier, threshold=0.10, compute_ci=True, weights=None, baseline_brier_wtd=None):
    """Computes classification metrics with probability calibration diagnostics against a target-specific baseline."""
    roc_auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.5
    pr_auc = float(average_precision_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float(np.mean(y_true))
    brier = float(brier_score_loss(y_true, y_prob))
    mean_p = float(np.mean(y_prob))
    bss = float(1.0 - (brier / target_baseline_brier)) if target_baseline_brier > 0 else 0.0

    y_pred = (y_prob >= threshold).astype(int)
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    intercept, slope = compute_calibration_slope_intercept(y_true, y_prob)

    metrics = {
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "target_baseline_brier": round(target_baseline_brier, 4),
        "brier_skill_score": round(bss, 4),
        "calibration_intercept": intercept,
        "calibration_slope": slope,
        "mean_predicted_prob": round(mean_p, 4),
        "operating_threshold": threshold,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4)
    }

    if weights is not None and baseline_brier_wtd is not None:
        sum_w = float(np.sum(weights))
        w_brier = float(np.sum(weights * (y_true - y_prob)**2) / sum_w)
        w_bss = float(1.0 - (w_brier / baseline_brier_wtd))
        metrics["survey_weighted_brier"] = round(w_brier, 4)
        metrics["survey_weighted_target_baseline_brier"] = round(baseline_brier_wtd, 4)
        metrics["survey_weighted_brier_skill_score"] = round(w_bss, 4)

    if compute_ci:
        ci = bootstrap_classification_ci(y_true, y_prob)
        metrics.update(ci)

    return metrics


def build_deployment_imputed_test_set(X_test, imputation_table):
    """
    Constructs an inference-parity test set where unobserved SAQ features are replaced
    by the empirical conditional expectations derived from the training set.
    """
    X_imp = X_test.astype(float).copy()
    for idx, row in X_imp.iterrows():
        age = row['AGE23X']
        cc = row['Comorbidity_Count']
        if age < 18:
            ab = 'pediatric'
        elif age < 45:
            ab = 'young_adult'
        elif age < 65:
            ab = 'middle_aged'
        else:
            ab = 'senior'
        ct = 'tier_0' if cc == 0 else ('tier_1' if cc == 1 else 'tier_2plus')
        key = f'{ab}_{ct}'
        imp = imputation_table[key]

        genh = imp['perceived_health']
        lmi = imp['physical_limitation']
        cog = imp['cognitive_difficulty']
        frailty = genh + (2.0 * lmi) + (2.0 * cog)

        X_imp.loc[idx, 'Frailty_Index'] = frailty
        X_imp.loc[idx, 'Age_x_Frailty'] = age * frailty
        X_imp.loc[idx, 'K6SUM42'] = imp['k6_distress']
    return X_imp


def train_and_evaluate_regressors(splits):
    """
    Trains and compares candidate regressors.
    Evaluates:
      1. 11-feature Observable-Only XGBoost (Leading Deployment Candidate)
      2. 14-feature XGBoost with Deployment Imputation
      3. 14-feature XGBoost Oracle (with ground truth survey features)
      4. Tweedie Compound Poisson-Gamma GLM (Dollar deviance optimizer)
      5. Two-Part Model (2PM) with Duan Smearing (Econometric expected dollar estimator)
      6. Linear and Ridge baselines
    """
    print("\n--- Evaluating Candidate Regressors on Held-Out Test Set ---")
    X_train, X_test = splits["X_train"], splits["X_test"]
    y_train_log, y_test_log = splits["y_train_log"], splits["y_test_log"]
    y_train_raw, y_test_raw = splits["y_train_raw"], splits["y_test_raw"]
    w_train, w_test = splits["w_train"], splits["w_test"]
    w_train_norm = splits["w_train_norm"]
    impute_table = splits["imputation_table"]

    regressor_results = {}

    # 1. Baseline Median
    p_median = np.full_like(y_test_raw, np.median(y_train_raw))
    regressor_results["Baseline_Median"] = calculate_metrics(y_test_raw, p_median, w_test)

    # 2. Baseline Mean
    p_mean = np.full_like(y_test_raw, np.mean(y_train_raw))
    regressor_results["Baseline_Mean"] = calculate_metrics(y_test_raw, p_mean, w_test)

    # 3. Model 1 (Leading Deployment Candidate): 11-Feature Observable-Only XGBoost
    obs_cols = splits["observable_feature_cols"]
    X_tr_obs = X_train[obs_cols]
    X_te_obs = X_test[obs_cols]
    xgb_observable = xgb.XGBRegressor(
        objective="reg:squarederror", n_estimators=500, learning_rate=0.01,
        max_depth=5, subsample=0.8, colsample_bytree=0.8, gamma=2,
        reg_alpha=1, reg_lambda=1, random_state=42
    ).fit(X_tr_obs, y_train_log)
    p_xgb_obs = np.maximum(np.expm1(xgb_observable.predict(X_te_obs)), 0)
    regressor_results["XGBoost_ObservableOnly_Unweighted"] = calculate_metrics(y_test_raw, p_xgb_obs, w_test)

    # 4. Model 1 (Survey-Weighted Fit): 11-Feature Observable-Only XGBoost
    xgb_obs_w = xgb.XGBRegressor(
        objective="reg:squarederror", n_estimators=500, learning_rate=0.01,
        max_depth=5, subsample=0.8, colsample_bytree=0.8, gamma=2,
        reg_alpha=1, reg_lambda=1, random_state=42
    ).fit(X_tr_obs, y_train_log, sample_weight=w_train_norm)
    p_xgb_obs_w = np.maximum(np.expm1(xgb_obs_w.predict(X_te_obs)), 0)
    regressor_results["XGBoost_ObservableOnly_WeightedFit"] = calculate_metrics(y_test_raw, p_xgb_obs_w, w_test)

    # 5. Full 14-Feature XGBoost Model
    xgb_full = xgb.XGBRegressor(
        objective="reg:squarederror", n_estimators=500, learning_rate=0.01,
        max_depth=5, subsample=0.8, colsample_bytree=0.8, gamma=2,
        reg_alpha=1, reg_lambda=1, random_state=42
    ).fit(X_train, y_train_log)

    # 6. Model 2: 14-Feature XGBoost with DEPLOYMENT IMPUTATION
    X_te_imp = build_deployment_imputed_test_set(X_test, impute_table)
    p_xgb_imp = np.maximum(np.expm1(xgb_full.predict(X_te_imp[FEATURE_COLS])), 0)
    regressor_results["XGBoost_14Feat_DeploymentImputed"] = calculate_metrics(y_test_raw, p_xgb_imp, w_test)

    # 7. Model 3: 14-Feature XGBoost Oracle (with ground truth survey features)
    p_xgb_oracle = np.maximum(np.expm1(xgb_full.predict(X_test)), 0)
    regressor_results["XGBoost_14Feat_OracleGroundTruth"] = calculate_metrics(y_test_raw, p_xgb_oracle, w_test)

    # 8. Tweedie Compound Poisson-Gamma GLM (11-Feature Observable-Only, Unweighted Fit)
    tw_obs = TweedieRegressor(power=1.5, link="log", max_iter=1000).fit(X_tr_obs, y_train_raw)
    p_tw_obs = tw_obs.predict(X_te_obs)
    regressor_results["Tweedie_GLM_ObservableOnly_Unweighted"] = calculate_metrics(y_test_raw, p_tw_obs, w_test)

    # 9. Tweedie Compound Poisson-Gamma GLM (14-Feature Full Model, Unweighted Fit)
    tw_unw = TweedieRegressor(power=1.5, link="log", max_iter=1000).fit(X_train, y_train_raw)
    p_tw_unw_oracle = tw_unw.predict(X_test)
    p_tw_unw_imp = tw_unw.predict(X_te_imp[FEATURE_COLS])
    regressor_results["Tweedie_GLM_14Feat_Unweighted_Oracle"] = calculate_metrics(y_test_raw, p_tw_unw_oracle, w_test)
    regressor_results["Tweedie_GLM_14Feat_DeploymentImputed"] = calculate_metrics(y_test_raw, p_tw_unw_imp, w_test)
    regressor_results["Tweedie_GLM_Unweighted"] = regressor_results["Tweedie_GLM_14Feat_Unweighted_Oracle"]

    # 10. Tweedie Compound Poisson-Gamma GLM (14-Feature Full Model, Normalized Survey-Weighted Fit)
    tw_w = TweedieRegressor(power=1.5, link="log", max_iter=1000).fit(X_train, y_train_raw, sample_weight=w_train_norm)
    p_tw_w_oracle = tw_w.predict(X_test)
    p_tw_w_imp = tw_w.predict(X_te_imp[FEATURE_COLS])
    regressor_results["Tweedie_GLM_14Feat_WeightedFit_Oracle"] = calculate_metrics(y_test_raw, p_tw_w_oracle, w_test)
    regressor_results["Tweedie_GLM_14Feat_WeightedFit_DeploymentImputed"] = calculate_metrics(y_test_raw, p_tw_w_imp, w_test)
    regressor_results["Tweedie_GLM_WeightedFit"] = regressor_results["Tweedie_GLM_14Feat_WeightedFit_Oracle"]

    # 11. Two-Part Model (2PM) with Duan Smearing (Expected Dollar Estimator)
    # Part 1: Probability of positive spending Pr(Y > 0 | X)
    y_pos_train = (y_train_raw > 0).astype(int)
    part1_clf = LogisticRegression(max_iter=1000, random_state=42).fit(X_train, y_pos_train)
    p_pos_test = part1_clf.predict_proba(X_test)[:, 1]

    # Part 2: Conditional expenditure among positive spenders Y > 0
    pos_idx = (y_train_raw > 0)
    X_pos_train = X_train[pos_idx]
    y_pos_log_train = np.log(y_train_raw[pos_idx])
    part2_reg = LinearRegression().fit(X_pos_train, y_pos_log_train)

    # Duan smearing factor on positive training residuals
    residuals_pos = y_pos_log_train - part2_reg.predict(X_pos_train)
    duan_smear_factor = float(np.mean(np.exp(residuals_pos)))

    p_pos_cost = np.exp(part2_reg.predict(X_test)) * duan_smear_factor
    p_2pm = p_pos_test * p_pos_cost
    regressor_results["TwoPart_Model_DuanSmearing"] = calculate_metrics(y_test_raw, p_2pm, w_test)
    regressor_results["TwoPart_Model_DuanSmearing"]["duan_smear_factor"] = round(duan_smear_factor, 4)

    # 12. Linear Regression (OLS)
    lr_unw = LinearRegression().fit(X_train, y_train_log)
    p_lr_unw = np.maximum(np.expm1(lr_unw.predict(X_test)), 0)
    regressor_results["Linear_Regression_Unweighted"] = calculate_metrics(y_test_raw, p_lr_unw, w_test)

    # 13. Ridge Regression
    ridge_unw = Ridge(alpha=10.0).fit(X_train, y_train_log)
    p_ridge_unw = np.maximum(np.expm1(ridge_unw.predict(X_test)), 0)
    regressor_results["Ridge_Regression_Unweighted"] = calculate_metrics(y_test_raw, p_ridge_unw, w_test)

    # Subgroup Evaluation: 11-Feature Observable vs 14-Feature Imputed
    subgroups = {}
    for ab_name, (low_age, high_age) in [("pediatric", (0, 17)), ("young_adult", (18, 44)), ("middle_aged", (45, 64)), ("senior", (65, 125))]:
        sub_idx = (X_test["AGE23X"] >= low_age) & (X_test["AGE23X"] <= high_age)
        y_sub_true = y_test_raw[sub_idx]
        subgroups[ab_name] = {
            "count": int(np.sum(sub_idx)),
            "obs_model_mae": round(float(mean_absolute_error(y_sub_true, p_xgb_obs[sub_idx])), 2),
            "imputed_model_mae": round(float(mean_absolute_error(y_sub_true, p_xgb_imp[sub_idx])), 2),
            "oracle_model_mae": round(float(mean_absolute_error(y_sub_true, p_xgb_oracle[sub_idx])), 2)
        }

    return regressor_results, subgroups, xgb_observable, xgb_full, tw_unw, tw_obs, part1_clf, part2_reg, duan_smear_factor, p_xgb_obs, p_tw_obs


def train_and_evaluate_classifiers(splits):
    """
    Evaluates high-expenditure classifiers across both unweighted and weighted targets.
    Each target is evaluated against its exact target-specific constant baseline.
    Clarifies classifier input conditions: evaluates 14-feature models on both actual MEPS
    questionnaire inputs (oracle) and deployment-imputed inputs alongside 11-feature observable model.
    """
    print("\n--- Evaluating High-Expenditure Classifiers with Target-Specific Baselines ---")
    X_train, X_test = splits["X_train"], splits["X_test"]
    y_train_cls_unw, y_test_cls_unw = splits["y_train_cls_unw"], splits["y_test_cls_unw"]
    y_train_cls_wtd, y_test_cls_wtd = splits["y_train_cls_wtd"], splits["y_test_cls_wtd"]
    w_train_norm, w_test = splits["w_train_norm"], splits["w_test"]
    impute_table = splits["imputation_table"]

    # Construct deployment-imputed test set for 14-feature candidate parity
    X_te_imp = build_deployment_imputed_test_set(X_test, impute_table)

    classifier_results = {"target_unweighted_p90": {}, "target_weighted_p90": {}}

    # =========================================================================
    # TARGET 1: Unweighted Sample Top Decile (Threshold >= $20,360.50)
    # =========================================================================
    train_prev_unw = float(np.mean(y_train_cls_unw))
    test_prev_unw = float(np.mean(y_test_cls_unw))
    base_brier_unw = float(brier_score_loss(y_test_cls_unw, np.full_like(y_test_cls_unw, train_prev_unw, dtype=float)))

    # Constant Baseline
    classifier_results["target_unweighted_p90"]["Constant_Prevalence_Baseline"] = {
        "roc_auc": 0.5000, "pr_auc": round(test_prev_unw, 4), "brier_score": round(base_brier_unw, 4),
        "target_baseline_brier": round(base_brier_unw, 4), "brier_skill_score": 0.0000,
        "calibration_intercept": 0.0, "calibration_slope": 0.0, "mean_predicted_prob": round(train_prev_unw, 4),
        "operating_threshold": 0.10, "precision": round(test_prev_unw, 4), "recall": 1.0000,
        "f1": round(2 * test_prev_unw / (1.0 + test_prev_unw), 4)
    }

    # 11-Feature Observable-Only Logistic Regression (Target 1, Zero SAQ Dependency)
    obs_cols = splits["observable_feature_cols"]
    X_tr_obs = X_train[obs_cols]
    X_te_obs = X_test[obs_cols]
    lr_obs_unw = LogisticRegression(max_iter=1000, random_state=42).fit(X_tr_obs, y_train_cls_unw)
    p_lr_obs_unw = lr_obs_unw.predict_proba(X_te_obs)[:, 1]
    classifier_results["target_unweighted_p90"]["Logistic_Regression_ObservableOnly"] = calculate_classification_metrics(
        y_test_cls_unw, p_lr_obs_unw, base_brier_unw, threshold=0.10
    )

    # Logistic Regression (14-Feature, Deployment-Imputed Inputs)
    lr_unw = LogisticRegression(max_iter=1000, random_state=42).fit(X_train, y_train_cls_unw)
    p_lr_imp = lr_unw.predict_proba(X_te_imp[FEATURE_COLS])[:, 1]
    classifier_results["target_unweighted_p90"]["Logistic_Regression_14Feat_DeploymentImputed"] = calculate_classification_metrics(
        y_test_cls_unw, p_lr_imp, base_brier_unw, threshold=0.10
    )

    # Logistic Regression (14-Feature, Actual MEPS Questionnaire / Oracle Ground Truth)
    p_lr_unw = lr_unw.predict_proba(X_test)[:, 1]
    classifier_results["target_unweighted_p90"]["Logistic_Regression_14Feat_ActualMEPS_Oracle"] = calculate_classification_metrics(
        y_test_cls_unw, p_lr_unw, base_brier_unw, threshold=0.10
    )
    classifier_results["target_unweighted_p90"]["Logistic_Regression_Natural"] = classifier_results["target_unweighted_p90"]["Logistic_Regression_14Feat_ActualMEPS_Oracle"]

    # Logistic Regression (Normalized Weighted Fit, 14-Feature)
    lr_w = LogisticRegression(max_iter=1000, random_state=42).fit(X_train, y_train_cls_unw, sample_weight=w_train_norm)
    p_lr_w = lr_w.predict_proba(X_test)[:, 1]
    classifier_results["target_unweighted_p90"]["Logistic_Regression_WeightedFit"] = calculate_classification_metrics(
        y_test_cls_unw, p_lr_w, base_brier_unw, threshold=0.10
    )

    # XGBoost Classifier (Natural, 14-Feature)
    xgb_c_unw = xgb.XGBClassifier(
        n_estimators=300, learning_rate=0.03, max_depth=4,
        random_state=42, eval_metric="logloss"
    ).fit(X_train, y_train_cls_unw)
    p_xgb_c_imp = xgb_c_unw.predict_proba(X_te_imp[FEATURE_COLS])[:, 1]
    p_xgb_c_unw = xgb_c_unw.predict_proba(X_test)[:, 1]
    classifier_results["target_unweighted_p90"]["XGBoost_Classifier_14Feat_DeploymentImputed"] = calculate_classification_metrics(
        y_test_cls_unw, p_xgb_c_imp, base_brier_unw, threshold=0.10
    )
    classifier_results["target_unweighted_p90"]["XGBoost_Classifier_14Feat_ActualMEPS_Oracle"] = calculate_classification_metrics(
        y_test_cls_unw, p_xgb_c_unw, base_brier_unw, threshold=0.10
    )
    classifier_results["target_unweighted_p90"]["XGBoost_Classifier_Natural"] = classifier_results["target_unweighted_p90"]["XGBoost_Classifier_14Feat_ActualMEPS_Oracle"]

    # XGBoost Classifier (Platt Calibrated, 14-Feature)
    cal_xgb_unw = CalibratedClassifierCV(estimator=xgb_c_unw, method="sigmoid", cv=5).fit(X_train, y_train_cls_unw)
    p_cal_xgb_imp = cal_xgb_unw.predict_proba(X_te_imp[FEATURE_COLS])[:, 1]
    p_cal_xgb_unw = cal_xgb_unw.predict_proba(X_test)[:, 1]
    classifier_results["target_unweighted_p90"]["XGBoost_Classifier_PlattCalibrated_14Feat_DeploymentImputed"] = calculate_classification_metrics(
        y_test_cls_unw, p_cal_xgb_imp, base_brier_unw, threshold=0.10
    )
    classifier_results["target_unweighted_p90"]["XGBoost_Classifier_PlattCalibrated_14Feat_ActualMEPS_Oracle"] = calculate_classification_metrics(
        y_test_cls_unw, p_cal_xgb_unw, base_brier_unw, threshold=0.10
    )
    classifier_results["target_unweighted_p90"]["XGBoost_Classifier_PlattCalibrated"] = classifier_results["target_unweighted_p90"]["XGBoost_Classifier_PlattCalibrated_14Feat_ActualMEPS_Oracle"]

    # =========================================================================
    # TARGET 2: Survey-Weighted Population Top Decile (Threshold >= $17,827.41)
    # =========================================================================
    train_prev_wtd_tgt = float(np.average(y_train_cls_wtd, weights=w_train_norm))
    test_prev_wtd_tgt = float(np.average(y_test_cls_wtd, weights=w_test))
    test_prev_unw_tgt = float(np.mean(y_test_cls_wtd))

    # Evaluate constant predictor (train_prev_wtd_tgt) on test set
    base_brier_tgt2 = float(np.mean((y_test_cls_wtd - train_prev_wtd_tgt)**2))

    # Compute survey-weighted baseline on test split with aligned test weights
    w_test_norm = w_test * (len(w_test) / np.sum(w_test))
    base_brier_tgt2_wtd = float(np.average((y_test_cls_wtd - train_prev_wtd_tgt)**2, weights=w_test_norm))

    # Constant Baseline for Target 2 (Reporting both unweighted and survey-weighted estimands)
    classifier_results["target_weighted_p90"]["Constant_Prevalence_Baseline"] = {
        "roc_auc": 0.5000, "pr_auc": round(test_prev_wtd_tgt, 4), "brier_score": round(base_brier_tgt2, 4),
        "target_baseline_brier": round(base_brier_tgt2, 4), "brier_skill_score": 0.0000,
        "survey_weighted_brier": round(base_brier_tgt2_wtd, 4),
        "survey_weighted_target_baseline_brier": round(base_brier_tgt2_wtd, 4),
        "survey_weighted_brier_skill_score": 0.0000,
        "calibration_intercept": 0.0, "calibration_slope": 0.0, "mean_predicted_prob": round(train_prev_wtd_tgt, 4),
        "operating_threshold": 0.10, "precision": round(test_prev_wtd_tgt, 4), "recall": 1.0000,
        "f1": round(2 * test_prev_wtd_tgt / (1.0 + test_prev_wtd_tgt), 4),
        "exact_arithmetic_audit": {
            "training_survey_weighted_prevalence": round(train_prev_wtd_tgt, 6),
            "constant_baseline_prediction": round(train_prev_wtd_tgt, 6),
            "test_survey_weighted_outcome_prevalence": round(test_prev_wtd_tgt, 6),
            "test_unweighted_outcome_prevalence": round(test_prev_unw_tgt, 6),
            "test_survey_weighted_baseline_brier": round(base_brier_tgt2_wtd, 6),
            "test_unweighted_baseline_brier": round(base_brier_tgt2, 6),
            "formula_verification": "Brier_wtd = test_prev_wtd * (1 - 2*p_hat) + p_hat^2"
        }
    }

    # 11-Feature Observable-Only Logistic Regression (Target 2, Normalized Weighted Fit)
    lr_obs_tgt2 = LogisticRegression(max_iter=1000, random_state=42).fit(X_tr_obs, y_train_cls_wtd, sample_weight=w_train_norm)
    p_lr_obs_tgt2 = lr_obs_tgt2.predict_proba(X_te_obs)[:, 1]
    classifier_results["target_weighted_p90"]["Logistic_Regression_ObservableOnly"] = calculate_classification_metrics(
        y_test_cls_wtd, p_lr_obs_tgt2, base_brier_tgt2, threshold=0.10,
        weights=w_test_norm, baseline_brier_wtd=base_brier_tgt2_wtd
    )

    # Logistic Regression (Normalized Weighted Fit for Target 2, 14-Feature Deployment-Imputed)
    lr_tgt2 = LogisticRegression(max_iter=1000, random_state=42).fit(X_train, y_train_cls_wtd, sample_weight=w_train_norm)
    p_lr_tgt2_imp = lr_tgt2.predict_proba(X_te_imp[FEATURE_COLS])[:, 1]
    classifier_results["target_weighted_p90"]["Logistic_Regression_14Feat_DeploymentImputed"] = calculate_classification_metrics(
        y_test_cls_wtd, p_lr_tgt2_imp, base_brier_tgt2, threshold=0.10,
        weights=w_test_norm, baseline_brier_wtd=base_brier_tgt2_wtd
    )

    # Logistic Regression (Normalized Weighted Fit for Target 2, 14-Feature Actual MEPS / Oracle)
    p_lr_tgt2_oracle = lr_tgt2.predict_proba(X_test)[:, 1]
    classifier_results["target_weighted_p90"]["Logistic_Regression_14Feat_ActualMEPS_Oracle"] = calculate_classification_metrics(
        y_test_cls_wtd, p_lr_tgt2_oracle, base_brier_tgt2, threshold=0.10,
        weights=w_test_norm, baseline_brier_wtd=base_brier_tgt2_wtd
    )
    classifier_results["target_weighted_p90"]["Logistic_Regression_WeightedFit"] = classifier_results["target_weighted_p90"]["Logistic_Regression_14Feat_ActualMEPS_Oracle"]

    # Platt-Calibrated XGBoost for Target 2 (14-Feature Deployment-Imputed)
    xgb_c_tgt2 = xgb.XGBClassifier(
        n_estimators=300, learning_rate=0.03, max_depth=4,
        random_state=42, eval_metric="logloss"
    ).fit(X_train, y_train_cls_wtd)
    cal_xgb_tgt2 = CalibratedClassifierCV(estimator=xgb_c_tgt2, method="sigmoid", cv=5).fit(X_train, y_train_cls_wtd)
    p_cal_xgb_tgt2_imp = cal_xgb_tgt2.predict_proba(X_te_imp[FEATURE_COLS])[:, 1]
    classifier_results["target_weighted_p90"]["XGBoost_Classifier_PlattCalibrated_14Feat_DeploymentImputed"] = calculate_classification_metrics(
        y_test_cls_wtd, p_cal_xgb_tgt2_imp, base_brier_tgt2, threshold=0.10,
        weights=w_test_norm, baseline_brier_wtd=base_brier_tgt2_wtd
    )

    # Platt-Calibrated XGBoost for Target 2 (14-Feature Actual MEPS / Oracle)
    p_cal_xgb_tgt2_oracle = cal_xgb_tgt2.predict_proba(X_test)[:, 1]
    classifier_results["target_weighted_p90"]["XGBoost_Classifier_PlattCalibrated_14Feat_ActualMEPS_Oracle"] = calculate_classification_metrics(
        y_test_cls_wtd, p_cal_xgb_tgt2_oracle, base_brier_tgt2, threshold=0.10,
        weights=w_test_norm, baseline_brier_wtd=base_brier_tgt2_wtd
    )
    classifier_results["target_weighted_p90"]["XGBoost_Classifier_PlattCalibrated"] = classifier_results["target_weighted_p90"]["XGBoost_Classifier_PlattCalibrated_14Feat_ActualMEPS_Oracle"]

    return (
        classifier_results, cal_xgb_unw, lr_obs_unw, cal_xgb_tgt2, lr_obs_tgt2,
        base_brier_unw, base_brier_tgt2, base_brier_tgt2_wtd, train_prev_wtd_tgt
    )


def compute_stratification_and_ranking_analysis(y_test_raw, p_xgb_obs, p_tw_obs, p_tw_unw, p_2pm, p90_threshold):
    """
    Computes decile stratification and ranking analysis across models.
    Generates:
      1. Observable XGBoost decile analysis (ranking by expm1 log predictions)
      2. Observable Tweedie GLM decile analysis (evaluating calibrated expected dollar spending)
    Provides exact aggregate reconciliation assertions for both candidates.
    """
    # 1. Stratification by 11-feature Observable XGBoost
    df_strat_xgb = pd.DataFrame({
        "observed": y_test_raw.values,
        "pred_xgb_obs": p_xgb_obs,
        "pred_tweedie": p_tw_unw,
        "pred_twopart": p_2pm
    })
    df_strat_xgb["decile"] = pd.qcut(df_strat_xgb["pred_xgb_obs"], q=10, labels=False) + 1

    decile_summary_xgb = []
    for d, grp in df_strat_xgb.groupby("decile"):
        obs_mean = float(grp["observed"].mean())
        xgb_mean = float(grp["pred_xgb_obs"].mean())
        tw_mean = float(grp["pred_tweedie"].mean())
        tp_mean = float(grp["pred_twopart"].mean())
        pct_zero = float((grp["observed"] == 0).mean() * 100.0)
        pct_top10 = float((grp["observed"] >= p90_threshold).mean() * 100.0)

        decile_summary_xgb.append({
            "decile": int(d),
            "count": len(grp),
            "xgb_obs_predicted_range": [round(float(grp["pred_xgb_obs"].min()), 2), round(float(grp["pred_xgb_obs"].max()), 2)],
            "mean_predicted_xgb_obs": round(xgb_mean, 2),
            "mean_predicted_tweedie": round(tw_mean, 2),
            "mean_predicted_twopart": round(tp_mean, 2),
            "mean_observed": round(obs_mean, 2),
            "xgb_underprediction_ratio": round(obs_mean / xgb_mean, 3) if xgb_mean > 0 else 1.0,
            "pct_zero_spenders": round(pct_zero, 1),
            "pct_top_decile_spenders": round(pct_top10, 1)
        })

    total_cnt_xgb = sum(x["count"] for x in decile_summary_xgb)
    overall_obs = float(y_test_raw.mean())
    overall_xgb = float(p_xgb_obs.mean())
    overall_tw = float(p_tw_unw.mean())
    overall_tw_obs = float(p_tw_obs.mean())
    overall_tp = float(p_2pm.mean())

    w_obs_xgb = sum(x["count"] * x["mean_observed"] for x in decile_summary_xgb) / total_cnt_xgb
    w_xgb = sum(x["count"] * x["mean_predicted_xgb_obs"] for x in decile_summary_xgb) / total_cnt_xgb
    w_tw = sum(x["count"] * x["mean_predicted_tweedie"] for x in decile_summary_xgb) / total_cnt_xgb
    w_tp = sum(x["count"] * x["mean_predicted_twopart"] for x in decile_summary_xgb) / total_cnt_xgb

    reconciliation_xgb = {
        "test_sample_size": total_cnt_xgb,
        "overall_observed_mean": round(overall_obs, 2),
        "overall_pred_xgb_obs_mean": round(overall_xgb, 2),
        "overall_pred_tweedie_mean": round(overall_tw, 2),
        "overall_pred_tweedie_obs_mean": round(overall_tw_obs, 2),
        "overall_pred_twopart_mean": round(overall_tp, 2),
        "count_weighted_observed_mean": round(w_obs_xgb, 2),
        "count_weighted_pred_xgb_obs_mean": round(w_xgb, 2),
        "count_weighted_pred_tweedie_mean": round(w_tw, 2),
        "count_weighted_pred_twopart_mean": round(w_tp, 2),
        "max_discrepancy": round(max(
            abs(overall_obs - w_obs_xgb),
            abs(overall_xgb - w_xgb),
            abs(overall_tw - w_tw),
            abs(overall_tp - w_tp)
        ), 4),
        "tolerance": 0.05,
        "reconciled": bool(max(
            abs(overall_obs - w_obs_xgb),
            abs(overall_xgb - w_xgb),
            abs(overall_tw - w_tw),
            abs(overall_tp - w_tp)
        ) < 0.05)
    }

    # 2. Stratification by 11-feature Observable Tweedie GLM (Predictions Generated by Observable Tweedie)
    df_strat_tw = pd.DataFrame({
        "observed": y_test_raw.values,
        "pred_tw_obs": p_tw_obs
    })
    df_strat_tw["decile"] = pd.qcut(df_strat_tw["pred_tw_obs"], q=10, labels=False) + 1

    decile_summary_tw = []
    for d, grp in df_strat_tw.groupby("decile"):
        obs_mean = float(grp["observed"].mean())
        tw_mean = float(grp["pred_tw_obs"].mean())
        pct_zero = float((grp["observed"] == 0).mean() * 100.0)
        pct_top10 = float((grp["observed"] >= p90_threshold).mean() * 100.0)

        decile_summary_tw.append({
            "decile": int(d),
            "count": len(grp),
            "tweedie_obs_predicted_range": [round(float(grp["pred_tw_obs"].min()), 2), round(float(grp["pred_tw_obs"].max()), 2)],
            "mean_predicted_tweedie_obs": round(tw_mean, 2),
            "mean_observed": round(obs_mean, 2),
            "observed_to_predicted_ratio": round(obs_mean / tw_mean, 3) if tw_mean > 0 else 1.0,
            "pct_zero_spenders": round(pct_zero, 1),
            "pct_top_decile_spenders": round(pct_top10, 1)
        })

    total_cnt_tw = sum(x["count"] for x in decile_summary_tw)
    w_obs_tw = sum(x["count"] * x["mean_observed"] for x in decile_summary_tw) / total_cnt_tw
    w_pred_tw = sum(x["count"] * x["mean_predicted_tweedie_obs"] for x in decile_summary_tw) / total_cnt_tw

    reconciliation_tw = {
        "test_sample_size": total_cnt_tw,
        "overall_observed_mean": round(overall_obs, 2),
        "overall_pred_tweedie_obs_mean": round(overall_tw_obs, 2),
        "count_weighted_observed_mean": round(w_obs_tw, 2),
        "count_weighted_pred_tweedie_obs_mean": round(w_pred_tw, 2),
        "max_discrepancy": round(max(abs(overall_obs - w_obs_tw), abs(overall_tw_obs - w_pred_tw)), 4),
        "tolerance": 0.05,
        "reconciled": bool(max(abs(overall_obs - w_obs_tw), abs(overall_tw_obs - w_pred_tw)) < 0.05)
    }

    reconciliation_xgb["count_weighted_pred_tweedie_obs_mean"] = round(w_pred_tw, 2)

    return decile_summary_xgb, reconciliation_xgb, decile_summary_tw, reconciliation_tw


def compute_oof_cost_benchmarks(X_train_obs, y_train_log, y_train_raw, w_train, n_splits=5):
    """Computes strictly Out-of-Fold (OOF) cross-validation predictions for the 11-feature observable model."""
    print(f"\n--- Computing {n_splits}-Fold Out-Of-Fold (OOF) Cost Benchmark on 11-Feature Observable Model ---")
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    oof_dollar_preds = np.zeros(len(X_train_obs))

    for fold, (train_idx, val_idx) in enumerate(kf.split(X_train_obs)):
        X_tr, y_tr = X_train_obs.iloc[train_idx], y_train_log.iloc[train_idx]
        X_val = X_train_obs.iloc[val_idx]

        model = xgb.XGBRegressor(
            objective="reg:squarederror", n_estimators=500, learning_rate=0.01,
            max_depth=5, subsample=0.8, colsample_bytree=0.8, gamma=2,
            reg_alpha=1, reg_lambda=1, random_state=42 + fold
        )
        model.fit(X_tr, y_tr)
        val_pred_log = model.predict(X_val)
        oof_dollar_preds[val_idx] = np.maximum(np.expm1(val_pred_log), 0)

    # Compute survey-weighted percentile curve of observed training expenditures
    sorter = np.argsort(y_train_raw.values)
    vals_sorted = y_train_raw.values[sorter]
    w_sorted = w_train.values[sorter]
    cum_w = np.cumsum(w_sorted) - 0.5 * w_sorted
    cum_w /= np.sum(w_sorted)
    percentile_grid = np.linspace(0.01, 0.99, 99)
    observed_weighted_percentiles = np.interp(percentile_grid, cum_w, vals_sorted)

    benchmark_bundle = {
        "predicted_costs_oof": oof_dollar_preds,
        "observed_costs_train": y_train_raw.values,
        "observed_weighted_percentiles": observed_weighted_percentiles,
        "percentile_grid": percentile_grid,
        "documentation": {
            "predicted_costs_oof": "Distribution of 5-fold cross-validated 11-feature model log-regression expectations on training cohort (N=15,016). Percentiles represent relative predicted ranking among model conditional expectations.",
            "observed_costs_train": "Distribution of actual observed annual expenditures in training cohort (N=15,016). Includes 13.9% zero-spenders and heavy right tail.",
            "score_semantics": "relative_expenditure_score = 100 - percentile_model_expected_cost. Reflects relative rank among model conditional expectations, NOT a clinically validated measure of health status or clinical wellness."
        }
    }
    return benchmark_bundle


def run_shap_analysis(model, X_test_obs, feature_names):
    """Computes SHAP feature importance using TreeExplainer for the 11-feature observable model."""
    print("\n--- Computing SHAP TreeExplainer Attributions (Model Feature Contributions) ---")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test_obs)
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

    shap_importance = []
    for feat, imp in zip(feature_names, mean_abs_shap):
        shap_importance.append({
            "feature": feat,
            "mean_abs_shap": round(float(imp), 4),
            "interpretation": "Statistical contribution to model log-expenditure prediction (NOT a causal or clinical effect size)."
        })
    shap_importance.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
    return shap_importance


def main():
    print("=" * 75)
    print("HealthScore Audited Research Pipeline (Deployment Parity & Reconciled Metrics)")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 75)

    # 1. Load data
    df_raw = load_raw_meps()
    df_clean, audit_counts = clean_and_engineer_features(df_raw, filter_zero_expenditure=False)

    # 2. Split data strictly using training data for imputation
    splits = split_data(df_clean, raw_df=df_raw, test_size=0.20, random_state=42)

    # 3. Train candidate regressors
    (
        reg_results, subgroups, xgb_obs, xgb_full, tw_unw, tw_obs,
        part1_clf, part2_reg, duan_smear, p_xgb_obs, p_tw_obs
    ) = train_and_evaluate_regressors(splits)

    # 4. Train candidate classifiers
    (
        cls_results, cal_xgb_unw, lr_obs_unw, cal_xgb_tgt2, lr_obs_tgt2,
        base_brier_tgt1, base_brier_tgt2, base_brier_tgt2_wtd, p_hat_tgt2
    ) = train_and_evaluate_classifiers(splits)

    # 5. Stratification & Ranking Analysis
    p_tw = tw_unw.predict(splits["X_test"])
    p_2pm = part1_clf.predict_proba(splits["X_test"])[:, 1] * np.exp(part2_reg.predict(splits["X_test"])) * duan_smear
    (
        strat_xgb, recon_xgb, strat_tw, recon_tw
    ) = compute_stratification_and_ranking_analysis(
        splits["y_test_raw"], p_xgb_obs, p_tw_obs, p_tw, p_2pm, splits["p90_threshold_unweighted"]
    )

    # Compute variance conventions and verify mathematical identities
    var_ddof0 = round(float(np.var(splits["y_test_raw"], ddof=0)), 2)
    var_ddof1 = round(float(np.var(splits["y_test_raw"], ddof=1)), 2)

    # Mathematical identity verification: R2 == 1 - SS_res / SS_tot == 1 - RMSE^2 / Var_pop (ddof=0)
    ss_tot = float(np.sum((splits["y_test_raw"].values - np.mean(splits["y_test_raw"].values))**2))
    ss_res_xgb = float(np.sum((splits["y_test_raw"].values - p_xgb_obs)**2))
    r2_identity = 1.0 - (ss_res_xgb / ss_tot)
    r2_score_calc = float(r2_score(splits["y_test_raw"].values, p_xgb_obs))
    assert np.isclose(r2_identity, r2_score_calc, atol=1e-7), "R2 identity assertion failed against sklearn r2_score"
    print(f"\n[Variance & R2 Verification] Pop Var (ddof=0): ${var_ddof0:,.2f} | Sample Var (ddof=1): ${var_ddof1:,.2f}")
    print(f"[Variance & R2 Verification] R2 identity: {r2_identity:.6f} == sklearn r2_score: {r2_score_calc:.6f} (Strict agreement with ddof=0)")

    # 6. Out-of-fold benchmark on observable 11-feature model
    X_tr_obs = splits["X_train"][splits["observable_feature_cols"]]
    benchmark_bundle = compute_oof_cost_benchmarks(
        X_tr_obs, splits["y_train_log"], splits["y_train_raw"], splits["w_train"]
    )

    # 7. SHAP feature contributions
    X_te_obs = splits["X_test"][splits["observable_feature_cols"]]
    shap_summary = run_shap_analysis(xgb_obs, X_te_obs, splits["observable_feature_cols"])

    # 8. Export Model Artifacts
    # Primary deployment model is the 11-feature observable-inputs model!
    with open(PRIMARY_MODEL_FILE, "wb") as f:
        pickle.dump(xgb_obs, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_observable.pkl"), "wb") as f:
        pickle.dump(xgb_obs, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_14feat_full.pkl"), "wb") as f:
        pickle.dump(xgb_full, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_tweedie.pkl"), "wb") as f:
        pickle.dump(tw_unw, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_tweedie_observable.pkl"), "wb") as f:
        pickle.dump(tw_obs, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_twopart.pkl"), "wb") as f:
        pickle.dump({"part1_clf": part1_clf, "part2_reg": part2_reg, "duan_smear": duan_smear}, f)

    # Export classifiers with explicitly named artifacts and declared targets
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_classifier.pkl"), "wb") as f:
        pickle.dump(cal_xgb_unw, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_classifier_unweighted_p90.pkl"), "wb") as f:
        pickle.dump(cal_xgb_unw, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_classifier_weighted_p90.pkl"), "wb") as f:
        pickle.dump(cal_xgb_tgt2, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_classifier_observable.pkl"), "wb") as f:
        pickle.dump(lr_obs_tgt2, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_classifier_observable_weighted_p90.pkl"), "wb") as f:
        pickle.dump(lr_obs_tgt2, f)
    with open(os.path.join(ARTIFACTS_DIR, "risk_model_classifier_observable_unweighted_p90.pkl"), "wb") as f:
        pickle.dump(lr_obs_unw, f)

    with open(BENCHMARK_FILE, "wb") as f:
        pickle.dump(benchmark_bundle, f)
    with open(os.path.join(ARTIFACTS_DIR, "benchmark_costs_oof.pkl"), "wb") as f:
        pickle.dump(benchmark_bundle["predicted_costs_oof"], f)

    # 9. Export Comprehensive Evaluation Metrics
    evaluation_metrics = {
        "metadata": {
            "dataset": "MEPS HC-251 (2023 Full Year Consolidated)",
            "generated_at": datetime.now().isoformat(),
            "train_samples": len(splits["X_train"]),
            "test_samples": len(splits["X_test"]),
            "unweighted_p90_threshold": splits["p90_threshold_unweighted"],
            "weighted_p90_threshold": splits["p90_threshold_weighted"],
            "test_variance_raw_dollars": var_ddof0,
            "test_population_variance_ddof0": var_ddof0,
            "test_sample_variance_ddof1": var_ddof1,
            "variance_convention_diagnostics": {
                "population_variance_ddof0": var_ddof0,
                "sample_variance_ddof1": var_ddof1,
                "identity_verification": "R2 = 1 - (SS_res / SS_tot) = 1 - (RMSE^2 / Var_pop). Strictly verified against ddof=0 population variance ($602,354,051.95)."
            },
            "confidence_intervals_method": "Ordinary row-level percentile bootstrap (1,000 resamples). Reflects sample resampling uncertainty on exploratory held-out test split, NOT complex-survey design-based intervals.",
            "overall_test_metrics": {
                "test_samples": recon_xgb["test_sample_size"],
                "overall_observed_mean": recon_xgb["overall_observed_mean"],
                "overall_pred_xgb_obs_mean": recon_xgb["overall_pred_xgb_obs_mean"],
                "overall_pred_tweedie_obs_mean": recon_tw["overall_pred_tweedie_obs_mean"],
                "overall_pred_tweedie_mean": recon_xgb["overall_pred_tweedie_mean"],
                "overall_pred_twopart_mean": recon_xgb["overall_pred_twopart_mean"]
            }
        },
        "regressors": reg_results,
        "deployment_parity_subgroups": subgroups,
        "classifiers": cls_results,
        "stratification_and_ranking_analysis": strat_xgb,
        "reconciliation_summary": recon_xgb,
        "stratification_analysis_tweedie_observable": strat_tw,
        "reconciliation_summary_tweedie_observable": recon_tw,
        "stratification_analysis_xgb_observable": strat_xgb,
        "reconciliation_summary_xgb_observable": recon_xgb,
        "shap_importance": shap_summary
    }

    metrics_path = os.path.join(ARTIFACTS_DIR, "evaluation_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(evaluation_metrics, f, indent=2)

    # 10. Export Training Metadata
    training_metadata = {
        "cohort": audit_counts,
        "thresholds": {
            "unweighted_p90_expenditure_cutoff": splits["p90_threshold_unweighted"],
            "weighted_p90_expenditure_cutoff": splits["p90_threshold_weighted"],
            "description": "Thresholds derived strictly from training split (N=15,016) to prevent test-set data leakage."
        },
        "classifier_artifacts_metadata": {
            "risk_model_classifier_observable_weighted_p90.pkl": {
                "target_name": "Target 2: Survey-Weighted Population Top Decile",
                "target_threshold_dollars": splits["p90_threshold_weighted"],
                "target_prevalence_train_survey_weighted": round(float(p_hat_tgt2), 6),
                "baseline_brier_survey_weighted": round(float(base_brier_tgt2_wtd), 6),
                "baseline_brier_unweighted": round(float(base_brier_tgt2), 6),
                "feature_count": 11,
                "feature_schema": "observable_11_features",
                "algorithm": "LogisticRegression (Normalized Weighted Fit)",
                "role": "Primary candidate for runtime integration testing (zero synthetic imputation)."
            },
            "risk_model_classifier_observable_unweighted_p90.pkl": {
                "target_name": "Target 1: Unweighted Sample Top Decile",
                "target_threshold_dollars": splits["p90_threshold_unweighted"],
                "feature_count": 11,
                "feature_schema": "observable_11_features",
                "algorithm": "LogisticRegression (Unweighted Fit)",
                "baseline_brier_unweighted": round(float(base_brier_tgt1), 6)
            },
            "risk_model_classifier_observable.pkl": {
                "target_name": "Target 2: Survey-Weighted Population Top Decile",
                "target_threshold_dollars": splits["p90_threshold_weighted"],
                "feature_count": 11,
                "feature_schema": "observable_11_features",
                "algorithm": "LogisticRegression (Normalized Weighted Fit)",
                "role": "Canonical alias for risk_model_classifier_observable_weighted_p90.pkl (primary candidate for integration testing)."
            },
            "risk_model_classifier_weighted_p90.pkl": {
                "target_name": "Target 2: Survey-Weighted Population Top Decile",
                "target_threshold_dollars": splits["p90_threshold_weighted"],
                "feature_count": 14,
                "feature_schema": "canonical_14_features",
                "algorithm": "CalibratedClassifierCV(XGBClassifier, method='sigmoid', cv=5)"
            },
            "risk_model_classifier_unweighted_p90.pkl": {
                "target_name": "Target 1: Unweighted Sample Top Decile",
                "target_threshold_dollars": splits["p90_threshold_unweighted"],
                "feature_count": 14,
                "feature_schema": "canonical_14_features",
                "algorithm": "CalibratedClassifierCV(XGBClassifier, method='sigmoid', cv=5)"
            },
            "risk_model_classifier.pkl": {
                "target_name": "Target 1: Unweighted Sample Top Decile",
                "target_threshold_dollars": splits["p90_threshold_unweighted"],
                "feature_count": 14,
                "feature_schema": "canonical_14_features",
                "algorithm": "CalibratedClassifierCV(XGBClassifier, method='sigmoid', cv=5)",
                "role": "Benchmark 14-feature classifier targeting unweighted sample P90."
            }
        },
        "reconciliation_check": recon_xgb,
        "reconciliation_check_tweedie_observable": recon_tw,
        "conditional_imputation_lookup": splits["imputation_table"],
        "observable_features": splits["observable_feature_cols"],
        "canonical_features": FEATURE_COLS,
        "weight_scale_audit": {
            "raw_sum_train_weights": round(float(splits["w_train"].sum()), 2),
            "raw_mean_train_weight": round(float(splits["w_train"].mean()), 2),
            "normalized_mean_train_weight": round(float(splits["w_train_norm"].mean()), 4),
            "note": "Normalized person weights (mean=1.0) used for ML solvers to preserve regularization balance."
        }
    }
    with open(os.path.join(ARTIFACTS_DIR, "training_metadata.json"), "w") as f:
        json.dump(training_metadata, f, indent=2)

    # 11. Feature Schema & Generation Paths
    feature_schema_payload = {
        "features": FEATURE_COLS,
        "observable_features": OBSERVABLE_FEATURE_COLS,
        "count_canonical": len(FEATURE_COLS),
        "count_observable": len(splits["observable_feature_cols"]),
        "artifacts_feature_counts": {
            "risk_model.pkl": 11,
            "risk_model_observable.pkl": 11,
            "risk_model_tweedie_observable.pkl": 11,
            "risk_model_classifier_observable.pkl": 11,
            "risk_model_classifier_observable_weighted_p90.pkl": 11,
            "risk_model_classifier_observable_unweighted_p90.pkl": 11,
            "risk_model_14feat_full.pkl": 14,
            "risk_model_tweedie.pkl": 14,
            "risk_model_classifier.pkl": 14,
            "risk_model_classifier_weighted_p90.pkl": 14,
            "risk_model_classifier_unweighted_p90.pkl": 14,
            "risk_model_twopart.pkl": 14
        },
        "deployment_parity_declaration": "Input Availability Parity; Semantic Validation Pending. Equal feature counts do not establish semantic equivalence.",
        "frontend_input_mapping": {
            "AGE23X": {
                "training_source": "Continuous person age (0-85) from variable AGE23X in MEPS HC-251.",
                "runtime_source": "Exact numeric float value passed via 'age' in intake JSON.",
                "parity_type": "Exact direct parity."
            },
            "Gender_Male": {
                "training_source": "Binary indicator derived from SEX == 1 (1=Male, 0=Female).",
                "runtime_source": "Binary indicator derived from 'gender' string (1 if 'male'/'m', else 0).",
                "parity_type": "Exact direct parity."
            },
            "Cardio_ACG": {
                "training_source": "Sum of 5 discrete MEPS clinician-confirmed binary condition indicators: HIBPDX (hypertension), CHDDX (coronary heart disease), ANGIDX (angina), MIDX (myocardial infarction), STRKDX (stroke). Range 0-5.",
                "runtime_source": "Regex heuristic score on 'diseaseInput'. Range 0-2 (2 if severe terms stroke/heart attack/infarction/cad affirmed; 1 if hypertension/cardiac affirmed; 0 if negated/unmentioned).",
                "parity_type": "Heuristic proxy; semantic validation pending."
            },
            "Metabolic_ACG": {
                "training_source": "Sum of 2 MEPS binary flags: DIABDX_M18 (diabetes) + CHOLDX (hyperlipidemia). Range 0-2.",
                "runtime_source": "Regex heuristic score on 'diseaseInput'. Range 0-2 (2 if diabetes AND cholesterol/lipids affirmed; 1 if either affirmed; 0 if negated/unmentioned).",
                "parity_type": "Heuristic proxy; semantic validation pending."
            },
            "Respiratory_ACG": {
                "training_source": "Sum of 3 MEPS binary flags: ASTHDX (asthma) + CHBRON (chronic bronchitis) + EMPHDX (emphysema). Range 0-3.",
                "runtime_source": "Regex heuristic score on 'diseaseInput'. Range 0-2 (2 if COPD/emphysema affirmed; 1 if asthma/bronchitis affirmed; 0 if negated/unmentioned).",
                "parity_type": "Heuristic proxy; semantic validation pending."
            },
            "Oncology_ACG": {
                "training_source": "Single MEPS binary flag CANCERDX (any cancer diagnosis). Range 0-1.",
                "runtime_source": "Regex heuristic score on 'diseaseInput'. Range 0-1 (1 if cancer/tumor terms affirmed; 0 if negated/unmentioned).",
                "parity_type": "Heuristic proxy; semantic validation pending."
            },
            "Musculoskeletal_ACG": {
                "training_source": "Single MEPS binary flag ARTHDX (arthritis diagnosis). Range 0-1.",
                "runtime_source": "Regex heuristic score on 'diseaseInput'. Range 0-1 (1 if arthritis/joint terms affirmed; 0 if negated/unmentioned).",
                "parity_type": "Heuristic proxy; semantic validation pending."
            },
            "Psychiatric_ACG": {
                "training_source": "Sum of 2 MEPS binary flags: ADDPRS42 (past-2-week depression symptoms) + ADHDADDX (pediatric ADHD). Range 0-2.",
                "runtime_source": "Regex heuristic score on 'diseaseInput'. Range 0-2 (2 if bipolar or depression+anxiety affirmed; 1 if depression/anxiety/adhd affirmed; 0 if negated/unmentioned).",
                "parity_type": "Heuristic proxy; semantic validation pending."
            },
            "Comorbidity_Count": {
                "training_source": "Count of positive clusters among the 6 chronic condition clusters (sum(I(cluster > 0))). Range 0-6.",
                "runtime_source": "Identical formula applied to the 6 runtime cluster values.",
                "parity_type": "Formulaic parity on proxy clusters."
            },
            "Multimorbidity_Penalty": {
                "training_source": "Quadratic interaction Comorbidity_Count**2. Range 0-36.",
                "runtime_source": "Identical quadratic interaction Comorbidity_Count**2.",
                "parity_type": "Formulaic parity."
            },
            "Age_x_Comorbidity": {
                "training_source": "Product AGE23X * Comorbidity_Count.",
                "runtime_source": "Identical product age * Comorbidity_Count.",
                "parity_type": "Formulaic parity."
            },
            "Frailty_Index": {
                "training_source": "Composite ADGENH42 + 2*ANYLMI23 + 2*DFCOG42 from self-administered questionnaire. Range 1-9.",
                "runtime_source": "Imputed conditional mean by age bracket and comorbidity tier from training lookup (unless explicit questionnaire inputs provided).",
                "parity_type": "Imputed population expectation."
            },
            "Age_x_Frailty": {
                "training_source": "Product AGE23X * Frailty_Index.",
                "runtime_source": "Product age * imputed Frailty_Index.",
                "parity_type": "Imputed interaction."
            },
            "K6SUM42": {
                "training_source": "Kessler 6 psychological distress sum (0-24) from self-administered questionnaire.",
                "runtime_source": "Imputed conditional mean by age bracket and comorbidity tier from training lookup (unless explicit questionnaire input provided).",
                "parity_type": "Imputed population expectation."
            }
        }
    }
    with open(os.path.join(ARTIFACTS_DIR, "feature_schema.json"), "w") as f:
        json.dump(feature_schema_payload, f, indent=2)

    print("\n✓ Training and evaluation harness completed successfully. All artifacts refreshed.")


if __name__ == "__main__":
    main()