#!/bin/bash
# Startup script for mining vehicle

echo "Starting Mining Vehicle System..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "mining_vehicle_env" ]; then
    echo "Virtual environment not found. Please run install_dependencies.py first"
    exit 1
fi

# Activate virtual environment
source mining_vehicle_env/bin/activate

# Check GPIO permissions
echo "Setting up GPIO permissions..."
chown root:gpio /dev/gpiomem
chmod g+rw /dev/gpiomem

# Start the server
echo "Starting Raspberry Pi server..."
python3 raspberry_pi_server.py

echo "Mining vehicle system stopped."
