#!/usr/bin/env python3
"""
Machine-Checkable Verification Script for HealthScore Caliper Benchmark Artifacts
Audits and reconciles:
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
        print(f"ℹ Note: Caliper partitioned {yaml_total_tx} configured transactions across {workers} workers, yielding {caliper_expected_tx} submitted transactions due to worker integer division.")

    # Check totals in manifest
    assert manifest_data['total_rounds_configured'] == len(yaml_rounds), "Manifest rounds count mismatch"
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

    print(f"\nTotal Configured Txs: {yaml_total_tx}")
    print(f"Total HTML Successful: {total_html_succ}")
    print(f"Total HTML Failed:     {total_html_fail}")

    if mismatches == 0 and total_html_succ in (yaml_total_tx, caliper_expected_tx) and total_html_fail == 0:
        print(f"✓ ALL {len(yaml_rounds)} ROUNDS AND METRICS RECONCILE 100% BYTE-FOR-BYTE ACROSS ALL ARTIFACTS!")
        return True
    else:
        print(f"❌ Found {mismatches} mismatches!")
        return False

if __name__ == '__main__':
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "caliper-benchmark/results/live/20261018-010200"
    success = verify_live_run(target_dir)
    sys.exit(0 if success else 1)
