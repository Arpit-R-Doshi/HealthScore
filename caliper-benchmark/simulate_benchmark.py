#!/usr/bin/env python3
"""
Hyperledger Fabric Queueing & Performance Simulator
HealthScore Consortium Benchmark Modeling

This module implements a stochastic fluid-queueing performance model with
Raft consensus jitter for Hyperledger Fabric transactions, modeling
consensus-backed writes and local state queries across arbitrary offered loads.

Calibration target:
- Historical Caliper baseline (commit 944fb0d, 8 rounds, 24,500 txs)

Held-out comparison:
- Live isolated Caliper benchmark (run 20261018-010200, 11 rounds, 31,500 txs)

IMPORTANT PROVENANCE DISCLAIMER:
Simulation outputs are SYNTHETIC queueing model estimates, NOT empirical
benchmark measurements. They must never be conflated with live Caliper outputs.
Synthetic seed variations represent a model sensitivity envelope, NOT an
empirical confidence interval.
"""

import os
import sys
import json
import csv
import argparse
import numpy as np

def simulate_round(
    target_function,
    offered_tps,
    tx_count,
    write_capacity=350.1,
    read_capacity=1200.0,
    base_write_latency=0.035,
    base_read_latency=0.002,
    block_batch_timeout=2.0,
    max_batch_size=10,
    n_seeds=100,
    seed_base=42
):
    """
    Simulate a single benchmark round across multiple random seeds.
    
    Parameters:
    -----------
    target_function: str
        Chaincode function ('createPatientRecord', 'updateHealthScore', etc.)
    offered_tps: float
        Offered transaction rate (TPS)
    tx_count: int
        Total number of transactions configured for the round
    write_capacity: float
        Max committed write throughput capacity (TPS) under Raft consensus
    read_capacity: float
        Max local query throughput capacity (QPS)
    base_write_latency: float
        Base network + endorsement latency for writes (seconds)
    base_read_latency: float
        Base query execution latency (seconds)
    block_batch_timeout: float
        Fabric orderer batch timeout (seconds)
    max_batch_size: int
        Fabric orderer max block message count
    n_seeds: int
        Number of synthetic simulation repetitions
    seed_base: int
        PRNG seed base
        
    Returns:
    --------
    dict containing median and sensitivity envelope (5th-95th percentile).
    """
    is_read = target_function in ['getPatientRecord', 'getAllPrescriptions', 'getAllScanOrders']
    duration_nominal = tx_count / offered_tps

    throughputs = []
    avg_latencies = []
    max_latencies = []
    min_latencies = []
    successful_txs = []
    failed_txs = []

    for s in range(n_seeds):
        rng = np.random.default_rng(seed_base + s * 1009)
        
        if is_read:
            # Read-only path: Local peer leveldb/couchdb lookup (no Raft ordering)
            # Service capacity has log-normal jitter
            eff_capacity = read_capacity * rng.lognormal(mean=0.0, sigma=0.05)
            achieved_tps = min(offered_tps, eff_capacity)
            
            # Base query latency with micro-jitter
            base_lat = base_read_latency * rng.lognormal(mean=0.0, sigma=0.15)
            
            # If offered_tps > eff_capacity, queueing occurs
            if offered_tps > eff_capacity:
                queue_time = (offered_tps - eff_capacity) * duration_nominal / (2.0 * eff_capacity)
                avg_lat = base_lat + queue_time
                max_lat = base_lat + queue_time * 2.0
            else:
                avg_lat = base_lat
                max_lat = base_lat * rng.uniform(1.5, 3.0)
            min_lat = max(0.0005, base_lat * 0.5)
            succ = tx_count
            fail = 0

        else:
            # Write path: Execute-Order-Validate lifecycle with Raft consensus
            # Service capacity jitter
            eff_capacity = write_capacity * rng.lognormal(mean=0.0, sigma=0.04)
            
            # Block-cutting delay component
            # If offered rate is fast, blocks cut on max_batch_size (tx_interval * max_batch_size)
            # If slow, blocks cut on block_batch_timeout
            avg_batch_fill_time = min(block_batch_timeout, max_batch_size / max(1.0, offered_tps))
            block_delay = avg_batch_fill_time / 2.0
            
            base_lat = (base_write_latency + block_delay) * rng.lognormal(mean=0.0, sigma=0.08)

            if offered_tps <= eff_capacity:
                # Linear operating regime: No sustained queueing
                # M/M/1-like mild queueing near capacity
                utilization = min(0.98, offered_tps / eff_capacity)
                mild_queue = (utilization / (1.0 - utilization)) * (1.0 / eff_capacity) * 0.1
                
                achieved_tps = offered_tps * rng.uniform(0.998, 1.002)
                avg_lat = base_lat + mild_queue
                max_lat = avg_lat * rng.uniform(2.0, 3.5)
                min_lat = base_lat * 0.5
            else:
                # Saturation regime: Orderer queue accumulation
                # Queue grows at (offered - capacity)
                achieved_tps = eff_capacity
                saturation_queue_avg = ((offered_tps - eff_capacity) * duration_nominal) / (2.0 * eff_capacity)
                avg_lat = base_lat + saturation_queue_avg
                max_lat = base_lat + saturation_queue_avg * 1.8
                min_lat = base_lat * 0.8
                
            succ = tx_count
            fail = 0

        throughputs.append(float(achieved_tps))
        avg_latencies.append(float(avg_lat))
        max_latencies.append(float(max_lat))
        min_latencies.append(float(min_lat))
        successful_txs.append(int(succ))
        failed_txs.append(int(fail))

    return {
        'target_function': target_function,
        'is_read_only': is_read,
        'offered_tps': offered_tps,
        'tx_count': tx_count,
        'n_synthetic_seeds': n_seeds,
        'simulated_throughput': {
            'median_tps': round(float(np.median(throughputs)), 2),
            'p5_tps': round(float(np.percentile(throughputs, 5)), 2),
            'p95_tps': round(float(np.percentile(throughputs, 95)), 2),
            'std_tps': round(float(np.std(throughputs)), 2)
        },
        'simulated_avg_latency': {
            'median_sec': round(float(np.median(avg_latencies)), 4),
            'p5_sec': round(float(np.percentile(avg_latencies, 5)), 4),
            'p95_sec': round(float(np.percentile(avg_latencies, 95)), 4),
            'std_sec': round(float(np.std(avg_latencies)), 4)
        },
        'simulated_max_latency': {
            'median_sec': round(float(np.median(max_latencies)), 4),
            'p5_sec': round(float(np.percentile(max_latencies, 5)), 4),
            'p95_sec': round(float(np.percentile(max_latencies, 95)), 4)
        },
        'simulated_min_latency': {
            'median_sec': round(float(np.median(min_latencies)), 4)
        },
        'transaction_counts': {
            'total_configured': tx_count,
            'simulated_successful': int(np.median(successful_txs)),
            'simulated_failed': int(np.median(failed_txs))
        }
    }


def run_workload_simulation(config_rounds, write_cap=350.1, read_cap=1200.0, n_seeds=100):
    """
    Simulate the complete benchmark workload matrix.
    """
    sim_results = []
    for rnd in config_rounds:
        name = rnd['name']
        fn = rnd['function']
        tps = rnd['offered_tps']
        txs = rnd['tx_count']
        
        res = simulate_round(
            target_function=fn,
            offered_tps=tps,
            tx_count=txs,
            write_capacity=write_cap,
            read_capacity=read_cap,
            n_seeds=n_seeds
        )
        res['round_name'] = name
        sim_results.append(res)
    return sim_results


DEFAULT_ROUNDS = [
    {'name': 'createPatientRecord-50-tps',   'function': 'createPatientRecord', 'offered_tps': 50.0,   'tx_count': 500},
    {'name': 'createPatientRecord-100-tps',  'function': 'createPatientRecord', 'offered_tps': 100.0,  'tx_count': 1000},
    {'name': 'createPatientRecord-200-tps',  'function': 'createPatientRecord', 'offered_tps': 200.0,  'tx_count': 2000},
    {'name': 'createPatientRecord-350-tps',  'function': 'createPatientRecord', 'offered_tps': 350.0,  'tx_count': 3500},
    {'name': 'createPatientRecord-1000-tps', 'function': 'createPatientRecord', 'offered_tps': 1000.0, 'tx_count': 10000},
    {'name': 'updateHealthScore-200-tps',    'function': 'updateHealthScore',    'offered_tps': 200.0,  'tx_count': 2000},
    {'name': 'createPrescription-200-tps',   'function': 'createPrescription',   'offered_tps': 200.0,  'tx_count': 2000},
    {'name': 'requestScan-200-tps',          'function': 'requestScan',          'offered_tps': 200.0,  'tx_count': 2000},
    {'name': 'getPatientRecord-100-tps',     'function': 'getPatientRecord',     'offered_tps': 100.0,  'tx_count': 1000},
    {'name': 'getPatientRecord-250-tps',     'function': 'getPatientRecord',     'offered_tps': 250.0,  'tx_count': 2500},
    {'name': 'getPatientRecord-500-tps',     'function': 'getPatientRecord',     'offered_tps': 500.0,  'tx_count': 5000},
]


def main():
    parser = argparse.ArgumentParser(description="Hyperledger Fabric Caliper Performance Simulator")
    parser.add_argument('--output-dir', default=None, help="Directory to save simulation results")
    parser.add_argument('--seeds', type=int, default=100, help="Number of PRNG seeds per round")
    parser.add_argument('--write-cap', type=float, default=350.1, help="Calibrated write saturation capacity (TPS)")
    parser.add_argument('--read-cap', type=float, default=1200.0, help="Calibrated read capacity (QPS)")
    args = parser.parse_args()

    out_dir = args.output_dir
    if out_dir is None:
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = f"caliper-benchmark/results/simulated/{ts}"

    os.makedirs(out_dir, exist_ok=True)
    print(f"Running Hyperledger Fabric queueing simulation ({args.seeds} seeds per scenario)...")
    results = run_workload_simulation(DEFAULT_ROUNDS, write_cap=args.write_cap, read_cap=args.read_cap, n_seeds=args.seeds)

    # Save JSON
    json_path = os.path.join(out_dir, "simulation_results.json")
    with open(json_path, "w") as f:
        json.dump({
            "evidence_class": "SYNTHETIC_SIMULATION_ESTIMATES",
            "model_type": "Stochastic Fluid-Queueing Performance Model with Raft Consensus Jitter",
            "calibration_target": "caliper-benchmark/report.html (commit 944fb0d, 8 rounds, 24,500 txs)",
            "held_out_comparison": "caliper-benchmark/results/live/20261018-010200 (11 rounds, 31,500 txs)",
            "parameters": {
                "write_saturation_capacity_tps": args.write_cap,
                "read_capacity_qps": args.read_cap,
                "seeds_per_round": args.seeds
            },
            "disclaimer": "SYNTHETIC ESTIMATES ONLY. Do not treat as empirical Caliper observations. Seed variations represent sensitivity envelopes, not empirical confidence intervals.",
            "results": results
        }, f, indent=2)

    # Save CSV
    csv_path = os.path.join(out_dir, "simulation_results.csv")
    csv_rows = []
    for r in results:
        csv_rows.append({
            'Round_Name': r['round_name'],
            'Function': r['target_function'],
            'Offered_TPS': r['offered_tps'],
            'Configured_Tx': r['tx_count'],
            'Simulated_Throughput_Median_TPS': r['simulated_throughput']['median_tps'],
            'Simulated_Throughput_P5_TPS': r['simulated_throughput']['p5_tps'],
            'Simulated_Throughput_P95_TPS': r['simulated_throughput']['p95_tps'],
            'Simulated_Avg_Latency_Median_s': r['simulated_avg_latency']['median_sec'],
            'Simulated_Avg_Latency_P5_s': r['simulated_avg_latency']['p5_sec'],
            'Simulated_Avg_Latency_P95_s': r['simulated_avg_latency']['p95_sec'],
            'Simulated_Max_Latency_Median_s': r['simulated_max_latency']['median_sec']
        })

    with open(csv_path, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"✓ Simulation completed across {len(results)} rounds.")
    print(f"✓ Results saved to:\n  - {json_path}\n  - {csv_path}")

if __name__ == '__main__':
    main()
