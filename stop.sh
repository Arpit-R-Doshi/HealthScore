#!/bin/bash
echo "🛑 Pausing HealthScore Network..."
# Stop only containers on the healthscore Fabric network
docker stop $(docker ps -q --filter network=fabric_healthscore)

echo "📉 Stopping Monitoring Stack (Grafana & Prometheus)..."
docker compose -f monitoring/docker-compose.monitor.yml stop

echo "✅ Network and Monitoring paused. Data is safe."
