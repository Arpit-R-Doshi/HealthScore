#!/usr/bin/env python3
"""
Machine-Checkable Verification Script for HealthScore Caliper Benchmark Artifacts
Audits, reconciles, and validates:
- Semantic workload configuration (explicit targetFunction, label parity, pre-seeding)
- report.html (HTML performance summary table)
- live_benchmark_results.json
- live_benchmark_results.csv
- run_manifest.json
- benchmark_expanded.yaml
"""

import os
import sys
import re
import json
import csv
import yaml

KNOWN_OPERATIONS = [
    'createPatientRecord',
    'updateHealthScore',
    'createPrescription',
    'requestScan',
    'getPatientRecord',
    'getAllPrescriptions',
    'getAllScanOrders'
]

NEEDS_PRE_SEEDING = [
    'updateHealthScore',
    'getPatientRecord',
    'getAllPrescriptions',
    'getAllScanOrders'
]


def validate_round_semantics(round_cfg):
    """
    Validates semantic correctness of an individual benchmark round configuration.
    Returns a list of error strings (empty if valid).
    """
    errors = []
    label = round_cfg.get('label', '')
    workload = round_cfg.get('workload', {})
    args = workload.get('arguments', {})

    if not isinstance(args, dict):
        errors.append(f"Round '{label}': workload.arguments must be a mapping/dict, got {type(args).__name__}")
        return errors

    # Rule 1: Reject deprecated/invalid 'action' argument
    if 'action' in args:
        errors.append(
            f"Round '{label}': Contains deprecated/invalid argument 'action'. "
            f"Benchmark rounds must configure 'targetFunction' explicitly."
        )

    # Rule 2: Require explicit, non-empty 'targetFunction'
    target_fn = args.get('targetFunction')
    if not target_fn:
        errors.append(
            f"Round '{label}': Missing mandatory argument 'targetFunction'. "
            f"A target function must be explicitly specified to prevent silent fallback to write transactions."
        )
    else:
        # Rule 3: Enforce consistency between round label and configured targetFunction
        matched_ops = [op for op in KNOWN_OPERATIONS if op in label]
        if matched_ops:
            expected_op = matched_ops[0]
            if target_fn != expected_op:
                errors.append(
                    f"Round '{label}': Semantic mismatch! Label indicates operation '{expected_op}', "
                    f"but configured targetFunction is '{target_fn}'."
                )

        # Rule 4: Require valid preSeedCount for operations needing pre-existing state
        if target_fn in NEEDS_PRE_SEEDING:
            pre_seed = args.get('preSeedCount')
            if pre_seed is None or not isinstance(pre_seed, int) or pre_seed <= 0:
                errors.append(
                    f"Round '{label}': Target function '{target_fn}' requires pre-seeded ledger state, "
                    f"but 'preSeedCount' is {pre_seed} (must be integer > 0)."
                )

        # Rule 5: Require invokerIdentity
        if not args.get('invokerIdentity'):
            errors.append(f"Round '{label}': Missing mandatory argument 'invokerIdentity'.")

    return errors


def verify_benchmark_semantics(bench_yaml):
    """
    Validates semantic correctness for all rounds in a benchmark YAML dict.
    Returns (is_valid, list_of_errors).
    """
    rounds = bench_yaml.get('test', {}).get('rounds', [])
    all_errors = []
    for r in rounds:
        errs = validate_round_semantics(r)
        all_errors.extend(errs)
    return len(all_errors) == 0, all_errors


def verify_live_run(directory):
    print(f"=== Auditing Benchmark Artifacts in {directory} ===")
    html_file = os.path.join(directory, "report.html")
    json_file = os.path.join(directory, "live_benchmark_results.json")
    csv_file = os.path.join(directory, "live_benchmark_results.csv")
    manifest_file = os.path.join(directory, "run_manifest.json")
    yaml_file = os.path.join(directory, "benchmark_expanded.yaml")

    for f in [html_file, json_file, csv_file, manifest_file, yaml_file]:
        if not os.path.isfile(f):
            print(f"❌ Missing artifact: {f}")
            return False

    # 1. Parse YAML configured rounds
    with open(yaml_file) as f:
        bench_yaml = yaml.safe_load(f)
    yaml_rounds = bench_yaml['test']['rounds']
    yaml_dict = {}
    yaml_total_tx = 0
    for r in yaml_rounds:
        lbl = r['label']
        txs = r['txNumber']
        yaml_dict[lbl] = txs
        yaml_total_tx += txs

    print(f"✓ benchmark_expanded.yaml: {len(yaml_rounds)} rounds, {yaml_total_tx} total transactions configured.")

    # 1b. Semantic Validation of Round Configurations
    is_valid_semantics, semantic_errors = verify_benchmark_semantics(bench_yaml)
    if not is_valid_semantics:
        print("\n❌ SEMANTIC VALIDATION FAILED:")
        for err in semantic_errors:
            print(f"  - {err}")
        return False
    print(f"✓ Semantic verification passed: all {len(yaml_rounds)} rounds have valid explicit targetFunction and parameters.")

    # 2. Parse HTML Summary Table
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    tables = re.findall(r'<table[^>]*>(.*?)</table>', html_content, re.DOTALL)
    if not tables:
        print("❌ No tables found in report.html")
        return False

    summary_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tables[0], re.DOTALL)
    headers = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<th[^>]*>(.*?)</th>', summary_rows[0], re.DOTALL)]
    
    html_data = []
    html_dict = {}
    for r in summary_rows[1:]:
        cols = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)]
        if cols and len(cols) == len(headers):
            row_dict = dict(zip(headers, cols))
            html_data.append(row_dict)
            html_dict[row_dict['Name']] = row_dict

    print(f"✓ report.html: {len(html_data)} unique rounds in summary table (ignoring {len(tables)-1} round-detail tables).")

    # 3. Parse JSON Results
    with open(json_file) as f:
        json_data = json.load(f)
    json_dict = {r['Name']: r for r in json_data}
    print(f"✓ live_benchmark_results.json: {len(json_data)} rounds recorded.")

    # 4. Parse CSV Results
    with open(csv_file) as f:
        csv_reader = csv.DictReader(f)
        csv_data = list(csv_reader)
    csv_dict = {r['Name']: r for r in csv_data}
    print(f"✓ live_benchmark_results.csv: {len(csv_data)} rounds recorded.")

    # 5. Parse Manifest
    with open(manifest_file) as f:
        manifest_data = json.load(f)
    manifest_rounds = manifest_data.get('round_metrics', [])
    manifest_dict = {r['Name']: r for r in manifest_rounds}
    print(f"✓ run_manifest.json: {len(manifest_rounds)} round metrics recorded.")

    workers = bench_yaml.get('test', {}).get('workers', {}).get('number', 1)
    caliper_expected_tx = sum((r.get('txNumber', 0) // workers) * workers if r.get('txNumber') else 0 for r in yaml_rounds)
    if caliper_expected_tx != yaml_total_tx:
        shortfall_initial = yaml_total_tx - caliper_expected_tx
        print(f"ℹ Note: Caliper partitioned {yaml_total_tx} configured transactions across {workers} workers, yielding {caliper_expected_tx} submitted transactions due to worker integer division (shortfall: {shortfall_initial} unsubmitted proposals).")

    # Check totals in manifest
    assert manifest_data['total_rounds_configured'] == len(yaml_rounds), "Manifest rounds count mismatch"
    if 'total_transactions_configured' in manifest_data:
        assert manifest_data['total_transactions_configured'] == yaml_total_tx, "Manifest configured tx mismatch"
    assert manifest_data['total_transactions_submitted'] in (yaml_total_tx, caliper_expected_tx), "Manifest submitted tx mismatch"
    assert manifest_data['total_transactions_successful'] in (yaml_total_tx, caliper_expected_tx), "Manifest successful tx mismatch"
    assert manifest_data['total_transactions_failed'] == 0, "Manifest failed tx mismatch"

    # Cross-Reconciliation Check across all artifacts
    print("\n--- Cross-Reconciling Round-by-Round Metrics ---")
    mismatches = 0
    total_html_succ = 0
    total_html_fail = 0

    for lbl, cfg_tx in yaml_dict.items():
        if lbl not in html_dict:
            print(f"❌ Round '{lbl}' present in YAML but missing from HTML report!")
            mismatches += 1
            continue
        h = html_dict[lbl]
        j = json_dict.get(lbl)
        c = csv_dict.get(lbl)
        m = manifest_dict.get(lbl)

        succ = int(h['Succ'])
        fail = int(h['Fail'])
        send_rate = float(h['Send Rate (TPS)'])
        throughput = float(h['Throughput (TPS)'])
        avg_lat = float(h['Avg Latency (s)'])
        max_lat = float(h['Max Latency (s)'])
        min_lat = float(h['Min Latency (s)'])

        total_html_succ += succ
        total_html_fail += fail

        # Check configured vs actual
        caliper_round_expected = (cfg_tx // workers) * workers
        if succ + fail not in (cfg_tx, caliper_round_expected):
            print(f"❌ {lbl}: Total txs ({succ+fail}) != configured ({cfg_tx}) or worker-partitioned ({caliper_round_expected})")
            mismatches += 1

        # Check parity across JSON, CSV, Manifest
        for source_name, src in [("JSON", j), ("CSV", c), ("Manifest", m)]:
            if not src:
                print(f"❌ {lbl}: Missing in {source_name}")
                mismatches += 1
                continue
            if src['Succ'] != h['Succ'] or src['Fail'] != h['Fail']:
                print(f"❌ {lbl}: Succ/Fail mismatch in {source_name}")
                mismatches += 1
            if src['Send Rate (TPS)'] != h['Send Rate (TPS)']:
                print(f"❌ {lbl}: Send rate mismatch in {source_name}")
                mismatches += 1
            if src['Throughput (TPS)'] != h['Throughput (TPS)']:
                print(f"❌ {lbl}: Throughput mismatch in {source_name}")
                mismatches += 1
            if src['Avg Latency (s)'] != h['Avg Latency (s)']:
                print(f"❌ {lbl}: Avg latency mismatch in {source_name}")
                mismatches += 1
            if src['Max Latency (s)'] != h['Max Latency (s)']:
                print(f"❌ {lbl}: Max latency mismatch in {source_name}")
                mismatches += 1
            if src['Min Latency (s)'] != h['Min Latency (s)']:
                print(f"❌ {lbl}: Min latency mismatch in {source_name}")
                mismatches += 1

        if m and 'targetFunction' in m:
            yaml_round = next((r for r in yaml_rounds if r['label'] == lbl), {})
            expected_fn = yaml_round.get('workload', {}).get('arguments', {}).get('targetFunction')
            if expected_fn and m['targetFunction'] != expected_fn:
                print(f"❌ {lbl}: Manifest targetFunction '{m['targetFunction']}' != YAML targetFunction '{expected_fn}'")
                mismatches += 1

    shortfall = yaml_total_tx - total_html_succ
    print("\n--- Transaction Accounting Summary ---")
    print(f"Configured Benchmark-Round Txs:  {yaml_total_tx}")
    print(f"Submitted/Recorded Round Txs:    {total_html_succ}")
    if shortfall > 0:
        print(f"Per-Worker Allocation Shortfall: {shortfall} txs (Caliper integer division across {workers} workers)")
    else:
        print(f"Per-Worker Allocation Shortfall: 0 txs (full 1:1 allocation across {workers} workers)")
    print(f"Reported Failures (Submitted):   {total_html_fail}")

    # Inspect manifest transaction / pre-seeding accounting if present
    pre_seeding_accounting = manifest_data.get('pre_seeding_accounting') or manifest_data.get('transaction_accounting')
    if isinstance(pre_seeding_accounting, dict) and pre_seeding_accounting.get('pre_seeding_write_requests'):
        pre_seed_tx = pre_seeding_accounting['pre_seeding_write_requests']
        total_requests = total_html_succ + pre_seed_tx
        print(f"Pre-Seeding Setup Write Txs:     {pre_seed_tx}")
        print(f"Total Testbed Workload Requests: {total_requests}")

    if mismatches == 0 and total_html_succ in (yaml_total_tx, caliper_expected_tx) and total_html_fail == 0:
        if shortfall > 0:
            print(f"\n✓ ALL {len(yaml_rounds)} ROUNDS AND SUBMITTED METRICS RECONCILE 100% BYTE-FOR-BYTE ACROSS ALL ARTIFACTS!")
            print(f"  (Accounting: {total_html_succ} submitted of {yaml_total_tx} configured due to {workers}-worker integer allocation; {shortfall} shortfall; 0 reported failures among submitted transactions).")
        else:
            print(f"\n✓ ALL {len(yaml_rounds)} ROUNDS AND METRICS RECONCILE 100% BYTE-FOR-BYTE ACROSS ALL ARTIFACTS!")
        return True
    else:
        print(f"\n❌ Found {mismatches} mismatches!")
        return False


if __name__ == '__main__':
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "caliper-benchmark/results/live/20261018-010200"
    success = verify_live_run(target_dir)
    sys.exit(0 if success else 1)
