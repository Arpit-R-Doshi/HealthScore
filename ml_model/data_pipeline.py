"""
HealthScore Data Processing Pipeline
Authoritative module for loading, cleaning, feature engineering, and splitting MEPS HC-251 data.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(BASE_DIR, "h251.dta")

# The exact 14 features used by the HealthScore clinical models
FEATURE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Frailty_Index',
    'Age_x_Frailty', 'Age_x_Comorbidity', 'K6SUM42'
]

# Survey and administrative variables
DESIGN_COLS = ['DUPERSID', 'PERWT23F', 'VARSTR', 'VARPSU', 'TOTEXP23']

# Features directly observable from standard user profile / intake
OBSERVABLE_FEATURE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Age_x_Comorbidity'
]

# Diagnostic variables in raw MEPS
DIAGNOSTIC_COLS = [
    'HIBPDX', 'CHDDX', 'MIDX', 'STRKDX', 'DIABDX_M18', 'CHOLDX',
    'ASTHDX', 'EMPHDX', 'CHBRON31', 'CANCERDX', 'ARTHDX', 'JTPAIN31_M18',
    'ADDPRS42', 'ADHDADDX', 'DFCOG42', 'ANYLMI23', 'ADGENH42', 'K6SUM42'
]


def load_raw_meps(filepath=DEFAULT_DATA_PATH):
    """Load raw Stata MEPS HC-251 dataset."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"MEPS dataset not found at: {filepath}")
    
    needed_cols = ['AGE23X', 'SEX', 'TOTEXP23', 'PERWT23F', 'VARSTR', 'VARPSU'] + DIAGNOSTIC_COLS
    df = pd.read_stata(filepath, columns=needed_cols, convert_categoricals=False)
    return df


def compute_conditional_imputation_table(df_train_raw, df_train_clean):
    """
    Computes empirical conditional expectation table strictly from training data.
    Excludes MEPS special nonresponse codes (-7 Refused, -8 Don't Know, -9 Not Ascertained)
    and accounts for age-based survey skip patterns (e.g. SAQ variables inapplicable to children).
    """
    df = df_train_raw.copy()
    df['Comorbidity_Count'] = df_train_clean['Comorbidity_Count']
    df['age_bracket'] = pd.cut(
        df['AGE23X'],
        bins=[-1, 17, 44, 64, 150],
        labels=['pediatric', 'young_adult', 'middle_aged', 'senior']
    )
    df['comorb_tier'] = pd.cut(
        df['Comorbidity_Count'],
        bins=[-1, 0, 1, 10],
        labels=['tier_0', 'tier_1', 'tier_2plus']
    )

    lookup = {}
    for ab in ['pediatric', 'young_adult', 'middle_aged', 'senior']:
        for ct in ['tier_0', 'tier_1', 'tier_2plus']:
            sub = df[(df['age_bracket'] == ab) & (df['comorb_tier'] == ct)]
            
            # ADGENH42: Valid adult responses 1-5; pediatric not administered
            valid_genh = sub[sub['ADGENH42'].between(1, 5)]['ADGENH42']
            mean_genh = float(valid_genh.mean()) if len(valid_genh) > 0 else 2.0

            # K6SUM42: Valid adult scores 0-24; pediatric not administered
            valid_k6 = sub[sub['K6SUM42'].between(0, 24)]['K6SUM42']
            mean_k6 = float(valid_k6.mean()) if len(valid_k6) > 0 else 0.0

            # ANYLMI23: Valid responses 1=Yes, 2=No
            valid_lmi = sub[sub['ANYLMI23'].isin([1, 2])]
            pct_lmi = float((valid_lmi['ANYLMI23'] == 1).mean()) if len(valid_lmi) > 0 else 0.0

            # DFCOG42: Valid responses 1=Yes, 2=No (ages 5+)
            valid_cog = sub[sub['DFCOG42'].isin([1, 2])]
            pct_cog = float((valid_cog['DFCOG42'] == 1).mean()) if len(valid_cog) > 0 else 0.0

            lookup[f"{ab}_{ct}"] = {
                "perceived_health": round(mean_genh, 4),
                "physical_limitation": round(pct_lmi, 4),
                "cognitive_difficulty": round(pct_cog, 4),
                "k6_distress": round(mean_k6, 4),
                "sample_size_total": int(len(sub)),
                "sample_size_valid_saq": int(len(valid_genh))
            }
    return lookup


def clean_and_engineer_features(df, filter_zero_expenditure=False):
    """
    Cleans raw MEPS records and engineers custom chronic condition clusters and frailty features.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Raw MEPS dataframe.
    filter_zero_expenditure : bool
        If True, drops TOTEXP23 == 0 (conditional expenditure model).
        If False, retains all eligible individuals (full-population model).
        
    Returns:
    --------
    cleaned_df : pd.DataFrame
        Dataframe with engineered features, target, and audit log.
    audit_report : dict
        Counts of records before and after each filter.
    """
    initial_count = len(df)
    
    # Step 1: Filter invalid/deceased/ineligible ages (AGE23X < 0)
    df_valid_age = df[df['AGE23X'] >= 0].copy()
    dropped_age = initial_count - len(df_valid_age)
    
    # Step 2: Zero expenditure handling
    zero_count = (df_valid_age['TOTEXP23'] == 0).sum()
    if filter_zero_expenditure:
        df_clean = df_valid_age[df_valid_age['TOTEXP23'] > 0].copy()
        dropped_zero = zero_count
    else:
        df_clean = df_valid_age.copy()
        dropped_zero = 0

    final_count = len(df_clean)

    # Demographic Features
    df_clean['Gender_Male'] = (df_clean['SEX'] == 1).astype(int)

    # Binary Diagnostics: In MEPS, 1=Yes, 2=No, -1=Inapplicable
    binary_dx_cols = [
        'HIBPDX', 'CHDDX', 'MIDX', 'STRKDX', 'DIABDX_M18', 'CHOLDX',
        'ASTHDX', 'EMPHDX', 'CHBRON31', 'CANCERDX', 'ARTHDX', 'JTPAIN31_M18',
        'ADHDADDX'
    ]
    for col in binary_dx_cols:
        df_clean[col] = (df_clean[col] == 1).astype(int)

    # ADDPRS42: PHQ-2 symptom screener (0=None, 1=Few days, 2=Half days, 3=Nearly every day; negative=Inapplicable)
    # Binarized as indicator of past-2-week depressive symptoms (codes 1, 2, 3)
    df_clean['ADDPRS42'] = df_clean['ADDPRS42'].apply(lambda x: 1 if x in [1, 2, 3] else 0)

    # Functional and Cognitive Limitations (1=Yes, 2=No)
    df_clean['ANYLMI23'] = (df_clean['ANYLMI23'] == 1).astype(int)
    df_clean['DFCOG42'] = (df_clean['DFCOG42'] == 1).astype(int)

    # Self-Rated General Health: ADGENH42 (1=Excellent, 2=Very Good, 3=Good, 4=Fair, 5=Poor; -1=Inapplicable)
    # Inapplicable respondents (mostly children under 18) default to 2 (Very Good, empirical median)
    df_clean['ADGENH42'] = df_clean['ADGENH42'].apply(lambda x: x if x > 0 else 2)

    # Psychological Distress Scale: K6SUM42 (0-24 score; negative=Inapplicable)
    df_clean['K6SUM42'] = df_clean['K6SUM42'].apply(lambda x: x if x >= 0 else 0)

    # Custom Chronic Condition Clusters (Heuristic clusters inspired by ACG concepts, NOT official ACG grouper software)
    df_clean['Cardio_ACG'] = df_clean['HIBPDX'] + df_clean['CHDDX'] + df_clean['MIDX'] + df_clean['STRKDX']
    df_clean['Metabolic_ACG'] = df_clean['DIABDX_M18'] + df_clean['CHOLDX']
    df_clean['Respiratory_ACG'] = df_clean['ASTHDX'] + df_clean['EMPHDX'] + df_clean['CHBRON31']
    df_clean['Oncology_ACG'] = df_clean['CANCERDX']
    df_clean['Musculoskeletal_ACG'] = df_clean['ARTHDX'] + df_clean['JTPAIN31_M18']
    df_clean['Psychiatric_ACG'] = df_clean['ADDPRS42'] + df_clean['ADHDADDX']

    cluster_cols = ['Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG',
                    'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG']

    df_clean['Comorbidity_Count'] = (df_clean[cluster_cols] > 0).sum(axis=1)
    df_clean['Multimorbidity_Penalty'] = df_clean['Comorbidity_Count'] ** 2
    df_clean['Frailty_Index'] = df_clean['ADGENH42'] + (df_clean['ANYLMI23'] * 2) + (df_clean['DFCOG42'] * 2)

    df_clean['Age_x_Frailty'] = df_clean['AGE23X'] * df_clean['Frailty_Index']
    df_clean['Age_x_Comorbidity'] = df_clean['AGE23X'] * df_clean['Comorbidity_Count']

    # Target Variables
    df_clean['y_expenditure'] = df_clean['TOTEXP23'].astype(float)
    df_clean['y_log_cost'] = np.log1p(df_clean['y_expenditure'])

    audit_report = {
        "raw_records": int(initial_count),
        "dropped_invalid_age": int(dropped_age),
        "zero_expenditure_records": int(zero_count),
        "zero_expenditure_dropped": int(dropped_zero),
        "final_records": int(final_count)
    }

    return df_clean, audit_report


def split_data(df, raw_df=None, test_size=0.20, random_state=42):
    """
    Performs reproducible train/test split.
    High-expenditure thresholds are derived STRICTLY on training split to eliminate data leakage.
    Provides normalized weights for ML solvers and computes both unweighted and weighted P90 targets.
    """
    X = df[FEATURE_COLS].copy()
    y_reg = df['y_log_cost'].copy()
    y_raw = df['y_expenditure'].copy()
    weights = df['PERWT23F'].copy()

    X_train, X_test, y_train_log, y_test_log, y_train_raw, y_test_raw, w_train, w_test = train_test_split(
        X, y_reg, y_raw, weights,
        test_size=test_size,
        random_state=random_state
    )

    # Derive high-expenditure threshold strictly from X_train / y_train (zero test leakage)
    p90_threshold_unw = float(np.percentile(y_train_raw, 90))
    y_train_cls_unw = (y_train_raw >= p90_threshold_unw).astype(int)
    y_test_cls_unw = (y_test_raw >= p90_threshold_unw).astype(int)

    # Survey-weighted P90 threshold derived from training distribution
    sorter = np.argsort(y_train_raw.values)
    vals_sorted = y_train_raw.values[sorter]
    w_sorted = w_train.values[sorter]
    cum_w = np.cumsum(w_sorted) - 0.5 * w_sorted
    cum_w /= np.sum(w_sorted)
    p90_threshold_w = float(np.interp([0.90], cum_w, vals_sorted)[0])
    y_train_cls_wtd = (y_train_raw >= p90_threshold_w).astype(int)
    y_test_cls_wtd = (y_test_raw >= p90_threshold_w).astype(int)

    # Normalized weights for ML solvers (preserves effective sample size N and regularizer balance)
    w_train_norm = w_train * (len(w_train) / w_train.sum())
    w_test_norm = w_test * (len(w_test) / w_test.sum())

    # Compute training conditional imputation table strictly from training split
    if raw_df is not None:
        imputation_table = compute_conditional_imputation_table(raw_df.loc[X_train.index], df.loc[X_train.index])
    else:
        imputation_table = compute_conditional_imputation_table(df.loc[X_train.index], df.loc[X_train.index])

    data_splits = {
        "X_train": X_train, "X_test": X_test,
        "y_train_log": y_train_log, "y_test_log": y_test_log,
        "y_train_raw": y_train_raw, "y_test_raw": y_test_raw,
        "y_train_cls": y_train_cls_unw, "y_test_cls": y_test_cls_unw,
        "y_train_cls_unw": y_train_cls_unw, "y_test_cls_unw": y_test_cls_unw,
        "y_train_cls_wtd": y_train_cls_wtd, "y_test_cls_wtd": y_test_cls_wtd,
        "w_train": w_train, "w_test": w_test,
        "w_train_norm": w_train_norm, "w_test_norm": w_test_norm,
        "p90_threshold_unweighted": p90_threshold_unw,
        "p90_threshold_weighted": p90_threshold_w,
        "feature_cols": FEATURE_COLS,
        "observable_feature_cols": OBSERVABLE_FEATURE_COLS,
        "imputation_table": imputation_table
    }
    return data_splits
