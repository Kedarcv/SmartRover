#!/bin/bash

# SmartRover Enhanced Server Startup Script
# This script starts all services including WiFi discovery and Bluetooth

set -e

echo "🚀 Starting SmartRover Enhanced Server..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Create necessary directories
mkdir -p /var/log/smartrover
mkdir -p /var/lib/smartrover
mkdir -p /etc/smartrover

# Set permissions
chown -R pi:pi /var/log/smartrover
chown -R pi:pi /var/lib/smartrover

echo "📁 Directories created and permissions set"

# Install Python dependencies if needed
echo "📦 Installing Python dependencies..."
pip3 install -r /opt/smartrover/requirements.txt

# Setup WiFi discovery if not already done
if [ ! -f "/etc/systemd/system/smartrover-wifi-discovery.service" ]; then
    echo "🔧 Setting up WiFi discovery..."
    python3 /opt/smartrover/scripts/wifi_setup.py
fi

# Start the enhanced server
echo "🌐 Starting enhanced server..."
cd /opt/smartrover
python3 scripts/enhanced_server.py

echo "✅ SmartRover Enhanced Server started successfully!"
