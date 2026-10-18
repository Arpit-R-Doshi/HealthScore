#!/usr/bin/env python3
"""
Unit and integration tests for Caliper benchmark artifact semantic verification
caliper-benchmark/verify_benchmark_artifacts.py
"""

import os
import sys
import copy
import pytest

# Ensure caliper-benchmark directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from verify_benchmark_artifacts import (
    validate_round_semantics,
    verify_benchmark_semantics,
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

