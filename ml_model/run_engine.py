import sys
import json
import os
from risk_engine import calculate_risk

def main():
    try:
        # Load JSON from Node.js spawn command
        if len(sys.argv) < 2:
            return

        input_data = json.loads(sys.argv[1])
        result = calculate_risk(input_data)

        # Map Risk Score to UI Metrics (0-100 scale)
        risk = result['risk_score']
        # PDF Logic: 100 - (Risk * Factor)
        health_score = max(0, min(100, 100 - (risk * 4)))
        
        # Insurance Premium Logic (Base 5000)
        premium = 5000 * (1 + (risk * 0.1))

        output = {
            "risk_score": round(risk, 2),
            "health_score": round(health_score, 2),
            "premium": round(premium, 2),
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