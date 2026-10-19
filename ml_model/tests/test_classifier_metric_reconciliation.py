"""
Automated Lightweight Consistency Check for Classifier Metric Reconciliation
Validates concordance across:
  - ml_model/risk_engine.py
  - ml_model/model_manifest.json
  - research_completion/experiments/experiment_registry.json
  - research_completion/paper/REVISED_PAPER.md
  - research_completion/MODEL_COMPARISON_REPORT.md
  - research_completion/MANUSCRIPT_FINAL_QA_CHECKLIST.md
"""

import os
import json
import hashlib
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_approved_classifier_serving_candidate():
    """Verify ml_model/risk_engine.py selects the weighted P90 classifier artifact."""
    import sys
    sys.path.insert(0, os.path.join(REPO_ROOT, "ml_model"))
    import risk_engine

    expected_artifact = "risk_model_classifier_observable_weighted_p90.pkl"
    assert os.path.basename(risk_engine.CLS_MODEL_PATH) == expected_artifact
    assert os.path.exists(risk_engine.CLS_MODEL_PATH)

    # Check hash matches manifest
    with open(risk_engine.CLS_MODEL_PATH, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    manifest_path = os.path.join(REPO_ROOT, "ml_model", "model_manifest.json")
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    cls_spec = manifest["approved_models"]["high_cost_classifier"]
    assert cls_spec["artifact_path"] == f"artifacts/{expected_artifact}"
    assert cls_spec["sha256"].lower() == file_hash.lower()
    assert cls_spec["weighting_policy"] == "normalized_person_weights"


def test_registry_canonical_metrics():
    """Verify exact canonical metrics for weighted serving candidate in experiment_registry.json."""
    registry_path = os.path.join(REPO_ROOT, "research_completion", "experiments", "experiment_registry.json")
    with open(registry_path, "r") as f:
        reg = json.load(f)

    cls_comparisons = {m["model_name"]: m for m in reg["classification_comparisons"]}

    # Approved Serving Candidate
    wtd_candidate = cls_comparisons.get("Logistic Regression (11-Feat Observable, Weighted Fit)")
    assert wtd_candidate is not None
    assert wtd_candidate["roc_auc"] == 0.7654
    assert wtd_candidate["roc_auc_ci_95"] == [0.7444, 0.7881]
    assert wtd_candidate["pr_auc"] == 0.3184
    assert wtd_candidate["pr_auc_ci_95"] == [0.2876, 0.3556]
    assert wtd_candidate["brier_unweighted"] == 0.0936
    assert wtd_candidate["bss_unweighted"] == 0.1123
    assert wtd_candidate["brier_weighted"] == 0.0845
    assert wtd_candidate["bss_weighted"] == 0.1025
    assert wtd_candidate["calibration_in_the_large_citl"] == 0.0646
    assert wtd_candidate["citl_method"] == "exact_brentq_root"
    assert wtd_candidate["cal_intercept"] == -0.0409
    assert wtd_candidate["cal_slope"] == 0.9438
    assert wtd_candidate["precision_at_10pct"] == 0.2318
    assert wtd_candidate["recall_at_10pct"] == 0.7733
    assert wtd_candidate["f1_at_10pct"] == 0.3567

    # Weighting Ablation Candidate (distinct metrics)
    unw_candidate = cls_comparisons.get("Logistic Regression (11-Feat Observable, Unweighted Fit)")
    assert unw_candidate is not None
    assert unw_candidate["roc_auc"] == 0.7652
    assert unw_candidate["roc_auc_ci_95"] == [0.7433, 0.7882]
    assert unw_candidate["pr_auc"] == 0.3192
    assert unw_candidate["pr_auc_ci_95"] == [0.2869, 0.3582]
    assert unw_candidate["calibration_in_the_large_citl"] == 0.0570
    assert unw_candidate["cal_intercept"] == -0.1271
    assert unw_candidate["cal_slope"] == 0.9008
    assert unw_candidate["precision_at_10pct"] == 0.2278
    assert unw_candidate["recall_at_10pct"] == 0.7644
    assert unw_candidate["f1_at_10pct"] == 0.3510


def test_enrichment_arithmetic():
    """Verify precision enrichment arithmetic across all three baselines using exact reported values."""
    prec = 0.2318
    unw_test_prev = 0.1198
    wtd_test_prev = 0.105134
    train_wtd_prev = 0.099888

    ratio_unw = prec / unw_test_prev
    ratio_wtd = prec / wtd_test_prev
    ratio_train = prec / train_wtd_prev

    # 0.2318 / 0.1198 = 1.9348... -> 1.93x
    assert round(ratio_unw, 2) == 1.93
    # 0.2318 / 0.105134 = 2.2048... -> 2.20x
    assert round(ratio_wtd, 2) == 2.20
    # 0.2318 / 0.099888 = 2.3206... -> 2.32x
    assert round(ratio_train, 2) == 2.32


def test_revised_paper_alignment():
    """Verify that REVISED_PAPER.md correctly presents reconciled metrics without stale errors."""
    paper_path = os.path.join(REPO_ROOT, "research_completion", "paper", "REVISED_PAPER.md")
    with open(paper_path, "r") as f:
        content = f.read()

    # Must contain exact reconciled metrics
    assert "**0.7654** [0.7444, 0.7881]" in content
    assert "**0.3184** [0.2876, 0.3556]" in content
    assert "+0.0646" in content
    assert "0.9438" in content
    assert "-0.0409" in content
    assert "0.3567" in content

    # Enrichment ratios explicitly labeled
    assert "1.93" in content
    assert "2.20" in content
    assert "2.32" in content

    # Stale/erroneous strings must NOT appear in the manuscript
    assert "-0.038" not in content
    assert "2.2-fold enrichment over the unweighted base prevalence" not in content


def test_model_comparison_report_alignment():
    """Verify that MODEL_COMPARISON_REPORT.md accurately reflects the reconciled metrics."""
    report_path = os.path.join(REPO_ROOT, "research_completion", "MODEL_COMPARISON_REPORT.md")
    with open(report_path, "r") as f:
        content = f.read()

    assert "**0.7654** [0.7444, 0.7881]" in content
    assert "**0.3184** [0.2876, 0.3556]" in content
    assert "+0.0646" in content
    assert "0.9438" in content
    assert "-0.0409" in content
