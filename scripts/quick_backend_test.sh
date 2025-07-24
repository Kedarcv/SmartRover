#!/bin/bash

# Quick Backend Test Script
# Performs rapid health checks on all SmartRover backend components

set -e

echo "⚡ SmartRover Quick Backend Test"
echo "==============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local timeout="${3:-5}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    printf "%-30s " "$test_name"
    
    if timeout $timeout bash -c "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to check if port is open
check_port() {
    nc -z localhost $1 2>/dev/null
}

# Function to check HTTP endpoint
check_http() {
    curl -s -f "$1" >/dev/null
}

# Function to check file exists
check_file() {
    [ -f "$1" ]
}

# Function to check directory exists
check_dir() {
    [ -d "$1" ]
}

# Function to check Python module
check_python_module() {
    python3 -c "import $1" 2>/dev/null
}

echo "🔍 Testing System Prerequisites..."
echo "================================="

# Test Python dependencies
run_test "Python RPi.GPIO" "check_python_module RPi.GPIO"
run_test "Python OpenCV" "check_python_module cv2"
run_test "Python SQLite3" "check_python_module sqlite3"
run_test "Python WebSockets" "check_python_module websockets"
run_test "Python Bluetooth" "check_python_module bluetooth"
run_test "Python Flask" "check_python_module flask"
run_test "Python Requests" "check_python_module requests"

echo ""
echo "📁 Testing File System..."
echo "========================="

# Test file system structure
run_test "Scripts directory" "check_dir scripts"
run_test "Enhanced server script" "check_file scripts/enhanced_server.py"
run_test "Vehicle controller" "check_file scripts/vehicle_controller.py"
run_test "Mobile API script" "check_file scripts/mobile_api.py"
run_test "Database directory" "check_dir /var/lib/smartrover"

echo ""
echo "🔌 Testing Service Connectivity..."
echo "=================================="

# Test service ports
run_test "Main API (port 5000)" "check_port 5000"
run_test "Mobile API (port 5001)" "check_port 5001"
run_test "WebSocket (port 8765)" "check_port 8765"

echo ""
echo "🌐 Testing HTTP Endpoints..."
echo "============================"

# Test HTTP endpoints
run_test "Main API health" "check_http http://localhost:5000/health"
run_test "Vehicle status" "check_http http://localhost:5000/api/vehicle-status"
run_test "Mobile API health" "check_http http://localhost:5001/api/health"

echo ""
echo "🗄️ Testing Database..."
echo "======================"

# Test database operations
run_test "Database connection" "python3 -c 'import sqlite3; sqlite3.connect(\"/var/lib/smartrover/mining_data.db\").close()'"
run_test "Waypoints table" "python3 -c 'import sqlite3; c=sqlite3.connect(\"/var/lib/smartrover/mining_data.db\"); c.execute(\"SELECT COUNT(*) FROM waypoints\"); c.close()'"

echo ""
echo "🔧 Testing Hardware Interfaces..."
echo "================================="

# Test hardware interfaces (may fail in simulation)
run_test "GPIO interface" "python3 -c 'import RPi.GPIO; RPi.GPIO.setmode(RPi.GPIO.BCM)'" 10
run_test "Camera interface" "python3 -c 'import cv2; cap=cv2.VideoCapture(0); print(cap.isOpened()); cap.release()'" 10
run_test "I2C interface" "python3 -c 'import smbus; smbus.SMBus(1)'" 5

echo ""
echo "🛡️ Testing Safety Systems..."
echo "============================"

# Test safety endpoints
run_test "Safety status" "check_http http://localhost:5000/api/safety-status"
run_test "Emergency stop" "curl -s -X POST http://localhost:5000/api/vehicle-control -d '{\"command\":\"emergency_stop\"}' -H 'Content-Type: application/json'"

echo ""
echo "📱 Testing Mobile API..."
echo "========================"

# Test mobile API endpoints
run_test "Mobile auth endpoint" "curl -s -X POST http://localhost:5001/api/auth/login -d '{\"username\":\"admin\",\"password\":\"smartrover123\"}' -H 'Content-Type: application/json'"
run_test "Mobile vehicle status" "check_http http://localhost:5001/api/vehicle/status"

echo ""
echo "⚡ Testing WebSocket..."
echo "======================"

# Test WebSocket connection (simplified)
run_test "WebSocket connection" "python3 -c 'import websockets, asyncio; asyncio.get_event_loop().run_until_complete(websockets.connect(\"ws://localhost:8765\"))'" 10

echo ""
echo "📊 Test Summary"
echo "==============="

# Calculate success rate
SUCCESS_RATE=0
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
fi

echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS ✅${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS ❌${NC}"
echo "Success Rate: $SUCCESS_RATE%"

# Overall result
if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 All tests passed! Backend is ready.${NC}"
    exit 0
elif [ $SUCCESS_RATE -ge 80 ]; then
    echo ""
    echo -e "${YELLOW}⚠️ Most tests passed. Some issues detected.${NC}"
    exit 1
else
    echo ""
    echo -e "${RED}❌ Multiple test failures. Backend needs attention.${NC}"
    exit 2
fi
