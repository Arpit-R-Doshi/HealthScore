"""
Automated Targeted Consistency Check for Classifier Metric Reconciliation
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
import re
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
    """Verify exact canonical metrics for all key candidate models in experiment_registry.json."""
    registry_path = os.path.join(REPO_ROOT, "research_completion", "experiments", "experiment_registry.json")
    with open(registry_path, "r") as f:
        reg = json.load(f)

    cls_comparisons = {m["model_name"]: m for m in reg["classification_comparisons"]}

    # Approved Serving Candidate: Logistic Regression (11-Feat Observable, Weighted Fit)
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

    # Weighting Ablation Candidate: Logistic Regression (11-Feat Observable, Unweighted Fit)
    unw_candidate = cls_comparisons.get("Logistic Regression (11-Feat Observable, Unweighted Fit)")
    assert unw_candidate is not None
    assert unw_candidate["roc_auc"] == 0.7652
    assert unw_candidate["roc_auc_ci_95"] == [0.7433, 0.7882]
    assert unw_candidate["pr_auc"] == 0.3192
    assert unw_candidate["pr_auc_ci_95"] == [0.2869, 0.3582]
    assert unw_candidate["brier_unweighted"] == 0.0936
    assert unw_candidate["brier_weighted"] == 0.0845
    assert unw_candidate["bss_weighted"] == 0.1025
    assert unw_candidate["calibration_in_the_large_citl"] == 0.0570
    assert unw_candidate["cal_intercept"] == -0.1271
    assert unw_candidate["cal_slope"] == 0.9008
    assert unw_candidate["precision_at_10pct"] == 0.2278
    assert unw_candidate["recall_at_10pct"] == 0.7644
    assert unw_candidate["f1_at_10pct"] == 0.3510

    # Random Forest (11-Feat Observable)
    rf_candidate = cls_comparisons.get("Random Forest (11-Feat Observable)")
    assert rf_candidate is not None
    assert rf_candidate["roc_auc"] == 0.7693
    assert rf_candidate["roc_auc_ci_95"] == [0.7458, 0.7928]
    assert rf_candidate["pr_auc"] == 0.3157
    assert rf_candidate["pr_auc_ci_95"] == [0.2823, 0.355]
    assert rf_candidate["brier_unweighted"] == 0.0935
    assert rf_candidate["bss_unweighted"] == 0.1136
    assert rf_candidate["brier_weighted"] == 0.0841
    assert rf_candidate["bss_weighted"] == 0.1062
    assert rf_candidate["calibration_in_the_large_citl"] == 0.0601
    assert rf_candidate["cal_intercept"] == 0.0111
    assert rf_candidate["cal_slope"] == 0.9736
    assert rf_candidate["precision_at_10pct"] == 0.2342
    assert rf_candidate["recall_at_10pct"] == 0.7556
    assert rf_candidate["f1_at_10pct"] == 0.3575

    # XGBoost (Uncalibrated)
    xgb_candidate = cls_comparisons.get("XGBoost (Uncalibrated)")
    assert xgb_candidate is not None
    assert xgb_candidate["roc_auc"] == 0.7705
    assert xgb_candidate["roc_auc_ci_95"] == [0.7482, 0.794]
    assert xgb_candidate["pr_auc"] == 0.3196
    assert xgb_candidate["pr_auc_ci_95"] == [0.2853, 0.3598]
    assert xgb_candidate["brier_unweighted"] == 0.0932
    assert xgb_candidate["bss_unweighted"] == 0.1166
    assert xgb_candidate["brier_weighted"] == 0.0838
    assert xgb_candidate["bss_weighted"] == 0.1093
    assert xgb_candidate["calibration_in_the_large_citl"] == 0.0572
    assert xgb_candidate["cal_intercept"] == 0.0434
    assert xgb_candidate["cal_slope"] == 0.9926
    assert xgb_candidate["precision_at_10pct"] == 0.2262
    assert xgb_candidate["recall_at_10pct"] == 0.8022
    assert xgb_candidate["f1_at_10pct"] == 0.3529


def test_unweighted_enrichment_arithmetic():
    """
    Verify precision enrichment arithmetic strictly comparing unweighted precision to
    unweighted held-out test prevalence, avoiding mixed-base comparisons.
    """
    prec = 0.2318454363757495   # 348 / 1501
    unw_test_prev = 0.11984021304926765  # 450 / 3755

    enrichment = prec / unw_test_prev
    # 0.231845 / 0.119840 = 1.9346... -> approx 1.93x
    assert round(enrichment, 2) == 1.93

    # Point estimates reported to 4 decimal places
    prec_reported = 0.2318
    unw_test_reported = 0.119840
    enrichment_reported = prec_reported / unw_test_reported
    assert round(enrichment_reported, 2) == 1.93


def test_revised_paper_comparison_table_completeness():
    """
    Verify that REVISED_PAPER.md Table 6b contains all 9 canonical models,
    including restored Random Forest and uncalibrated XGBoost rows with exact metrics.
    """
    paper_path = os.path.join(REPO_ROOT, "research_completion", "paper", "REVISED_PAPER.md")
    with open(paper_path, "r") as f:
        content = f.read()

    # Verify all 9 model names appear in Table 6b
    table_models = [
        "**Constant Prevalence Baseline**",
        "**Demographic Baseline**",
        "**Clinical Conditions Only**",
        "**Logistic (11-Feat Observable, Weighted Fit)**",
        "*Logistic (11-Feat Observable, Unweighted Fit)*",
        "**Random Forest (11-Feat Observable)**",
        "**XGBoost (Uncalibrated)**",
        "**Platt-Calibrated XGBoost**",
        "**Logistic (14-Feat Oracle)**",
    ]
    for model_name in table_models:
        assert model_name in content, f"Model {model_name} missing from REVISED_PAPER.md"

    # Verify Random Forest (11-Feat Observable) row in Table 6b
    rf_pattern = (
        r"\|\s*\*\*Random Forest \(11-Feat Observable\)\*\*\s*\|\s*11\s*\|\s*Normalized Person Weights\s*\|"
        r"\s*0\.7693 \[0\.7458, 0\.7928\]\s*\|\s*0\.3157 \[0\.2823, 0\.3550\]\s*\|\s*0\.0935\s*\|\s*0\.0841\s*\|"
        r"\s*\+0\.1062\s*\|\s*\+0\.0601\s*\|\s*0\.9736\s*\|\s*0\.2342\s*\|\s*0\.7556\s*\|\s*0\.3575\s*\|"
    )
    assert re.search(rf_pattern, content) is not None, "Random Forest row in Table 6b does not match canonical metrics"

    # Verify XGBoost (Uncalibrated) row in Table 6b
    xgb_pattern = (
        r"\|\s*\*\*XGBoost \(Uncalibrated\)\*\*\s*\|\s*11\s*\|\s*Normalized Person Weights\s*\|"
        r"\s*0\.7705 \[0\.7482, 0\.7940\]\s*\|\s*0\.3196 \[0\.2853, 0\.3598\]\s*\|\s*0\.0932\s*\|\s*0\.0838\s*\|"
        r"\s*\+0\.1093\s*\|\s*\+0\.0572\s*\|\s*0\.9926\s*\|\s*0\.2262\s*\|\s*0\.8022\s*\|\s*0\.3529\s*\|"
    )
    assert re.search(xgb_pattern, content) is not None, "Uncalibrated XGBoost row in Table 6b does not match canonical metrics"

    # Verify approved serving candidate row in Table 6b
    serving_pattern = (
        r"\|\s*\*\*Logistic \(11-Feat Observable, Weighted Fit\)\*\*\s*\|\s*\*\*11\*\*\s*\|\s*\*\*Frozen Normalized Weights \(Serving\)\*\*\s*\|"
        r"\s*\*\*0\.7654\*\* \[0\.7444, 0\.7881\]\s*\|\s*\*\*0\.3184\*\* \[0\.2876, 0\.3556\]\s*\|\s*\*\*0\.0936\*\*\s*\|\s*\*\*0\.0845\*\*\s*\|"
        r"\s*\*\*\+0\.1025\*\*\s*\|\s*\*\*\+0\.0646\*\*\s*\|\s*\*\*0\.9438\*\*\s*\|\s*\*\*0\.2318\*\*\s*\|\s*\*\*0\.7733\*\*\s*\|\s*\*\*0\.3567\*\*\s*\|"
    )
    assert re.search(serving_pattern, content) is not None, "Serving candidate row in Table 6b does not match canonical metrics"


def test_revised_paper_enrichment_reporting():
    """
    Verify that REVISED_PAPER.md reports enrichment strictly as ~1.93x over unweighted test prevalence,
    and does NOT contain incompatible mixed-base comparisons against survey-weighted prevalences.
    """
    paper_path = os.path.join(REPO_ROOT, "research_completion", "paper", "REVISED_PAPER.md")
    with open(paper_path, "r") as f:
        content = f.read()

    # Must contain unweighted enrichment of approx 1.93x
    assert "1.93" in content
    assert "0.119840" in content or "11.98%" in content

    # Mixed-base enrichment claims must NOT appear anywhere in the paper
    assert "2.20x" not in content and "2.20\\text{x}" not in content
    assert "2.32x" not in content and "2.32\\text{x}" not in content
    assert "2.2-fold" not in content
    assert "2.3-fold" not in content

    # Ensure no claim compares precision 0.2318 against weighted prevalence (10.51% or 9.99%) for enrichment
    assert "over the survey-weighted test prevalence" not in content
    assert "over the training survey-weighted prevalence" not in content


def test_model_comparison_report_alignment():
    """Verify that MODEL_COMPARISON_REPORT.md accurately reflects all 9 models and unweighted enrichment."""
    report_path = os.path.join(REPO_ROOT, "research_completion", "MODEL_COMPARISON_REPORT.md")
    with open(report_path, "r") as f:
        content = f.read()

    # Must contain exact reconciled metrics for serving candidate
    assert "**0.7654** [0.7444, 0.7881]" in content
    assert "**0.3184** [0.2876, 0.3556]" in content
    assert "+0.0646" in content
    assert "0.9438" in content
    assert "-0.0409" in content
    assert "0.3567" in content

    # Must contain Random Forest and XGBoost rows
    assert "**Random Forest (11-Feat Observable)**" in content
    assert "0.7693 [0.7458, 0.7928]" in content
    assert "0.3157 [0.2823, 0.3550]" in content
    assert "+0.1062" in content

    assert "**XGBoost (Uncalibrated)**" in content
    assert "0.7705 [0.7482, 0.7940]" in content
    assert "0.3196 [0.2853, 0.3598]" in content
    assert "+0.1093" in content

    # Weighting policy column check
    assert "Weighting Policy" in content
    assert "Frozen Normalized Weights (Serving)" in content

    # Enrichment reporting: must contain unweighted 1.93x and not mixed-base 2.20x / 2.32x
    assert "1.93" in content
    assert "2.20" not in content
    assert "2.32" not in content


def test_no_stale_contradictory_classifier_metrics():
    """Verify no stale or erroneous classifier metrics remain across paper and comparison report."""
    files_to_check = [
        os.path.join(REPO_ROOT, "research_completion", "paper", "REVISED_PAPER.md"),
        os.path.join(REPO_ROOT, "research_completion", "MODEL_COMPARISON_REPORT.md"),
    ]

    stale_fragments = [
        "-0.038",  # old stale CITL/intercept
        "2.2-fold enrichment over the unweighted base prevalence",
        "2.20\\text{x}",
        "2.32\\text{x}",
    ]

    for filepath in files_to_check:
        with open(filepath, "r") as f:
            text = f.read()
        for stale in stale_fragments:
            assert stale not in text, f"Stale fragment '{stale}' found in {filepath}"


def test_no_unsupported_statistical_significance_claims():
    """
    Verify that neither the manuscript nor the model report claims that marginal CI overlap
    establishes 'no statistically significant' difference or advantage, and that both explicitly
    qualify the descriptive comparison as not being a formal paired statistical hypothesis test.
    """
    files_to_check = [
        os.path.join(REPO_ROOT, "research_completion", "paper", "REVISED_PAPER.md"),
        os.path.join(REPO_ROOT, "research_completion", "MODEL_COMPARISON_REPORT.md"),
    ]

    disallowed_phrases = [
        "no statistically significant discriminative advantage",
        "no statistically significant discriminative gain",
        "no statistically significant gain",
        "statistically significant discriminative advantage",
        "statistically significant discriminative gain",
    ]

    for filepath in files_to_check:
        with open(filepath, "r") as f:
            text = f.read()
        for phrase in disallowed_phrases:
            assert phrase not in text, f"Unsupported significance claim '{phrase}' found in {filepath}"
        # Assert explicit disclosure that paired statistical tests were not performed
        assert "paired statistical" in text
        assert "no claims of statistical significance or non-significance" in text


def test_off_chain_inference_architecture_consistency():
    """
    Verify that model selection rationale correctly reflects off-chain ML inference and
    does NOT claim on-chain inference verification or tree-traversal avoidance during transaction validation.
    """
    files_to_check = [
        os.path.join(REPO_ROOT, "research_completion", "paper", "REVISED_PAPER.md"),
        os.path.join(REPO_ROOT, "research_completion", "MODEL_COMPARISON_REPORT.md"),
    ]

    disallowed_implementation_claims = [
        "direct on-chain verification",
        "tree traversal in transaction validation",
        "tree-based computational overhead in transaction validation",
        "smart contract auditability, avoiding the higher compute overhead",
    ]

    for filepath in files_to_check:
        with open(filepath, "r") as f:
            text = f.read()
        for claim in disallowed_implementation_claims:
            assert claim not in text, f"Inconsistent on-chain implementation claim '{claim}' found in {filepath}"
        # Assert proper framing around off-chain inference and auditable ledger milestones
        assert "off-chain Python inference" in text
        assert "auditable risk-score milestones" in text
