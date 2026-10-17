"""
HealthScore Subprocess Runner
Bridge between Node.js Express backend and Python ML engine.
Reads JSON from argv[1] and writes pure JSON to stdout.
"""

import sys
import json
import os
import warnings

warnings.filterwarnings('ignore')

# Add the ml_model directory to path so risk_engine can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from risk_engine import calculate_risk

def main():
    try:
        # Load JSON from Node.js spawn command
        if len(sys.argv) < 2:
            print(json.dumps({"error": "Missing input JSON payload"}))
            sys.stdout.flush()
            return

        input_data = json.loads(sys.argv[1])
        result = calculate_risk(input_data)

        output = {
            "risk_score": result['risk_score'],
            "health_score": result['health_score'],
            "premium": result['premium'],
            "high_cost_probability": result.get('high_cost_probability'),
            "confidence": result['confidence_interval'],
            "top_risk_factors": result.get('top_risk_factors', [])
        }

        # Print clean JSON and flush for Node.js
        print(json.dumps(output))
        sys.stdout.flush()

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()