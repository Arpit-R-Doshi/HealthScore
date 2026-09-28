import sys
import json
import os

# Add the ml_model directory to path so risk_engine can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from risk_engine import calculate_risk

def main():
    try:
        # Load JSON from Node.js spawn command
        if len(sys.argv) < 2:
            return

        input_data = json.loads(sys.argv[1])
        result = calculate_risk(input_data)

        # Output is already in the correct format from risk_engine:
        # { risk_score, health_score, premium, confidence_interval }
        output = {
            "risk_score": result['risk_score'],
            "health_score": result['health_score'],
            "premium": result['premium'],
            "confidence": result['confidence_interval']
        }

        # Print JSON and flush for Node.js
        print(json.dumps(output))
        sys.stdout.flush()

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.stdout.flush()

if __name__ == "__main__":
    main()