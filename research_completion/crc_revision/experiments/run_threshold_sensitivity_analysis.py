"""
HealthScore — Phase 1 Classification Probability Threshold Sensitivity & Diagnostic Analysis
===========================================================================================
Reproducible experimental script evaluating the frozen 11-feature Observable Logistic Regression
serving candidate (`risk_model_classifier_observable_weighted_p90.pkl`) across probability
decision thresholds without model retraining or test-set leakage.

Implements:
  1. Exact baseline verification at threshold tau = 0.10 on held-out test split (N=3,755).
  2. Leak-free threshold comparison & operating-point selection on Training 5-Fold Out-of-Fold (OOF)
     validation predictions (both StratifiedKFold and Household-Grouped GroupKFold by DUID, N=15,016).
  3. Evaluation across required thresholds (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
     plus intermediate thresholds (0.05, 0.15, 0.25) on OOF validation, held-out test, and external
     2024 cohorts (HC-256 Full, Panel 28 overlap, Panel 29 unseen, and HC-257 prospective).
  4. Both unweighted (raw observation counts/proportions) and survey-weighted metrics at every cutoff.
  5. Six-part diagnostic investigation of low precision at tau = 0.10:
     (A) Threshold sensitivity, (B) Class imbalance & Bayes bound, (C) Model discrimination,
     (D) Probability calibration & bin prevalence, (E) Multi-split/multi-cohort overfitting audit,
     and (F) Discrete 11-feature granularity & within-profile expenditure heterogeneity.
  6. Generation of >=600 DPI PNG and vector PDF figures and machine-readable CSV/JSON artifacts.
"""

import os
import sys
import json
import pickle
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import StratifiedKFold, GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss, log_loss,
    confusion_matrix, roc_curve, precision_recall_curve
)

# Resolve paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CRC_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(CRC_DIR))
sys.path.insert(0, os.path.join(REPO_ROOT, "ml_model"))

from data_pipeline import (
    load_raw_meps, clean_and_engineer_features, split_data,
    OBSERVABLE_FEATURE_COLS, FEATURE_COLS
)

RESULTS_DIR = os.path.join(CRC_DIR, "results")
FIGURES_DIR = os.path.join(CRC_DIR, "figures")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
PRIMARY_THRESHOLDS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def evaluate_threshold_grid(y_true, y_prob, weights, thresholds):
    """
    Computes complete unweighted and survey-weighted classification metrics across a grid of
    probability decision thresholds for fixed predicted probabilities y_prob.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    weights = np.asarray(weights, dtype=float)

    n_total = int(len(y_true))
    pos_total = int(np.sum(y_true == 1))
    neg_total = int(np.sum(y_true == 0))
    prev_unw = float(pos_total / n_total)

    w_total = float(np.sum(weights))
    w_pos_total = float(np.sum(weights[y_true == 1]))
    w_neg_total = float(np.sum(weights[y_true == 0]))
    prev_wtd = float(w_pos_total / w_total)

    rows = []
    for tau in thresholds:
        y_pred = (y_prob >= tau).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        tn, fp, fn, tp = int(tn), int(fp), int(fn), int(tp)
        flagged = tp + fp
        unflagged = tn + fn

        # Unweighted metrics
        prec_u = float(tp / flagged) if flagged > 0 else 0.0
        rec_u = float(tp / pos_total) if pos_total > 0 else 0.0
        f1_u = float(2.0 * prec_u * rec_u / (prec_u + rec_u)) if (prec_u + rec_u) > 0 else 0.0
        spec_u = float(tn / neg_total) if neg_total > 0 else 0.0
        npv_u = float(tn / unflagged) if unflagged > 0 else 0.0
        bal_acc_u = float(0.5 * (rec_u + spec_u))
        youden_j_u = float(rec_u + spec_u - 1.0)
        fpr_u = float(fp / neg_total) if neg_total > 0 else 0.0
        fnr_u = float(fn / pos_total) if pos_total > 0 else 0.0
        flag_prop_u = float(flagged / n_total)
        enrich_u = float(prec_u / prev_unw) if prev_unw > 0 else 0.0
        fp_per_tp_u = float(fp / tp) if tp > 0 else None

        # Theoretical Oracle Precision Bound at this exact flagged volume: min(pos_total, flagged) / flagged
        oracle_max_prec_u = float(min(pos_total, flagged) / flagged) if flagged > 0 else 0.0

        # Survey-weighted metrics
        w_tp = float(np.sum(weights[(y_true == 1) & (y_pred == 1)]))
        w_fp = float(np.sum(weights[(y_true == 0) & (y_pred == 1)]))
        w_tn = float(np.sum(weights[(y_true == 0) & (y_pred == 0)]))
        w_fn = float(np.sum(weights[(y_true == 1) & (y_pred == 0)]))
        w_flagged = w_tp + w_fp
        w_unflagged = w_tn + w_fn

        prec_w = float(w_tp / w_flagged) if w_flagged > 0 else 0.0
        rec_w = float(w_tp / w_pos_total) if w_pos_total > 0 else 0.0
        f1_w = float(2.0 * prec_w * rec_w / (prec_w + rec_w)) if (prec_w + rec_w) > 0 else 0.0
        spec_w = float(w_tn / w_neg_total) if w_neg_total > 0 else 0.0
        npv_w = float(w_tn / w_unflagged) if w_unflagged > 0 else 0.0
        bal_acc_w = float(0.5 * (rec_w + spec_w))
        youden_j_w = float(rec_w + spec_w - 1.0)
        fpr_w = float(w_fp / w_neg_total) if w_neg_total > 0 else 0.0
        fnr_w = float(w_fn / w_pos_total) if w_pos_total > 0 else 0.0
        flag_prop_w = float(w_flagged / w_total)
        enrich_w = float(prec_w / prev_wtd) if prev_wtd > 0 else 0.0

        rows.append({
            "threshold": round(float(tau), 2),
            "is_primary_grid": bool(round(float(tau), 2) in PRIMARY_THRESHOLDS),
            "n_total": n_total,
            "actual_positives": pos_total,
            "actual_negatives": neg_total,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "flagged_count": flagged,
            "flagged_proportion_unweighted": round(flag_prop_u, 4),
            "flagged_pct_unweighted": round(flag_prop_u * 100.0, 2),
            "precision_unweighted": round(prec_u, 4),
            "recall_unweighted": round(rec_u, 4),
            "f1_unweighted": round(f1_u, 4),
            "specificity_unweighted": round(spec_u, 4),
            "npv_unweighted": round(npv_u, 4),
            "balanced_accuracy_unweighted": round(bal_acc_u, 4),
            "youden_j_unweighted": round(youden_j_u, 4),
            "fpr_unweighted": round(fpr_u, 4),
            "fnr_unweighted": round(fnr_u, 4),
            "enrichment_ratio_unweighted": round(enrich_u, 2),
            "fp_per_tp_unweighted": round(fp_per_tp_u, 2) if fp_per_tp_u is not None else None,
            "oracle_max_precision_at_volume": round(oracle_max_prec_u, 4),
            "flagged_proportion_weighted": round(flag_prop_w, 4),
            "flagged_pct_weighted": round(flag_prop_w * 100.0, 2),
            "precision_weighted": round(prec_w, 4),
            "recall_weighted": round(rec_w, 4),
            "f1_weighted": round(f1_w, 4),
            "specificity_weighted": round(spec_w, 4),
            "npv_weighted": round(npv_w, 4),
            "balanced_accuracy_weighted": round(bal_acc_w, 4),
            "youden_j_weighted": round(youden_j_w, 4),
            "fpr_weighted": round(fpr_w, 4),
            "fnr_weighted": round(fnr_w, 4),
            "enrichment_ratio_weighted": round(enrich_w, 2),
            "w_tp_share": round(w_tp / w_total, 4),
            "w_fp_share": round(w_fp / w_total, 4),
            "w_tn_share": round(w_tn / w_total, 4),
            "w_fn_share": round(w_fn / w_total, 4)
        })
    return rows


def compute_threshold_independent_summary(y_true, y_prob, weights, train_prev_unw, train_prev_wtd):
    """Computes threshold-independent ranking and probability accuracy metrics."""
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    weights = np.asarray(weights, dtype=float)
    w_norm = weights * (len(weights) / np.sum(weights))

    roc_u = float(roc_auc_score(y_true, y_prob))
    roc_w = float(roc_auc_score(y_true, y_prob, sample_weight=w_norm))
    pr_u = float(average_precision_score(y_true, y_prob))
    pr_w = float(average_precision_score(y_true, y_prob, sample_weight=w_norm))
    ll_u = float(log_loss(y_true, y_prob))
    ll_w = float(log_loss(y_true, y_prob, sample_weight=w_norm))

    brier_u = float(brier_score_loss(y_true, y_prob))
    base_brier_u = float(np.mean((y_true - train_prev_unw) ** 2))
    bss_u = float(1.0 - (brier_u / base_brier_u))

    brier_w = float(np.average((y_true - y_prob) ** 2, weights=w_norm))
    base_brier_w = float(np.average((y_true - train_prev_wtd) ** 2, weights=w_norm))
    bss_w = float(1.0 - (brier_w / base_brier_w))

    return {
        "n_samples": int(len(y_true)),
        "positive_count": int(np.sum(y_true == 1)),
        "prevalence_unweighted": round(float(np.mean(y_true)), 4),
        "prevalence_weighted": round(float(np.average(y_true, weights=weights)), 4),
        "mean_predicted_prob_unweighted": round(float(np.mean(y_prob)), 4),
        "mean_predicted_prob_weighted": round(float(np.average(y_prob, weights=weights)), 4),
        "min_predicted_prob": round(float(np.min(y_prob)), 4),
        "median_predicted_prob": round(float(np.median(y_prob)), 4),
        "p90_predicted_prob": round(float(np.percentile(y_prob, 90)), 4),
        "p99_predicted_prob": round(float(np.percentile(y_prob, 99)), 4),
        "max_predicted_prob": round(float(np.max(y_prob)), 4),
        "roc_auc_unweighted": round(roc_u, 4),
        "roc_auc_weighted": round(roc_w, 4),
        "pr_auc_unweighted": round(pr_u, 4),
        "pr_auc_weighted": round(pr_w, 4),
        "log_loss_unweighted": round(ll_u, 4),
        "log_loss_weighted": round(ll_w, 4),
        "brier_unweighted": round(brier_u, 4),
        "baseline_brier_unweighted": round(base_brier_u, 4),
        "bss_unweighted": round(bss_u, 4),
        "brier_weighted": round(brier_w, 4),
        "baseline_brier_weighted": round(base_brier_w, 4),
        "bss_weighted": round(bss_w, 4)
    }


def prepare_external_hc256():
    """Loads and harmonizes MEPS HC-256 (2024 Full-Year Consolidated) with exact Phase 1 formulas."""
    path = os.path.join(REPO_ROOT, "ml_model", "validation", "hc256", "data", "h256.dta")
    df = pd.read_stata(path, convert_categoricals=False)
    df = df[df["AGE24X"] >= 0].copy()
    df["AGE23X"] = df["AGE24X"]
    df["Gender_Male"] = (df["SEX"] == 1).astype(int)
    dx_cols = [
        "HIBPDX", "CHDDX", "MIDX", "STRKDX", "DIABDX_M18", "CHOLDX",
        "ASTHDX", "EMPHDX", "CHBRON31", "CANCERDX", "ARTHDX", "JTPAIN31_M18", "ADHDADDX"
    ]
    for col in dx_cols:
        df[col] = (df[col] == 1).astype(int)
    df["ADDPRS42"] = df["ADDPRS42"].apply(lambda x: 1 if x in [1, 2, 3] else 0)
    df["Cardio_ACG"] = df["HIBPDX"] + df["CHDDX"] + df["MIDX"] + df["STRKDX"]
    df["Metabolic_ACG"] = df["DIABDX_M18"] + df["CHOLDX"]
    df["Respiratory_ACG"] = df["ASTHDX"] + df["EMPHDX"] + df["CHBRON31"]
    df["Oncology_ACG"] = df["CANCERDX"]
    df["Musculoskeletal_ACG"] = df["ARTHDX"] + df["JTPAIN31_M18"]
    df["Psychiatric_ACG"] = df["ADDPRS42"] + df["ADHDADDX"]
    clusters = [
        "Cardio_ACG", "Metabolic_ACG", "Respiratory_ACG",
        "Oncology_ACG", "Musculoskeletal_ACG", "Psychiatric_ACG"
    ]
    df["Comorbidity_Count"] = (df[clusters] > 0).sum(axis=1)
    df["Multimorbidity_Penalty"] = df["Comorbidity_Count"] ** 2
    df["Age_x_Comorbidity"] = df["AGE23X"] * df["Comorbidity_Count"]
    return df


def prepare_prospective_hc257():
    """Loads and harmonizes MEPS HC-257 (Panel 28 Longitudinal 2023->2024) with exact Phase 1 formulas."""
    path = os.path.join(REPO_ROOT, "ml_model", "validation", "hc257", "data", "h257.dta")
    df = pd.read_stata(path, convert_categoricals=False)
    df = df[(df["YEARIND"] == 1) & (df["AGEY1X"] >= 0)].copy()
    df["AGE23X"] = df["AGEY1X"]
    df["Gender_Male"] = (df["SEX"] == 1).astype(int)
    map_y1 = {
        "HIBPDX": "HIBPDXY1", "CHDDX": "CHDDXY1", "MIDX": "MIDXY1", "STRKDX": "STRKDXY1",
        "DIABDX_M18": "DIABDXY1_M18", "CHOLDX": "CHOLDXY1", "ASTHDX": "ASTHDXY1",
        "EMPHDX": "EMPHDXY1", "CHBRON31": "CHBRON1", "CANCERDX": "CANCERY1",
        "ARTHDX": "ARTHDXY1", "JTPAIN31_M18": "JTPAIN1_M18", "ADHDADDX": "ADHDADY1"
    }
    for clean_col, raw_col in map_y1.items():
        df[clean_col] = (df[raw_col] == 1).astype(int)
    df["ADDPRS42"] = df["ADDPRS2"].apply(lambda x: 1 if x in [1, 2, 3] else 0)
    df["Cardio_ACG"] = df["HIBPDX"] + df["CHDDX"] + df["MIDX"] + df["STRKDX"]
    df["Metabolic_ACG"] = df["DIABDX_M18"] + df["CHOLDX"]
    df["Respiratory_ACG"] = df["ASTHDX"] + df["EMPHDX"] + df["CHBRON31"]
    df["Oncology_ACG"] = df["CANCERDX"]
    df["Musculoskeletal_ACG"] = df["ARTHDX"] + df["JTPAIN31_M18"]
    df["Psychiatric_ACG"] = df["ADDPRS42"] + df["ADHDADDX"]
    clusters = [
        "Cardio_ACG", "Metabolic_ACG", "Respiratory_ACG",
        "Oncology_ACG", "Musculoskeletal_ACG", "Psychiatric_ACG"
    ]
    df["Comorbidity_Count"] = (df[clusters] > 0).sum(axis=1)
    df["Multimorbidity_Penalty"] = df["Comorbidity_Count"] ** 2
    df["Age_x_Comorbidity"] = df["AGE23X"] * df["Comorbidity_Count"]
    return df


def main():
    print("=" * 85)
    print("PHASE 1: PROBABILITY THRESHOLD SENSITIVITY & DIAGNOSTIC ANALYSIS")
    print("=" * 85)

    # 1. Load HC-251 and splits
    h251_path = os.path.join(REPO_ROOT, "ml_model", "h251.dta")
    df_raw = load_raw_meps(h251_path)
    h251_meta = pd.read_stata(
        h251_path, columns=["DUPERSID", "DUID", "PANEL", "AGE23X"], convert_categoricals=False
    )
    h251_meta = h251_meta[h251_meta["AGE23X"] >= 0]

    df_clean, audit = clean_and_engineer_features(df_raw, filter_zero_expenditure=False)
    splits = split_data(df_clean, raw_df=df_raw, test_size=0.20, random_state=42)

    X_train = splits["X_train"][OBSERVABLE_FEATURE_COLS]
    X_test = splits["X_test"][OBSERVABLE_FEATURE_COLS]
    y_train = splits["y_train_cls_wtd"].values
    y_test = splits["y_test_cls_wtd"].values
    y_train_raw = splits["y_train_raw"].values
    y_test_raw = splits["y_test_raw"].values
    w_train = splits["w_train"].values
    w_test = splits["w_test"].values
    w_train_norm = splits["w_train_norm"].values
    w_test_norm = splits["w_test_norm"].values
    p90_wtd_cutoff = float(splits["p90_threshold_weighted"])

    train_prev_unw = float(np.mean(y_train))
    train_prev_wtd = float(np.average(y_train, weights=w_train))

    duid_train = h251_meta.loc[splits["X_train"].index, "DUID"].values
    duid_test = h251_meta.loc[splits["X_test"].index, "DUID"].values
    dupers_train = set(h251_meta.loc[splits["X_train"].index, "DUPERSID"])
    dupers_test = set(h251_meta.loc[splits["X_test"].index, "DUPERSID"])

    # 2. Load frozen serving classifier
    clf_path = os.path.join(
        REPO_ROOT, "ml_model", "artifacts", "risk_model_classifier_observable_weighted_p90.pkl"
    )
    clf_sha = sha256_file(clf_path)
    with open(clf_path, "rb") as f:
        frozen_clf = pickle.load(f)

    prob_train_in_sample = frozen_clf.predict_proba(X_train)[:, 1]
    prob_test = frozen_clf.predict_proba(X_test)[:, 1]

    # 3. Leak-free 5-Fold Out-of-Fold (OOF) Validation on Training Split (Stratified & Household-Grouped)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof_prob_stratified = np.zeros(len(X_train))
    fold_metrics_stratified = []

    for fold_idx, (tr_i, val_i) in enumerate(skf.split(X_train, y_train)):
        m = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=42)
        m.fit(X_train.iloc[tr_i], y_train[tr_i], sample_weight=w_train_norm[tr_i])
        preds = m.predict_proba(X_train.iloc[val_i])[:, 1]
        oof_prob_stratified[val_i] = preds
        yt_f = y_train[val_i]
        wt_f = w_train_norm[val_i]
        pred10 = (preds >= 0.10).astype(int)
        pred20 = (preds >= 0.20).astype(int)
        tn10, fp10, fn10, tp10 = confusion_matrix(yt_f, pred10, labels=[0, 1]).ravel()
        tn20, fp20, fn20, tp20 = confusion_matrix(yt_f, pred20, labels=[0, 1]).ravel()
        fold_metrics_stratified.append({
            "fold": fold_idx + 1,
            "n_val": int(len(val_i)),
            "roc_auc": round(float(roc_auc_score(yt_f, preds)), 4),
            "pr_auc": round(float(average_precision_score(yt_f, preds)), 4),
            "log_loss": round(float(log_loss(yt_f, preds)), 4),
            "brier_unweighted": round(float(brier_score_loss(yt_f, preds)), 4),
            "brier_weighted": round(float(np.average((yt_f - preds) ** 2, weights=wt_f)), 4),
            "prec_at_010": round(float(tp10 / (tp10 + fp10)), 4),
            "rec_at_010": round(float(tp10 / (tp10 + fn10)), 4),
            "f1_at_010": round(float(2 * tp10 / (2 * tp10 + fp10 + fn10)), 4),
            "prec_at_020": round(float(tp20 / (tp20 + fp20)), 4),
            "rec_at_020": round(float(tp20 / (tp20 + fn20)), 4),
            "f1_at_020": round(float(2 * tp20 / (2 * tp20 + fp20 + fn20)), 4)
        })

    gkf = GroupKFold(n_splits=5)
    oof_prob_household = np.zeros(len(X_train))
    fold_metrics_household = []
    for fold_idx, (tr_i, val_i) in enumerate(gkf.split(X_train, y_train, groups=duid_train)):
        m = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=42)
        m.fit(X_train.iloc[tr_i], y_train[tr_i], sample_weight=w_train_norm[tr_i])
        preds = m.predict_proba(X_train.iloc[val_i])[:, 1]
        oof_prob_household[val_i] = preds
        yt_f = y_train[val_i]
        wt_f = w_train_norm[val_i]
        fold_metrics_household.append({
            "fold": fold_idx + 1,
            "n_val": int(len(val_i)),
            "roc_auc": round(float(roc_auc_score(yt_f, preds)), 4),
            "pr_auc": round(float(average_precision_score(yt_f, preds)), 4),
            "log_loss": round(float(log_loss(yt_f, preds)), 4),
            "brier_unweighted": round(float(brier_score_loss(yt_f, preds)), 4),
            "brier_weighted": round(float(np.average((yt_f - preds) ** 2, weights=wt_f)), 4)
        })

    # 4. External datasets (HC-256 and HC-257)
    df_256 = prepare_external_hc256()
    y_256 = (df_256["TOTEXP24"] >= p90_wtd_cutoff).astype(int).values
    w_256 = df_256["PERWT24F"].values
    prob_256 = frozen_clf.predict_proba(df_256[OBSERVABLE_FEATURE_COLS])[:, 1]
    mask_p28 = (df_256["PANEL"] == 28).values
    mask_p29 = (df_256["PANEL"] == 29).values

    df_257 = prepare_prospective_hc257()
    y_257 = (df_257["TOTEXPY2"] >= p90_wtd_cutoff).astype(int).values
    w_257 = df_257["LONGWT"].values
    prob_257 = frozen_clf.predict_proba(df_257[OBSERVABLE_FEATURE_COLS])[:, 1]

    # 5. Evaluate threshold grids
    grid_val_oof = evaluate_threshold_grid(y_train, oof_prob_stratified, w_train, THRESHOLDS)
    grid_val_hh_oof = evaluate_threshold_grid(y_train, oof_prob_household, w_train, THRESHOLDS)
    grid_test = evaluate_threshold_grid(y_test, prob_test, w_test, THRESHOLDS)
    grid_256_full = evaluate_threshold_grid(y_256, prob_256, w_256, THRESHOLDS)
    grid_256_p29 = evaluate_threshold_grid(y_256[mask_p29], prob_256[mask_p29], w_256[mask_p29], THRESHOLDS)
    grid_257 = evaluate_threshold_grid(y_257, prob_257, w_257, THRESHOLDS)

    # Save CSV tables
    pd.DataFrame(grid_val_oof).to_csv(
        os.path.join(RESULTS_DIR, "threshold_comparison_validation_oof.csv"), index=False
    )
    pd.DataFrame(grid_val_hh_oof).to_csv(
        os.path.join(RESULTS_DIR, "threshold_comparison_household_oof.csv"), index=False
    )
    pd.DataFrame(grid_test).to_csv(
        os.path.join(RESULTS_DIR, "threshold_comparison_test.csv"), index=False
    )
    pd.DataFrame(grid_256_p29).to_csv(
        os.path.join(RESULTS_DIR, "threshold_comparison_external_hc256_panel29.csv"), index=False
    )

    # 6. Fine-grained threshold optimization strictly on 5-Fold OOF Validation (step 0.01)
    fine_taus = np.round(np.arange(0.05, 0.76, 0.01), 2)
    fine_val_rows = evaluate_threshold_grid(y_train, oof_prob_stratified, w_train, fine_taus)
    best_bal_acc_val = max(fine_val_rows, key=lambda r: r["balanced_accuracy_unweighted"])
    best_f1_unw_val = max(fine_val_rows, key=lambda r: r["f1_unweighted"])
    best_f1_wtd_val = max(fine_val_rows, key=lambda r: r["f1_weighted"])
    breakeven_val = min(
        [r for r in fine_val_rows if r["flagged_count"] > 0],
        key=lambda r: abs(r["precision_unweighted"] - r["recall_unweighted"])
    )

    # Primary grid optima on OOF Validation
    prim_val_rows = [r for r in grid_val_oof if r["is_primary_grid"]]
    best_prim_bal_acc = max(prim_val_rows, key=lambda r: r["balanced_accuracy_unweighted"])
    best_prim_f1_unw = max(prim_val_rows, key=lambda r: r["f1_unweighted"])
    best_prim_f1_wtd = max(prim_val_rows, key=lambda r: r["f1_weighted"])

    # 7. Probability calibration & bin prevalence analysis on Held-Out Test & OOF Validation
    bin_edges = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
    cal_bins_test = []
    for i in range(len(bin_edges) - 1):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == len(bin_edges) - 2:
            mask_b = (prob_test >= lo) & (prob_test <= hi)
        else:
            mask_b = (prob_test >= lo) & (prob_test < hi)
        cnt = int(np.sum(mask_b))
        pos_b = int(np.sum(y_test[mask_b])) if cnt > 0 else 0
        mean_p = float(np.mean(prob_test[mask_b])) if cnt > 0 else None
        obs_rate_u = float(pos_b / cnt) if cnt > 0 else None
        obs_rate_w = float(np.average(y_test[mask_b], weights=w_test[mask_b])) if cnt > 0 else None
        cal_bins_test.append({
            "bin_range": f"[{lo:.2f}, {hi:.2f})" if i < len(bin_edges) - 2 else f"[{lo:.2f}, {hi:.2f}]",
            "n_patients": cnt,
            "pct_of_test_cohort": round(cnt / len(y_test) * 100.0, 2),
            "observed_high_cost_count": pos_b,
            "mean_predicted_prob": round(mean_p, 4) if mean_p is not None else None,
            "observed_event_rate_unweighted": round(obs_rate_u, 4) if obs_rate_u is not None else None,
            "observed_event_rate_weighted": round(obs_rate_w, 4) if obs_rate_w is not None else None
        })

    # 8. Overfitting & Generalization Audit Table across all splits and releases
    overfitting_audit = {
        "HC251_Train_InSample": compute_threshold_independent_summary(
            y_train, prob_train_in_sample, w_train, train_prev_unw, train_prev_wtd
        ),
        "HC251_5Fold_Stratified_OOF_Val": compute_threshold_independent_summary(
            y_train, oof_prob_stratified, w_train, train_prev_unw, train_prev_wtd
        ),
        "HC251_5Fold_HouseholdGroup_OOF_Val": compute_threshold_independent_summary(
            y_train, oof_prob_household, w_train, train_prev_unw, train_prev_wtd
        ),
        "HC251_HeldOut_Test": compute_threshold_independent_summary(
            y_test, prob_test, w_test, train_prev_unw, train_prev_wtd
        ),
        "HC256_2024_Full": compute_threshold_independent_summary(
            y_256, prob_256, w_256, train_prev_unw, train_prev_wtd
        ),
        "HC256_2024_Panel28_Overlap": compute_threshold_independent_summary(
            y_256[mask_p28], prob_256[mask_p28], w_256[mask_p28], train_prev_unw, train_prev_wtd
        ),
        "HC256_2024_Panel29_Unseen": compute_threshold_independent_summary(
            y_256[mask_p29], prob_256[mask_p29], w_256[mask_p29], train_prev_unw, train_prev_wtd
        ),
        "HC257_Panel28_Prospective_Y2": compute_threshold_independent_summary(
            y_257, prob_257, w_257, train_prev_unw, train_prev_wtd
        ),
        "stratified_5fold_summary": {
            "roc_auc_mean": round(float(np.mean([f["roc_auc"] for f in fold_metrics_stratified])), 4),
            "roc_auc_std": round(float(np.std([f["roc_auc"] for f in fold_metrics_stratified])), 4),
            "pr_auc_mean": round(float(np.mean([f["pr_auc"] for f in fold_metrics_stratified])), 4),
            "pr_auc_std": round(float(np.std([f["pr_auc"] for f in fold_metrics_stratified])), 4),
            "log_loss_mean": round(float(np.mean([f["log_loss"] for f in fold_metrics_stratified])), 4),
            "log_loss_std": round(float(np.std([f["log_loss"] for f in fold_metrics_stratified])), 4),
            "brier_unw_mean": round(float(np.mean([f["brier_unweighted"] for f in fold_metrics_stratified])), 4),
            "brier_unw_std": round(float(np.std([f["brier_unweighted"] for f in fold_metrics_stratified])), 4),
            "folds": fold_metrics_stratified
        },
        "household_group_5fold_summary": {
            "roc_auc_mean": round(float(np.mean([f["roc_auc"] for f in fold_metrics_household])), 4),
            "roc_auc_std": round(float(np.std([f["roc_auc"] for f in fold_metrics_household])), 4),
            "pr_auc_mean": round(float(np.mean([f["pr_auc"] for f in fold_metrics_household])), 4),
            "pr_auc_std": round(float(np.std([f["pr_auc"] for f in fold_metrics_household])), 4),
            "folds": fold_metrics_household
        }
    }

    # 9. Participant & Household Overlap Audit
    dupers_256 = set(df_256["DUPERSID"])
    dupers_256_p29 = set(df_256.loc[mask_p29, "DUPERSID"])
    dupers_257 = set(df_257["DUPERSID"])
    duid_train_set = set(duid_train)
    duid_test_set = set(duid_test)

    overlap_audit = {
        "hc251_total_eligible": int(len(df_clean)),
        "hc251_unique_dupersid": int(h251_meta["DUPERSID"].nunique()),
        "hc251_unique_duid_households": int(h251_meta["DUID"].nunique()),
        "hc251_train_n": int(len(X_train)),
        "hc251_test_n": int(len(X_test)),
        "hc251_train_test_dupersid_overlap": int(len(dupers_train.intersection(dupers_test))),
        "hc251_train_test_shared_households_duid": int(len(duid_train_set.intersection(duid_test_set))),
        "hc251_test_rows_sharing_train_household": int(np.sum(np.isin(duid_test, list(duid_train_set)))),
        "hc251_test_pct_sharing_train_household": round(
            float(np.mean(np.isin(duid_test, list(duid_train_set))) * 100.0), 2
        ),
        "hc256_total_eligible": int(len(df_256)),
        "hc256_panel28_n": int(np.sum(mask_p28)),
        "hc256_panel29_n": int(np.sum(mask_p29)),
        "hc256_dupersid_overlap_with_hc251_total": int(len(dupers_256.intersection(dupers_train.union(dupers_test)))),
        "hc256_dupersid_overlap_with_hc251_train": int(len(dupers_256.intersection(dupers_train))),
        "hc256_dupersid_overlap_with_hc251_test": int(len(dupers_256.intersection(dupers_test))),
        "hc256_panel29_dupersid_overlap_with_hc251": int(
            len(dupers_256_p29.intersection(dupers_train.union(dupers_test)))
        ),
        "hc257_total_eligible": int(len(df_257)),
        "hc257_dupersid_overlap_with_hc251_total": int(len(dupers_257.intersection(dupers_train.union(dupers_test)))),
        "hc257_dupersid_overlap_with_hc251_train": int(len(dupers_257.intersection(dupers_train))),
        "hc257_dupersid_overlap_with_hc251_test": int(len(dupers_257.intersection(dupers_test)))
    }

    # 10. Feature-Space Granularity & Comorbidity Stratum Analysis
    comorb_strata = []
    for c_label, c_mask in [
        ("0 Comorbidities", (X_test["Comorbidity_Count"] == 0).values),
        ("1 Comorbidity", (X_test["Comorbidity_Count"] == 1).values),
        ("2 Comorbidities", (X_test["Comorbidity_Count"] == 2).values),
        ("3+ Comorbidities", (X_test["Comorbidity_Count"] >= 3).values)
    ]:
        n_c = int(np.sum(c_mask))
        pos_c = int(np.sum(y_test[c_mask]))
        comorb_strata.append({
            "stratum": c_label,
            "n_test": n_c,
            "pct_of_test": round(n_c / len(y_test) * 100.0, 2),
            "high_cost_count": pos_c,
            "share_of_all_high_cost_pct": round(pos_c / np.sum(y_test) * 100.0, 2),
            "observed_high_cost_prevalence_pct": round(pos_c / n_c * 100.0, 2),
            "mean_predicted_prob": round(float(np.mean(prob_test[c_mask])), 4),
            "mean_observed_expenditure_usd": round(float(np.mean(y_test_raw[c_mask])), 2)
        })

    # Model coefficients for transparent reporting
    coef_table = [
        {"feature": col, "coefficient": round(float(coef), 6), "odds_ratio_per_unit": round(float(np.exp(coef)), 4)}
        for col, coef in zip(OBSERVABLE_FEATURE_COLS, frozen_clf.coef_[0])
    ]

    full_registry = {
        "model_provenance": {
            "artifact_path": "ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl",
            "artifact_sha256": clf_sha,
            "estimator": "LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=42)",
            "intercept": round(float(frozen_clf.intercept_[0]), 6),
            "coefficients": coef_table,
            "target_definition": f"Survey-Weighted P90 (TOTEXP23 >= ${p90_wtd_cutoff:,.2f})"
        },
        "threshold_selection_validation_oof": {
            "primary_grid_max_balanced_accuracy": best_prim_bal_acc,
            "primary_grid_max_f1_unweighted": best_prim_f1_unw,
            "primary_grid_max_f1_weighted": best_prim_f1_wtd,
            "fine_grid_max_balanced_accuracy": best_bal_acc_val,
            "fine_grid_max_f1_unweighted": best_f1_unw_val,
            "fine_grid_max_f1_weighted": best_f1_wtd_val,
            "fine_grid_precision_recall_breakeven": breakeven_val
        },
        "threshold_grids": {
            "validation_5fold_stratified_oof": grid_val_oof,
            "validation_5fold_household_oof": grid_val_hh_oof,
            "held_out_test": grid_test,
            "external_hc256_full": grid_256_full,
            "external_hc256_panel29_unseen": grid_256_p29,
            "prospective_hc257_panel28": grid_257
        },
        "probability_calibration_bins_test": cal_bins_test,
        "overfitting_and_generalization_audit": overfitting_audit,
        "participant_and_household_overlap_audit": overlap_audit,
        "comorbidity_stratum_analysis_test": comorb_strata
    }

    with open(os.path.join(RESULTS_DIR, "threshold_analysis_complete_registry.json"), "w") as f:
        json.dump(full_registry, f, indent=2)

    print("✓ Saved CSV tables and threshold_analysis_complete_registry.json")

    # =========================================================================
    # GENERATE PUBLICATION-QUALITY FIGURES (>=600 DPI PNG + VECTOR PDF)
    # =========================================================================
    generate_all_threshold_figures(
        grid_val_oof, grid_test, fine_val_rows,
        y_train, oof_prob_stratified, y_test, prob_test,
        cal_bins_test, overfitting_audit
    )


def generate_all_threshold_figures(
    grid_val_oof, grid_test, fine_val_rows,
    y_train, oof_prob_stratified, y_test, prob_test,
    cal_bins_test, overfitting_audit
):
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]

    taus = [r["threshold"] for r in grid_test]
    prec_t = [r["precision_unweighted"] for r in grid_test]
    rec_t = [r["recall_unweighted"] for r in grid_test]
    f1_t = [r["f1_unweighted"] for r in grid_test]
    bal_t = [r["balanced_accuracy_unweighted"] for r in grid_test]
    spec_t = [r["specificity_unweighted"] for r in grid_test]

    prec_v = [r["precision_unweighted"] for r in grid_val_oof]
    rec_v = [r["recall_unweighted"] for r in grid_val_oof]
    f1_v = [r["f1_unweighted"] for r in grid_val_oof]
    bal_v = [r["balanced_accuracy_unweighted"] for r in grid_val_oof]

    # -------------------------------------------------------------------------
    # Figure T1: Precision, Recall, F1-Score, and Balanced Accuracy vs Threshold
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=600)

    ax1.plot(taus, prec_t, "o-", color="#1f78b4", lw=2.2, markersize=6, label="Precision (Test Set, N=3,755)")
    ax1.plot(taus, prec_v, "s--", color="#a6cee3", lw=1.6, markersize=5, label="Precision (5-Fold OOF Val, N=15,016)")
    ax1.plot(taus, rec_t, "^-", color="#d95f02", lw=2.2, markersize=6, label="Recall / Sensitivity (Test Set)")
    ax1.plot(taus, rec_v, "v--", color="#fdbf6f", lw=1.6, markersize=5, label="Recall / Sensitivity (5-Fold OOF Val)")
    ax1.plot(taus, spec_t, "d:", color="#33a02c", lw=1.8, markersize=5, label="Specificity (Test Set)")
    ax1.axhline(0.1198, color="gray", linestyle="-.", lw=1.2, label="Unweighted Test Prevalence (11.98%)")

    ax1.axvline(0.10, color="#e31a1c", linestyle=":", lw=1.4, alpha=0.8)
    ax1.axvline(0.20, color="#6a3d9a", linestyle=":", lw=1.4, alpha=0.8)
    ax1.annotate("τ=0.10 Baseline\nPrec: 23.2%, Rec: 77.3%", xy=(0.10, 0.7733), xytext=(0.14, 0.83),
                 arrowprops=dict(facecolor="#e31a1c", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.5, fontweight="bold", color="#b10026",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#e31a1c", alpha=0.92))
    ax1.annotate("τ=0.20 F1-Optimal\nPrec: 30.5%, Rec: 46.9%", xy=(0.20, 0.3049), xytext=(0.28, 0.22),
                 arrowprops=dict(facecolor="#6a3d9a", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.5, fontweight="bold", color="#6a3d9a",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#6a3d9a", alpha=0.92))

    ax1.set_title("(A) Precision, Recall, and Specificity vs. Decision Threshold", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("Classification Decision Threshold (τ)", fontsize=10.5)
    ax1.set_ylabel("Metric Value (Proportion)", fontsize=10.5)
    ax1.set_xlim(0.02, 0.93)
    ax1.set_ylim(-0.03, 1.05)
    ax1.set_xticks([0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    ax1.legend(loc="center right", fontsize=8.0, frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.45)

    ax2.plot(taus, f1_t, "o-", color="#6a3d9a", lw=2.3, markersize=6, label="F1-Score (Test Set, N=3,755)")
    ax2.plot(taus, f1_v, "s--", color="#cab2d6", lw=1.8, markersize=5, label="F1-Score (5-Fold OOF Val, N=15,016)")
    ax2.plot(taus, bal_t, "D-", color="#1b9e77", lw=2.2, markersize=6, label="Balanced Accuracy (Test Set)")
    ax2.plot(taus, bal_v, "^--", color="#66c2a5", lw=1.6, markersize=5, label="Balanced Accuracy (5-Fold OOF Val)")

    ax2.annotate("Max Balanced Accuracy at τ=0.10\n(Val: 0.7152, Test: 0.7122)", xy=(0.10, 0.7122), xytext=(0.23, 0.73),
                 arrowprops=dict(facecolor="#1b9e77", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.5, fontweight="bold", color="#1b9e77",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#1b9e77", alpha=0.92))
    ax2.annotate("Validation Primary-Grid F1 Peak at τ=0.20\n(Val F1: 0.3855, Test F1: 0.3695;\nFine-Grid Peak τ=0.15 Test F1: 0.3742)",
                 xy=(0.20, 0.3855), xytext=(0.32, 0.37),
                 arrowprops=dict(facecolor="#6a3d9a", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.3, fontweight="bold", color="#6a3d9a",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#6a3d9a", alpha=0.92))

    ax2.set_title("(B) F1-Score and Balanced Accuracy Across Thresholds", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("Classification Decision Threshold (τ)", fontsize=10.5)
    ax2.set_ylabel("Composite Metric Score", fontsize=10.5)
    ax2.set_xlim(0.02, 0.93)
    ax2.set_ylim(-0.03, 0.85)
    ax2.set_xticks([0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    ax2.legend(loc="upper right", fontsize=8.2, frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.45)

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t1_precision_recall_f1_vs_threshold.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t1_precision_recall_f1_vs_threshold.png"), dpi=600, bbox_inches="tight")
    plt.close()
    print("✓ Saved fig_t1_precision_recall_f1_vs_threshold (.pdf and .png at 600 DPI)")

    # -------------------------------------------------------------------------
    # Figure T2: Precision-Recall Trade-off Curve & Threshold Operating Locus
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=600)

    pr_p_te, pr_r_te, _ = precision_recall_curve(y_test, prob_test)
    pr_p_val, pr_r_val, _ = precision_recall_curve(y_train, oof_prob_stratified)

    ax1.plot(pr_r_val, pr_p_val, color="#a6cee3", lw=2.0, linestyle="--",
             label="5-Fold OOF Validation PR Curve (PR-AUC = 0.3260)")
    ax1.plot(pr_r_te, pr_p_te, color="#1f78b4", lw=2.5,
             label="Held-Out Test PR Curve (PR-AUC = 0.3184)")
    ax1.axhline(0.1198, color="#d73027", linestyle=":", lw=1.5,
                label="Random Classifier Baseline (Test Prev = 11.98%)")

    # Overlay discrete threshold markers on Test PR curve
    highlight_taus = [
        (0.05, "#7f7f7f", (-42, -26)),
        (0.10, "#e31a1c", (8, 16)),
        (0.15, "#ff7f00", (-55, -28)),
        (0.20, "#6a3d9a", (10, 18)),
        (0.25, "#1b9e77", (-60, -28)),
        (0.30, "#2b5c8f", (12, 16)),
        (0.40, "#b15928", (14, 22)),
        (0.50, "#333333", (12, -22))
    ]
    r_map = {r["threshold"]: r for r in grid_test}
    for t_val, col, offset in highlight_taus:
        row = r_map[t_val]
        ax1.scatter([row["recall_unweighted"]], [row["precision_unweighted"]],
                    color=col, s=75, zorder=6, edgecolors="black", linewidths=0.8)
        ax1.annotate(
            f"τ={t_val:.2f}\n({row['precision_unweighted']*100:.1f}%, {row['recall_unweighted']*100:.1f}%)",
            xy=(row["recall_unweighted"], row["precision_unweighted"]),
            xytext=offset, textcoords="offset points",
            fontsize=7.3, fontweight="bold", color=col,
            arrowprops=dict(arrowstyle="-", color=col, lw=0.7, alpha=0.65),
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor=col, alpha=0.92, lw=0.6)
        )

    ax1.set_title("(A) Precision–Recall Curve with Threshold Operating Points", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("Recall / Sensitivity (Proportion of True High-Cost Captured)", fontsize=10.5)
    ax1.set_ylabel("Precision / Positive Predictive Value (PPV)", fontsize=10.5)
    ax1.set_xlim(-0.02, 1.03)
    ax1.set_ylim(0.0, 0.90)
    ax1.legend(loc="upper right", fontsize=8.2, frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.45)

    # Panel B: Actual vs Theoretical Oracle Max Precision Bound by Flagged Volume
    valid_rows = [r for r in grid_test if r["flagged_count"] > 0 and r["threshold"] <= 0.50]
    t_sub = [r["threshold"] for r in valid_rows]
    act_p = [r["precision_unweighted"] * 100.0 for r in valid_rows]
    max_p = [r["oracle_max_precision_at_volume"] * 100.0 for r in valid_rows]
    enr_u = [r["enrichment_ratio_unweighted"] for r in valid_rows]

    ax2.plot(t_sub, max_p, "s--", color="#525252", lw=1.8, markersize=6,
             label="Theoretical Oracle Ceiling at Flagged Volume (min(P, Flagged)/Flagged)")
    ax2.plot(t_sub, act_p, "o-", color="#1f78b4", lw=2.4, markersize=7,
             label="Observed Model Precision (%)")
    ax2.axhline(11.98, color="#d73027", linestyle=":", lw=1.5, label="Unweighted Base Prevalence (11.98%)")

    enr_offsets = {
        0.10: (-12, -32),
        0.15: (-8, 18),
        0.20: (14, -26),
        0.30: (0, -28),
        0.40: (0, -28),
    }
    for r in valid_rows:
        if r["threshold"] in enr_offsets:
            ax2.annotate(
                f"{r['enrichment_ratio_unweighted']:.2f}× base\n(Flag: {r['flagged_pct_unweighted']:.1f}%)",
                xy=(r["threshold"], r["precision_unweighted"] * 100.0),
                xytext=enr_offsets[r["threshold"]], textcoords="offset points", ha="center",
                fontsize=7.3, fontweight="bold", color="#1f78b4",
                arrowprops=dict(arrowstyle="-", color="#1f78b4", lw=0.6, alpha=0.6),
                bbox=dict(boxstyle="round,pad=0.16", facecolor="#f0f8ff", edgecolor="#1f78b4", alpha=0.92, lw=0.5)
            )

    ax2.annotate("At τ=0.10 (39.97% flagged),\neven a perfect oracle cannot\nexceed 450/1501 = 29.98% precision",
                 xy=(0.10, 29.98), xytext=(0.17, 68.0),
                 arrowprops=dict(facecolor="#525252", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.3, fontweight="bold", color="#333333",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#525252", alpha=0.92))

    ax2.set_title("(B) Prevalence Ceiling & Enrichment Ratio Across Thresholds", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("Classification Decision Threshold (τ)", fontsize=10.5)
    ax2.set_ylabel("Precision (%) / Theoretical Ceiling (%)", fontsize=10.5)
    ax2.set_xlim(0.03, 0.53)
    ax2.set_ylim(0.0, 105.0)
    ax2.legend(loc="upper left", fontsize=8.0, frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.45)

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t2_precision_recall_tradeoff.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t2_precision_recall_tradeoff.png"), dpi=600, bbox_inches="tight")
    plt.close()
    print("✓ Saved fig_t2_precision_recall_tradeoff (.pdf and .png at 600 DPI)")

    # -------------------------------------------------------------------------
    # Figure T3: False Positives vs False Negatives and Flagged Cohort Volume
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=600)

    fps = [r["fp"] for r in grid_test]
    fns = [r["fn"] for r in grid_test]
    tps = [r["tp"] for r in grid_test]
    flagged_cnts = [r["flagged_count"] for r in grid_test]
    flagged_pcts_u = [r["flagged_pct_unweighted"] for r in grid_test]
    flagged_pcts_w = [r["flagged_pct_weighted"] for r in grid_test]

    ax1.plot(taus, fps, "s-", color="#e31a1c", lw=2.3, markersize=6, label="False Positives (FP Count)")
    ax1.plot(taus, fns, "^-", color="#ff7f00", lw=2.3, markersize=6, label="False Negatives (FN Count)")
    ax1.plot(taus, tps, "o--", color="#1f78b4", lw=1.8, markersize=5, label="True Positives (TP Count)")

    ax1.annotate("τ=0.10: 1,153 FP vs. 102 FN\n(High sensitivity screening)",
                 xy=(0.10, 1153), xytext=(0.20, 1320),
                 arrowprops=dict(facecolor="#e31a1c", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.3, fontweight="bold", color="#b10026",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#e31a1c", alpha=0.92))
    ax1.annotate("τ=0.20: FP cut by 58.3%\n(481 FP, 239 FN, 211 TP)",
                 xy=(0.20, 481), xytext=(0.30, 720),
                 arrowprops=dict(facecolor="#6a3d9a", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.3, fontweight="bold", color="#6a3d9a",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#6a3d9a", alpha=0.92))
    ax1.annotate("FP ≈ FN Crossover near τ=0.25\n(286 FP vs. 296 FN)",
                 xy=(0.25, 290), xytext=(0.38, 260),
                 arrowprops=dict(facecolor="#333333", shrink=0.08, width=1, headwidth=5),
                 fontsize=8.3, fontweight="bold", color="#333333",
                 bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#333333", alpha=0.92))

    ax1.set_title("(A) Error Counts (FP vs. FN) & True Positives Across Thresholds", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("Classification Decision Threshold (τ)", fontsize=10.5)
    ax1.set_ylabel("Number of Patients (Held-Out Test Set, N=3,755)", fontsize=10.5)
    ax1.set_xlim(0.02, 0.93)
    ax1.set_ylim(-50, 2000)
    ax1.set_xticks([0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    ax1.legend(loc="upper right", fontsize=8.5, frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.45)

    ax2.plot(taus, flagged_pcts_u, "o-", color="#2b5c8f", lw=2.3, markersize=6,
             label="Unweighted Proportion Flagged (% of Sample)")
    ax2.plot(taus, flagged_pcts_w, "D--", color="#1b9e77", lw=2.0, markersize=5,
             label="Survey-Weighted Proportion Flagged (% of US Pop)")
    ax2.axhline(11.98, color="#d73027", linestyle=":", lw=1.4, label="Actual Unweighted High-Cost Prevalence (11.98%)")
    ax2.axhline(10.51, color="#33a02c", linestyle="-.", lw=1.4, label="Actual Survey-Weighted Prevalence (10.51%)")

    for t_v, y_off in [(0.10, 8), (0.20, 8), (0.30, 8), (0.50, 8)]:
        r_v = r_map[t_v]
        ax2.annotate(
            f"τ={t_v:.2f}: {r_v['flagged_count']} pts\n({r_v['flagged_pct_unweighted']:.1f}%)",
            xy=(t_v, r_v["flagged_pct_unweighted"]),
            xytext=(12, y_off), textcoords="offset points",
            fontsize=8.0, fontweight="bold", color="#2b5c8f",
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="#2b5c8f", alpha=0.9)
        )

    ax2.set_title("(B) Proportion of Patients Flagged as High-Expenditure", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("Classification Decision Threshold (τ)", fontsize=10.5)
    ax2.set_ylabel("Patients Classified as High-Expenditure (%)", fontsize=10.5)
    ax2.set_xlim(0.02, 0.93)
    ax2.set_ylim(-2, 68)
    ax2.set_xticks([0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    ax2.legend(loc="upper right", fontsize=8.2, frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.45)

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t3_fp_fn_and_flagged_volume.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t3_fp_fn_and_flagged_volume.png"), dpi=600, bbox_inches="tight")
    plt.close()
    print("✓ Saved fig_t3_fp_fn_and_flagged_volume (.pdf and .png at 600 DPI)")

    # -------------------------------------------------------------------------
    # Figure T4: Confusion Matrices at Key Operating Thresholds (0.10, 0.20, 0.30, 0.50)
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.3), dpi=600)
    cm_specs = [
        (0.10, "τ = 0.10 (Original Screening)\nMax BalAcc = 0.712 | F1 = 0.357"),
        (0.20, "τ = 0.20 (Validation F1-Opt)\nBalAcc = 0.662 | F1 = 0.370"),
        (0.30, "τ = 0.30 (Targeted Care)\nBalAcc = 0.601 | F1 = 0.310"),
        (0.50, "τ = 0.50 (Naive Default)\nBalAcc = 0.514 | F1 = 0.062")
    ]
    for ax, (tau_cm, title_cm) in zip(axes, cm_specs):
        row = r_map[tau_cm]
        mat = np.array([[row["tn"], row["fp"]], [row["fn"], row["tp"]]])
        im = ax.imshow(mat, cmap="Blues", vmin=0, vmax=3400)
        ax.set_title(title_cm, fontsize=9.5, fontweight="bold", pad=8)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Pred Low (<τ)", "Pred High (≥τ)"], fontsize=8.5)
        ax.set_yticklabels(["Actual Low\n(N=3,305)", "Actual High\n(N=450)"], fontsize=8.5)

        labels_mat = [
            [f"TN = {row['tn']:,}\n({row['specificity_unweighted']*100:.1f}% Spec)",
             f"FP = {row['fp']:,}\n({row['fpr_unweighted']*100:.1f}% FPR)"],
            [f"FN = {row['fn']:,}\n({row['fnr_unweighted']*100:.1f}% FNR)",
             f"TP = {row['tp']:,}\n({row['recall_unweighted']*100:.1f}% Rec)"]
        ]
        for i in range(2):
            for j in range(2):
                val = mat[i, j]
                txt_col = "white" if val > 1600 else "#111111"
                ax.text(j, i, labels_mat[i][j], ha="center", va="center",
                        fontsize=8.5, fontweight="bold", color=txt_col)
        ax.set_xlabel(
            f"Prec: {row['precision_unweighted']*100:.1f}% ({row['enrichment_ratio_unweighted']:.2f}×) | "
            f"Flagged: {row['flagged_count']:,} ({row['flagged_pct_unweighted']:.1f}%)",
            fontsize=8.2, fontweight="bold", labelpad=6
        )

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t4_confusion_matrices_comparison.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t4_confusion_matrices_comparison.png"), dpi=600, bbox_inches="tight")
    plt.close()
    print("✓ Saved fig_t4_confusion_matrices_comparison (.pdf and .png at 600 DPI)")

    # -------------------------------------------------------------------------
    # Figure T5: Calibration Bin Distribution & Multi-Cohort Overfitting Audit
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=600)

    non_empty_bins = [b for b in cal_bins_test if b["n_patients"] > 0]
    b_labels = [b["bin_range"] for b in non_empty_bins]
    b_counts = [b["n_patients"] for b in non_empty_bins]
    b_pred = [b["mean_predicted_prob"] * 100.0 for b in non_empty_bins]
    b_obs = [b["observed_event_rate_unweighted"] * 100.0 for b in non_empty_bins]
    x_pos = np.arange(len(non_empty_bins))

    ax1_twin = ax1.twinx()
    bars = ax1.bar(x_pos, b_counts, width=0.58, color="#cbd5e8", edgecolor="#4a6fe3", alpha=0.65,
                   label="Patient Count per Probability Bin (left axis)")
    l1 = ax1_twin.plot(x_pos, b_pred, "s--", color="#1f78b4", lw=2.0, markersize=6,
                       label="Mean Predicted Probability % (right axis)")
    l2 = ax1_twin.plot(x_pos, b_obs, "o-", color="#d95f02", lw=2.2, markersize=6,
                       label="Observed High-Cost Event Rate % (right axis)")

    for idx_b, cnt_b in enumerate(b_counts):
        ax1.text(idx_b, cnt_b + 30, f"{cnt_b}", ha="center", va="bottom", fontsize=7.5, color="#333333")

    ax1.set_title("(A) Score Distribution & Observed Event Rate by Probability Bin", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("Predicted Probability Bin (Test Set, N=3,755; Max p̂ = 0.8008)", fontsize=10.0)
    ax1.set_ylabel("Number of Patients in Bin", fontsize=10.5, color="#2b5c8f")
    ax1_twin.set_ylabel("Probability / Observed High-Cost Prevalence (%)", fontsize=10.5, color="#d95f02")
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(b_labels, rotation=35, ha="right", fontsize=8.0)
    ax1.set_ylim(0, 1980)
    ax1_twin.set_ylim(0, 112)

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax1_twin.get_legend_handles_labels()
    ax1_twin.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper center", bbox_to_anchor=(0.47, 0.99), fontsize=7.8, frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.4)

    # Panel B: Multi-Split & Multi-Release Overfitting Audit
    split_keys = [
        ("HC-251\nTrain\n(N=15,016)", "HC251_Train_InSample"),
        ("HC-251\nStrat OOF\n(N=15,016)", "HC251_5Fold_Stratified_OOF_Val"),
        ("HC-251\nHH OOF\n(N=15,016)", "HC251_5Fold_HouseholdGroup_OOF_Val"),
        ("HC-251\nHeld-Out\n(N=3,755)", "HC251_HeldOut_Test"),
        ("HC-256 P29\nUnseen 24\n(N=10,037)", "HC256_2024_Panel29_Unseen"),
        ("HC-256 Full\nCross-Sec\n(N=18,979)", "HC256_2024_Full"),
        ("HC-257 P28\nProsp Y2\n(N=8,708)", "HC257_Panel28_Prospective_Y2")
    ]
    s_labels = [k[0] for k in split_keys]
    s_rocs = [overfitting_audit[k[1]]["roc_auc_unweighted"] for k in split_keys]
    s_prs = [overfitting_audit[k[1]]["pr_auc_unweighted"] for k in split_keys]
    s_briers = [overfitting_audit[k[1]]["brier_unweighted"] for k in split_keys]
    s_bss_w = [overfitting_audit[k[1]]["bss_weighted"] for k in split_keys]

    x_s = np.arange(len(split_keys))
    w_bar = 0.25
    b1 = ax2.bar(x_s - w_bar, s_rocs, width=w_bar, color="#1f78b4", edgecolor="black", lw=0.6, label="ROC-AUC (Unweighted)")
    b2 = ax2.bar(x_s, s_prs, width=w_bar, color="#33a02c", edgecolor="black", lw=0.6, label="PR-AUC (Unweighted)")
    b3 = ax2.bar(x_s + w_bar, s_briers, width=w_bar, color="#e31a1c", edgecolor="black", lw=0.6, label="Brier Score (Lower = Better)")

    for bar_grp in [b1, b2, b3]:
        for rect in bar_grp:
            h = rect.get_height()
            ax2.text(rect.get_x() + rect.get_width() / 2.0, h + 0.012, f"{h:.3f}",
                     ha="center", va="bottom", fontsize=6.8, fontweight="bold", rotation=90)

    ax2.set_title("(B) Overfitting & Generalization Audit Across Splits and Releases", fontsize=11.5, fontweight="bold")
    ax2.set_ylabel("Metric Value", fontsize=10.5)
    ax2.set_xticks(x_s)
    ax2.set_xticklabels(s_labels, fontsize=7.5)
    ax2.set_ylim(0.0, 1.08)
    ax2.legend(loc="upper right", fontsize=8.0, frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.45)

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t5_calibration_and_overfitting_audit.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_t5_calibration_and_overfitting_audit.png"), dpi=600, bbox_inches="tight")
    plt.close()
    print("✓ Saved fig_t5_calibration_and_overfitting_audit (.pdf and .png at 600 DPI)")


if __name__ == "__main__":
    main()
