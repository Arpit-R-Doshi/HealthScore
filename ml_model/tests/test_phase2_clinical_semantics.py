"""
Adversarial Clinical Semantics and Intake Challenge Test Suite (Phase 2 - Stage B)

DISCLAIMER & METHODOLOGICAL NOTICE:
This test suite consists strictly of programmatic software challenge cases and synthetic test patterns.
Passing these unit tests verifies parser boundary behavior, exception handling, and input routing.
IT DOES NOT CONSTITUTE CLINICAL VALIDATION.
Clinical semantic validity requires independent medical chart review and gold-standard clinical annotation.
"""

import os
import sys
import pytest
import numpy as np

# Add ml_model to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk_engine import (
    parse_clinical_conditions_detailed,
    parse_clinical_conditions,
    parse_structured_clinical_conditions,
    calculate_risk,
    STRUCTURED_CONDITION_REGISTRY
)


class TestPhase2ClinicalSemanticChallenges:
    """Adversarial challenge suite testing free-text regex vs structured intake across 10+ clinical error categories."""

    # ---------------------------------------------------------
    # Category 1: Individual Condition Concepts & Clusters
    # ---------------------------------------------------------
    @pytest.mark.parametrize("text,expected_cluster_idx,expected_min_tier", [
        ("patient diagnosed with hypertension", 0, 1),
        ("history of stroke", 0, 2),
        ("patient has myocardial infarction", 0, 2),
        ("diagnosed with type 2 diabetes", 1, 1),
        ("high cholesterol lipids", 1, 1),
        ("history of asthma", 2, 1),
        ("severe chronic bronchitis", 2, 2),
        ("diagnosed with malignant neoplasm cancer", 3, 1),
        ("suffering from osteoarthritis", 4, 1),
        ("major depressive disorder", 5, 1),
        ("bipolar disorder", 5, 2),
    ])
    def test_individual_condition_concepts(self, text, expected_cluster_idx, expected_min_tier):
        flags = parse_clinical_conditions(text)
        assert flags[expected_cluster_idx] >= expected_min_tier, f"Failed concept extraction for: {text}"

    # ---------------------------------------------------------
    # Category 2: Affirmed vs Explicitly Negated Conditions
    # ---------------------------------------------------------
    def test_affirmed_vs_negated_conditions(self):
        affirmed_result = parse_clinical_conditions_detailed("patient reports diabetes and asthma")
        assert "metabolic" in affirmed_result["explicitly_present"]
        assert "respiratory" in affirmed_result["explicitly_present"]
        assert affirmed_result["flags"][1] >= 1
        assert affirmed_result["flags"][2] >= 1

        negated_result = parse_clinical_conditions_detailed("denies diabetes, no history of asthma, negative for cancer")
        assert "metabolic" in negated_result["explicitly_negated"]
        assert "respiratory" in negated_result["explicitly_negated"]
        assert "oncology" in negated_result["explicitly_negated"]
        assert negated_result["flags"][1] == 0
        assert negated_result["flags"][2] == 0
        assert negated_result["flags"][3] == 0

    # ---------------------------------------------------------
    # Category 3: Mixed Same-Cluster Conditions
    # ---------------------------------------------------------
    def test_mixed_same_cluster_resolution(self):
        """Negation of condition A must NOT suppress affirmed condition B in the same cluster."""
        text = "patient has no hypertension, but suffered a prior stroke"
        res = parse_clinical_conditions_detailed(text)
        assert res["flags"][0] == 2, "Cardio cluster must be scored 2 due to stroke, not wiped out by negated hypertension"
        assert "cardio" in res["explicitly_present"]

        # Structured intake equivalent (exact Phase 1 integer formula: Cardio_ACG = HIBPDX + CHDDX + MIDX + STRKDX)
        struct_res = parse_structured_clinical_conditions({
            "hypertension": {"status": "negated"},
            "stroke": {"status": "affirmed"}
        }, age=60)
        assert struct_res["flags"][0] == 1, "Stroke alone contributes 1 under Phase 1 integer formula (not suppressed by negated hypertension)"
        assert "stroke" in struct_res["conditions_affirmed"]
        assert "hypertension" in struct_res["conditions_negated"]

    # ---------------------------------------------------------
    # Category 4: Family History vs Patient Own History
    # ---------------------------------------------------------
    def test_family_history_vulnerability_and_structured_remedy(self):
        """
        Documented regex limitation: Free text parser falsely attributes family conditions to patient.
        Structured intake must correctly distinguish patient personal status.
        """
        family_text = "mother had severe diabetes and father died of stroke; patient is healthy"
        regex_res = parse_clinical_conditions_detailed(family_text)
        # Demonstrating documented regex limitation: regex falsely triggers on diabetes and stroke
        assert regex_res["flags"][0] > 0 or regex_res["flags"][1] > 0, (
            "Expected known regex limitation: falsely attributes family history keywords to patient"
        )

        # Structured pathway resolves this:
        struct_res = parse_structured_clinical_conditions({
            "diabetes": {"status": "negated", "notes": "family history only, patient negative"},
            "stroke": {"status": "negated", "notes": "paternal death, patient negative"},
            "hypertension": {"status": "negated"}
        }, age=45)
        assert struct_res["flags"][0] == 0
        assert struct_res["flags"][1] == 0
        assert "diabetes" in struct_res["conditions_negated"]
        assert "stroke" in struct_res["conditions_negated"]

    # ---------------------------------------------------------
    # Category 5: Current vs Historical Conditions
    # ---------------------------------------------------------
    def test_current_vs_historical_conditions(self):
        """Historical resolved conditions must not silently escalate acute active comorbidity scores."""
        struct_res = parse_structured_clinical_conditions({
            "asthma": {"status": "historical", "notes": "childhood asthma, resolved at age 12"},
            "hypertension": {"status": "affirmed", "notes": "current on lisinopril"}
        }, age=40)

        # Asthma is historical, hypertension is active
        assert struct_res["flags"][0] == 1  # Cardio affirmed
        assert struct_res["flags"][2] == 0  # Respiratory NOT elevated by historical resolved asthma
        assert "asthma" in struct_res["conditions_historical"]
        assert "hypertension" in struct_res["conditions_affirmed"]

    # ---------------------------------------------------------
    # Category 6: Uncertainty and Hypothetical Conditions
    # ---------------------------------------------------------
    def test_uncertainty_and_rule_out(self):
        """Rule-out and suspected conditions must NOT be counted as confirmed affirmations."""
        struct_res = parse_structured_clinical_conditions({
            "angina": {"status": "uncertain", "notes": "atypical chest pain, ruling out angina"},
            "diabetes": {"status": "affirmed"}
        }, age=55)

        assert struct_res["flags"][0] == 0  # Cardio NOT affirmed
        assert struct_res["flags"][1] == 1  # Diabetes affirmed
        assert "angina" in struct_res["conditions_uncertain"]
        assert "diabetes" in struct_res["conditions_affirmed"]

    # ---------------------------------------------------------
    # Category 7: Misspellings, Ambiguous Terms, and Unparseable Text
    # ---------------------------------------------------------
    def test_misspellings_and_unparseable_inputs(self):
        # Typo free-text
        typo_text = "patient has hypertention and diabtes"
        typo_res = parse_clinical_conditions_detailed(typo_text)
        assert typo_res["input_status"] == "unparseable_or_unmentioned"
        assert typo_res["flags"] == (0, 0, 0, 0, 0, 0)

        # Empty text
        empty_res = parse_clinical_conditions_detailed("")
        assert empty_res["input_status"] == "missing_or_empty"
        assert len(empty_res["unmentioned"]) == 6

        # In strict structured mode, unparseable/missing input returns insufficient_input
        strict_call = calculate_risk({"age": 45, "gender": "female", "diseaseInput": "asdf qwer zxcv"}, require_structured_inputs=True)
        assert strict_call["status"] == "insufficient_input"

    # ---------------------------------------------------------
    # Category 8: Conflicting Statements and Duplicate Mentions
    # ---------------------------------------------------------
    def test_conflicting_statements_and_duplicates(self):
        conflict_text = "patient has hypertension, denies high blood pressure, but reports hypertension"
        res = parse_clinical_conditions_detailed(conflict_text)
        # Affirmation takes clinical precedence over ambiguous negation
        assert res["flags"][0] >= 1
        assert "cardio" in res["explicitly_present"]

    # ---------------------------------------------------------
    # Category 9: Age-Dependent Inapplicable Conditions
    # ---------------------------------------------------------
    def test_age_dependent_applicability_enforcement(self):
        """MEPS survey restrictions: Adult arthritis/CAD asked only for age >= 18; ADHD asked for ages 5-17."""
        # 5-year-old child with adult arthritis input
        pediatric_res = parse_structured_clinical_conditions({
            "arthritis": {"status": "affirmed"},
            "asthma": {"status": "affirmed"}
        }, age=5)

        # Arthritis is age-inapplicable for age 5; Asthma is applicable
        assert pediatric_res["flags"][4] == 0  # MSK not elevated
        assert pediatric_res["flags"][2] == 1  # Respiratory elevated
        assert len(pediatric_res["conditions_inapplicable"]) == 1
        assert pediatric_res["conditions_inapplicable"][0]["condition"] == "arthritis"
        assert pediatric_res["input_status"] == "structured_with_warnings"

        # 60-year-old adult with pediatric ADHD
        adult_res = parse_structured_clinical_conditions({
            "adhd": {"status": "affirmed"},
            "hypertension": {"status": "affirmed"}
        }, age=60)
        assert len(adult_res["conditions_inapplicable"]) == 1
        assert adult_res["conditions_inapplicable"][0]["condition"] == "adhd"
        assert adult_res["flags"][0] == 1

    # ---------------------------------------------------------
    # Category 10: Unknown Fields and Invalid Structured Input
    # ---------------------------------------------------------
    def test_invalid_structured_inputs_and_unknown_fields(self):
        # Invalid status string
        with pytest.raises(ValueError, match="Invalid condition status"):
            parse_structured_clinical_conditions({"hypertension": {"status": "maybe_kinda"}})

        # Unknown condition name
        res = parse_structured_clinical_conditions({
            "alien_syndrome_xyz": {"status": "affirmed"},
            "diabetes": {"status": "affirmed"}
        }, age=50)
        assert "alien_syndrome_xyz" in res["unknown_fields"]
        assert res["input_status"] == "structured_with_warnings"
        assert res["flags"][1] == 1

        # Non-dict / non-list input
        with pytest.raises(ValueError, match="structured_input must be a dictionary or list"):
            parse_structured_clinical_conditions("not a valid struct")

    # ---------------------------------------------------------
    # Category 11: End-to-End calculate_risk Structured Pathway
    # ---------------------------------------------------------
    def test_calculate_risk_structured_end_to_end(self):
        payload = {
            "age": 52,
            "gender": "female",
            "conditions_structured": {
                "hypertension": {"status": "affirmed"},
                "diabetes": {"status": "affirmed"},
                "high_cholesterol": {"status": "affirmed"},
                "asthma": {"status": "negated"}
            }
        }
        output = calculate_risk(payload)
        diag = output["data_parity_diagnostics"]
        assert diag["clinical_condition_parsing"]["intake_mode"] == "structured_clinical_intake"
        assert diag["clinical_condition_parsing"]["is_heuristic_proxy"] is False
        assert "hypertension" in diag["clinical_condition_parsing"]["conditions_affirmed_detail"]
        assert "diabetes" in diag["clinical_condition_parsing"]["conditions_affirmed_detail"]
        assert "high_cholesterol" in diag["clinical_condition_parsing"]["conditions_affirmed_detail"]
        assert output["expected_annual_dollar_expenditure"] > 0
        assert output["relative_expenditure_score"] >= 0

        # Check strict mode with empty structured input
        empty_strict = calculate_risk({
            "age": 30,
            "gender": "male",
            "conditions_structured": {}
        }, require_structured_inputs=True)
        assert empty_strict["status"] == "insufficient_input"
