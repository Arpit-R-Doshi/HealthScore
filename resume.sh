#!/bin/bash
echo "🚀 Resuming HealthScore Network..."
# Restart only containers on the healthscore Fabric network
docker start $(docker ps -aq --filter network=fabric_healthscore)
echo "⏳ Waiting for peers to sync..."
sleep 5

echo "📊 Starting Monitoring Stack (Grafana & Prometheus)..."
docker compose -f monitoring/docker-compose.monitor.yml up -d

echo "✅ Network and Monitoring are back online!"
