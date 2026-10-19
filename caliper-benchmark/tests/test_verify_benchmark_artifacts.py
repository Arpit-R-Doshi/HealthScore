#!/usr/bin/env python3
"""
Unit and integration tests for Caliper benchmark artifact semantic verification
caliper-benchmark/verify_benchmark_artifacts.py
"""

import os
import sys
import copy
import json
import shutil
import pytest

# Ensure caliper-benchmark directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from verify_benchmark_artifacts import (
    validate_round_semantics,
    verify_benchmark_semantics,
    compute_transaction_accounting,
    validate_transaction_accounting_metadata,
    verify_live_run
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))


def test_valid_write_round_semantics():
    """Verify that a properly configured write round passes semantic validation."""
    valid_write = {
        'label': 'createPatientRecord-350-tps',
        'txNumber': 1750,
        'rateControl': {'type': 'fixed-rate', 'opts': {'tps': 350}},
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'chaincodeId': 'healthscore',
                'targetFunction': 'createPatientRecord',
                'invokerIdentity': 'HospitalOrgAdmin'
            }
        }
    }
    errors = validate_round_semantics(valid_write)
    assert errors == []


def test_valid_read_round_semantics():
    """Verify that a properly configured read round with pre-seeding passes validation."""
    valid_read = {
        'label': 'getPatientRecord-500-tps',
        'txNumber': 2500,
        'rateControl': {'type': 'fixed-rate', 'opts': {'tps': 500}},
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'chaincodeId': 'healthscore',
                'targetFunction': 'getPatientRecord',
                'invokerIdentity': 'HospitalOrgAdmin',
                'preSeedCount': 50
            }
        }
    }
    errors = validate_round_semantics(valid_read)
    assert errors == []


def test_reject_action_only_configuration():
    """Verify that using 'action' instead of 'targetFunction' fails validation."""
    action_cfg = {
        'label': 'getPatientRecord-500-tps',
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'action': 'getPatientRecord'
            }
        }
    }
    errors = validate_round_semantics(action_cfg)
    assert any("deprecated/invalid argument 'action'" in e for e in errors)
    assert any("Missing mandatory argument 'targetFunction'" in e for e in errors)


def test_reject_missing_target_function():
    """Verify that missing targetFunction is rejected."""
    missing_cfg = {
        'label': 'createPatientRecord-500-tps',
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'chaincodeId': 'healthscore',
                'invokerIdentity': 'HospitalOrgAdmin'
            }
        }
    }
    errors = validate_round_semantics(missing_cfg)
    assert any("Missing mandatory argument 'targetFunction'" in e for e in errors)


def test_reject_label_and_target_function_mismatch():
    """
    Critical defect test: catch when label says read ('getPatientRecord')
    but targetFunction is configured as write ('createPatientRecord').
    """
    mismatched_cfg = {
        'label': 'getPatientRecord-500-tps',
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'chaincodeId': 'healthscore',
                'targetFunction': 'createPatientRecord',
                'invokerIdentity': 'HospitalOrgAdmin'
            }
        }
    }
    errors = validate_round_semantics(mismatched_cfg)
    assert any("Semantic mismatch" in e for e in errors)
    assert any("Label indicates operation 'getPatientRecord'" in e for e in errors)
    assert any("configured targetFunction is 'createPatientRecord'" in e for e in errors)


def test_reject_read_round_without_pre_seeding():
    """Verify that read queries without pre-seeding state fail closed."""
    no_preseed_cfg = {
        'label': 'getPatientRecord-500-tps',
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'chaincodeId': 'healthscore',
                'targetFunction': 'getPatientRecord',
                'invokerIdentity': 'HospitalOrgAdmin'
            }
        }
    }
    errors = validate_round_semantics(no_preseed_cfg)
    assert any("requires pre-seeded ledger state" in e for e in errors)

    zero_preseed_cfg = copy.deepcopy(no_preseed_cfg)
    zero_preseed_cfg['workload']['arguments']['preSeedCount'] = 0
    errors_zero = validate_round_semantics(zero_preseed_cfg)
    assert any("must be integer > 0" in e for e in errors_zero)


def test_reject_missing_invoker_identity():
    """Verify that rounds without invokerIdentity fail validation."""
    no_invoker = {
        'label': 'createPatientRecord-100-tps',
        'workload': {
            'module': 'workload.js',
            'arguments': {
                'chaincodeId': 'healthscore',
                'targetFunction': 'createPatientRecord'
            }
        }
    }
    errors = validate_round_semantics(no_invoker)
    assert any("Missing mandatory argument 'invokerIdentity'" in e for e in errors)


def test_verify_live_run_valid_directory():
    """Verify that the valid 11-round run passes end-to-end audit."""
    target_dir = os.path.join(REPO_ROOT, "caliper-benchmark/results/live/20261018-010200")
    assert verify_live_run(target_dir) is True


def test_verify_live_run_catches_invalid_historical_stress_run():
    """
    Verify that the legacy stress run 20261018-205500_stress_investigation
    is properly rejected by the semantic validator.
    """
    target_dir = os.path.join(REPO_ROOT, "caliper-benchmark/results/live/20261018-205500_stress_investigation")
    assert verify_live_run(target_dir) is False


def test_verify_live_run_corrected_stress_run():
    """
    Verify that the corrected stress run 20261018-230500_stress_investigation
    passes 100% semantic and cross-artifact verification.
    """
    target_dir = os.path.join(REPO_ROOT, "caliper-benchmark/results/live/20261018-230500_stress_investigation")
    assert verify_live_run(target_dir) is True


def test_compute_transaction_accounting_known_8_worker_case():
    """
    Verify the known 8-worker stress case:
    - Configured: 25,500
    - Submitted: 25,480
    - Successful: 25,480
    - Failed: 0
    - Allocation shortfall: 20 proposals due to 8-worker integer division
    - Success rate among submitted: 100.0%
    - Configured proposal completion: 25,480 / 25,500 = ~99.92%
    - Failures: 0 (the 20-proposal shortfall is NOT a transaction failure)
    """
    acct = compute_transaction_accounting(configured=25500, successful=25480, failed=0, workers=8)
    assert acct['configured'] == 25500
    assert acct['submitted'] == 25480
    assert acct['successful'] == 25480
    assert acct['reported_failures'] == 0
    assert acct['allocation_shortfall'] == 20
    assert acct['success_rate_among_submitted_percent'] == 100.0
    assert round(acct['configured_proposal_completion_percent'], 2) == 99.92


def test_compute_transaction_accounting_with_failures_does_not_conflate():
    """
    Verify a synthetic scenario with actual transaction failures:
    - Configured: 25,500
    - Successful: 25,465
    - Failed: 15
    - Submitted: 25,480 (25,465 + 15)
    - Allocation shortfall: 20 (25,500 - 25,480)
    - Reported failures: 15
    - Success rate among submitted: 25,465 / 25,480 = 99.9411%
    - Configured proposal completion: 25,480 / 25,500 = ~99.92%
    Crucially, allocation shortfall remains 20 (not 35), and transaction failures are 15 (not 35).
    Transaction failures and allocation shortfalls are not conflated.
    """
    acct = compute_transaction_accounting(configured=25500, successful=25465, failed=15, workers=8)
    assert acct['configured'] == 25500
    assert acct['submitted'] == 25480
    assert acct['successful'] == 25465
    assert acct['reported_failures'] == 15
    assert acct['allocation_shortfall'] == 20
    assert acct['allocation_shortfall'] != 35
    assert acct['reported_failures'] != 35
    assert round(acct['success_rate_among_submitted_percent'], 2) == 99.94
    assert round(acct['configured_proposal_completion_percent'], 2) == 99.92


def test_compute_transaction_accounting_zero_denominators():
    """Verify safe handling of zero configured or zero submitted proposals without division by zero."""
    acct_zero_cfg = compute_transaction_accounting(configured=0, successful=0, failed=0, workers=8)
    assert acct_zero_cfg['submitted'] == 0
    assert acct_zero_cfg['allocation_shortfall'] == 0
    assert acct_zero_cfg['success_rate_among_submitted_percent'] == 0.0
    assert acct_zero_cfg['configured_proposal_completion_percent'] == 0.0

    acct_zero_sub = compute_transaction_accounting(configured=1000, successful=0, failed=0, workers=4)
    assert acct_zero_sub['submitted'] == 0
    assert acct_zero_sub['allocation_shortfall'] == 1000
    assert acct_zero_sub['success_rate_among_submitted_percent'] == 0.0
    assert acct_zero_sub['configured_proposal_completion_percent'] == 0.0


def test_validate_transaction_accounting_metadata_valid():
    """Verify that valid manifests pass validation."""
    manifest = {
        'total_transactions_configured': 25500,
        'total_transactions_submitted': 25480,
        'total_transactions_successful': 25480,
        'total_transactions_failed': 0,
        'overall_success_rate_percent': 100.0,
        'submitted_transaction_success_rate_percent': 100.0,
        'configured_proposal_completion_percent': 99.92,
        'success_rate_denominator': 'submitted_transactions',
        'transaction_accounting': {
            'configured_round_transactions': 25500,
            'submitted_round_transactions': 25480,
            'shortfall_proposals': 20,
            'reported_failures_among_submitted': 0,
            'submitted_transaction_success_rate_percent': 100.0,
            'configured_proposal_completion_percent': 99.92,
            'success_rate_denominator': 'submitted_transactions',
            'pre_seeding_write_requests': 400,
            'total_recorded_requests_processed': 25880
        },
        'pre_seeding_accounting': {
            'pre_seeding_write_requests': 400,
            'measured_round_transactions': 25480,
            'total_fabric_requests_including_setup': 25880
        }
    }
    valid, errors = validate_transaction_accounting_metadata(
        manifest_data=manifest,
        yaml_total_tx=25500,
        total_html_succ=25480,
        total_html_fail=0,
        workers=8
    )
    assert valid is True
    assert errors == []


def test_validate_transaction_accounting_metadata_catches_inconsistent_fields():
    """Verify that inconsistent nested or top-level accounting fields are flagged as invalid."""
    base_manifest = {
        'total_transactions_configured': 25500,
        'total_transactions_submitted': 25480,
        'total_transactions_successful': 25480,
        'total_transactions_failed': 0,
        'submitted_transaction_success_rate_percent': 100.0,
        'configured_proposal_completion_percent': 99.92,
        'success_rate_denominator': 'submitted_transactions',
        'transaction_accounting': {
            'configured_round_transactions': 25500,
            'submitted_round_transactions': 25480,
            'shortfall_proposals': 20,
            'reported_failures_among_submitted': 0,
            'submitted_transaction_success_rate_percent': 100.0,
            'configured_proposal_completion_percent': 99.92,
            'pre_seeding_write_requests': 400,
            'total_recorded_requests_processed': 25880
        },
        'pre_seeding_accounting': {
            'pre_seeding_write_requests': 400,
            'measured_round_transactions': 25480,
            'total_fabric_requests_including_setup': 25880
        }
    }

    # Case 1: Inconsistent nested shortfall_proposals
    m1 = copy.deepcopy(base_manifest)
    m1['transaction_accounting']['shortfall_proposals'] = 35
    valid1, errors1 = validate_transaction_accounting_metadata(m1, 25500, 25480, 0, 8)
    assert valid1 is False
    assert any("shortfall_proposals (35) != computed allocation shortfall (20)" in e for e in errors1)

    # Case 2: Inconsistent nested reported_failures_among_submitted
    m2 = copy.deepcopy(base_manifest)
    m2['transaction_accounting']['reported_failures_among_submitted'] = 5
    valid2, errors2 = validate_transaction_accounting_metadata(m2, 25500, 25480, 0, 8)
    assert valid2 is False
    assert any("reported_failures_among_submitted (5) != actual failed (0)" in e for e in errors2)

    # Case 3: Inconsistent total_recorded_requests_processed
    m3 = copy.deepcopy(base_manifest)
    m3['transaction_accounting']['total_recorded_requests_processed'] = 25500
    valid3, errors3 = validate_transaction_accounting_metadata(m3, 25500, 25480, 0, 8)
    assert valid3 is False
    assert any("total_recorded_requests_processed (25500) != computed (25880)" in e for e in errors3)

    # Case 4: Inconsistent pre_seeding_accounting total_fabric_requests_including_setup
    m4 = copy.deepcopy(base_manifest)
    m4['pre_seeding_accounting']['total_fabric_requests_including_setup'] = 25480
    valid4, errors4 = validate_transaction_accounting_metadata(m4, 25500, 25480, 0, 8)
    assert valid4 is False
    assert any("total_fabric_requests_including_setup (25480) != computed (25880)" in e for e in errors4)

    # Case 5: Inconsistent pre_seeding write requests between ta and psa
    m5 = copy.deepcopy(base_manifest)
    m5['pre_seeding_accounting']['pre_seeding_write_requests'] = 500
    valid5, errors5 = validate_transaction_accounting_metadata(m5, 25500, 25480, 0, 8)
    assert valid5 is False
    assert any("pre_seeding_write_requests" in e for e in errors5)

    # Case 6: Inconsistent success_rate_denominator
    m6 = copy.deepcopy(base_manifest)
    m6['success_rate_denominator'] = 'configured_proposals'
    valid6, errors6 = validate_transaction_accounting_metadata(m6, 25500, 25480, 0, 8)
    assert valid6 is False
    assert any("success_rate_denominator must be 'submitted_transactions'" in e for e in errors6)


def test_verify_live_run_catches_inconsistent_accounting(tmp_path):
    """
    Ensure inconsistent nested transaction_accounting fields cause end-to-end
    verification failure rather than being displayed as if validated.
    """
    src_dir = os.path.join(REPO_ROOT, "caliper-benchmark/results/live/20261018-230500_stress_investigation")
    dest_dir = tmp_path / "live_run_tampered"
    shutil.copytree(src_dir, dest_dir)

    manifest_path = dest_dir / "run_manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Corrupt the nested shortfall to 999
    data['transaction_accounting']['shortfall_proposals'] = 999
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    # Verification must fail closed
    assert verify_live_run(str(dest_dir)) is False
