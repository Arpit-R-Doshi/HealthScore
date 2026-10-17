#!/usr/bin/env python3
"""
Unit tests for the Hyperledger Fabric Benchmark Queueing Simulator
caliper-benchmark/simulate_benchmark.py
"""

import os
import sys
import pytest
import numpy as np

# Ensure caliper-benchmark directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from simulate_benchmark import simulate_round, run_workload_simulation, DEFAULT_ROUNDS


def test_output_schema_completeness():
    """Verify all expected keys and metadata fields exist in round simulation output."""
    res = simulate_round('createPatientRecord', offered_tps=100.0, tx_count=1000, n_seeds=10)
    assert 'target_function' in res
    assert 'is_read_only' in res
    assert res['is_read_only'] is False
    assert 'simulated_throughput' in res
    assert 'simulated_avg_latency' in res
    assert 'simulated_max_latency' in res
    assert 'simulated_min_latency' in res
    assert 'transaction_counts' in res
    assert res['simulated_throughput']['median_tps'] > 0
    assert res['simulated_avg_latency']['median_sec'] > 0


def test_deterministic_with_fixed_seed():
    """Verify simulator outputs are 100% deterministic when seeded identically."""
    res1 = simulate_round('createPatientRecord', 200.0, 2000, n_seeds=20, seed_base=12345)
    res2 = simulate_round('createPatientRecord', 200.0, 2000, n_seeds=20, seed_base=12345)
    assert res1['simulated_throughput']['median_tps'] == res2['simulated_throughput']['median_tps']
    assert res1['simulated_avg_latency']['median_sec'] == res2['simulated_avg_latency']['median_sec']
    assert res1['simulated_max_latency']['median_sec'] == res2['simulated_max_latency']['median_sec']


def test_latency_coherence_hierarchy():
    """Verify latency invariant: 0 <= Min <= Avg <= Max across both write and read paths."""
    for fn, tps, txs in [('createPatientRecord', 100.0, 1000), ('createPatientRecord', 1000.0, 10000), ('getPatientRecord', 500.0, 5000)]:
        res = simulate_round(fn, offered_tps=tps, tx_count=txs, n_seeds=25)
        min_l = res['simulated_min_latency']['median_sec']
        avg_l = res['simulated_avg_latency']['median_sec']
        max_l = res['simulated_max_latency']['median_sec']
        assert min_l >= 0.0, f"Min latency {min_l} must be non-negative"
        assert min_l <= avg_l + 1e-4, f"Min latency {min_l} must not exceed Avg {avg_l}"
        assert avg_l <= max_l + 1e-4, f"Avg latency {avg_l} must not exceed Max {max_l}"


def test_write_throughput_saturation_knee():
    """Verify that write throughput scales linearly up to saturation capacity, then caps at capacity."""
    cap = 350.0
    res_50 = simulate_round('createPatientRecord', 50.0, 500, write_capacity=cap, n_seeds=30)
    res_100 = simulate_round('createPatientRecord', 100.0, 1000, write_capacity=cap, n_seeds=30)
    res_200 = simulate_round('createPatientRecord', 200.0, 2000, write_capacity=cap, n_seeds=30)
    res_350 = simulate_round('createPatientRecord', 350.0, 3500, write_capacity=cap, n_seeds=30)
    res_1000 = simulate_round('createPatientRecord', 1000.0, 10000, write_capacity=cap, n_seeds=30)

    # Linear scaling below saturation
    assert 48.0 <= res_50['simulated_throughput']['median_tps'] <= 52.0
    assert 98.0 <= res_100['simulated_throughput']['median_tps'] <= 102.0
    assert 195.0 <= res_200['simulated_throughput']['median_tps'] <= 205.0
    assert 340.0 <= res_350['simulated_throughput']['median_tps'] <= 360.0

    # Saturation ceiling under 1000 TPS offered load
    tps_1000 = res_1000['simulated_throughput']['median_tps']
    assert 330.0 <= tps_1000 <= 370.0, f"Throughput under 1000 TPS must saturate near {cap}, got {tps_1000}"


def test_saturation_queueing_latency_growth():
    """Verify that over-saturation (1000 TPS) causes orderer queue accumulation and latency expansion."""
    res_200 = simulate_round('createPatientRecord', 200.0, 2000, write_capacity=350.0, n_seeds=30)
    res_1000 = simulate_round('createPatientRecord', 1000.0, 10000, write_capacity=350.0, n_seeds=30)

    avg_lat_200 = res_200['simulated_avg_latency']['median_sec']
    avg_lat_1000 = res_1000['simulated_avg_latency']['median_sec']
    assert avg_lat_200 < 0.20, f"Linear regime latency must be sub-second, got {avg_lat_200}"
    assert avg_lat_1000 > 5.0, f"Saturation regime latency must reflect queueing accumulation (>5s), got {avg_lat_1000}"


def test_read_path_independence_and_submillisecond_latency():
    """Verify that read-only queries bypass Raft write queueing and maintain sub-millisecond baseline."""
    res_read = simulate_round('getPatientRecord', 500.0, 5000, read_capacity=1500.0, n_seeds=30)
    assert res_read['is_read_only'] is True
    assert 495.0 <= res_read['simulated_throughput']['median_tps'] <= 505.0
    assert res_read['simulated_avg_latency']['median_sec'] < 0.02, "Read latency must remain minimal"


def test_full_matrix_coverage():
    """Verify simulator handles all 11 configured rounds from DEFAULT_ROUNDS."""
    results = run_workload_simulation(DEFAULT_ROUNDS, n_seeds=5)
    assert len(results) == 11
    names = [r['round_name'] for r in results]
    assert 'createPatientRecord-50-tps' in names
    assert 'createPatientRecord-1000-tps' in names
    assert 'getPatientRecord-500-tps' in names
    assert 'updateHealthScore-200-tps' in names
