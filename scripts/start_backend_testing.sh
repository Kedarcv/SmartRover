#!/bin/bash

# SmartRover Backend Testing Script
# Starts all backend services and runs comprehensive tests

set -e

echo "🚀 SmartRover Backend Testing Suite"
echo "=================================="

# Configuration
LOG_DIR="/var/log/smartrover"
PID_DIR="/var/run/smartrover"
TEST_MODE=${1:-"--interactive"}

# Create directories
sudo mkdir -p $LOG_DIR $PID_DIR
sudo chown -R $USER:$USER $LOG_DIR $PID_DIR

# Function to check if service is running
check_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $service_name to start on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
            echo "✅ $service_name is running on port $port"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    
    echo "❌ $service_name failed to start on port $port"
    return 1
}

# Function to start service
start_service() {
    local script_name=$1
    local service_name=$2
    local port=$3
    
    echo "🔄 Starting $service_name..."
    
    # Kill existing process if running
    pkill -f "$script_name" || true
    sleep 2
    
    # Start service in background
    python3 "scripts/$script_name" > "$LOG_DIR/${service_name}.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/${service_name}.pid"
    
    # Check if service started successfully
    if check_service "$service_name" "$port"; then
        echo "✅ $service_name started successfully (PID: $pid)"
        return 0
    else
        echo "❌ Failed to start $service_name"
        return 1
    fi
}

# Function to stop all services
stop_services() {
    echo "🛑 Stopping all services..."
    
    # Stop services gracefully
    for pid_file in $PID_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            local service_name=$(basename "$pid_file" .pid)
            
            if kill -0 $pid 2>/dev/null; then
                echo "🔄 Stopping $service_name (PID: $pid)..."
                kill -TERM $pid
                sleep 2
                
                # Force kill if still running
                if kill -0 $pid 2>/dev/null; then
                    kill -KILL $pid
                fi
            fi
            
            rm -f "$pid_file"
        fi
    done
    
    # Kill any remaining Python processes
    pkill -f "enhanced_server.py" || true
    pkill -f "mobile_api.py" || true
    pkill -f "realtime_streaming.py" || true
    
    echo "✅ All services stopped"
}

# Function to check prerequisites
check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    # Check Python dependencies
    python3 -c "
import sys
required_modules = ['RPi.GPIO', 'cv2', 'sqlite3', 'websockets', 'bluetooth', 'flask', 'requests']
missing_modules = []

for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        missing_modules.append(module)

if missing_modules:
    print(f'❌ Missing modules: {missing_modules}')
    sys.exit(1)
else:
    print('✅ All Python dependencies available')
"
    
    # Check database directory
    if [ ! -d "/var/lib/smartrover" ]; then
        echo "🔄 Creating database directory..."
        sudo mkdir -p /var/lib/smartrover
        sudo chown -R $USER:$USER /var/lib/smartrover
    fi
    
    # Check hardware test
    if [ -f "scripts/test_hardware.py" ]; then
        echo "🔧 Running hardware test..."
        python3 scripts/test_hardware.py || echo "⚠️ Hardware test failed (may be normal in simulation)"
    fi
    
    echo "✅ Prerequisites check complete"
}

# Function to run tests
run_tests() {
    echo "🧪 Running backend test suite..."
    
    if [ -f "scripts/backend_test_suite.py" ]; then
        python3 scripts/backend_test_suite.py
        local test_result=$?
        
        if [ $test_result -eq 0 ]; then
            echo "✅ All tests passed!"
        else
            echo "❌ Some tests failed. Check logs for details."
        fi
        
        return $test_result
    else
        echo "❌ Test suite not found: scripts/backend_test_suite.py"
        return 1
    fi
}

# Function to show service status
show_status() {
    echo "📊 Service Status:"
    echo "=================="
    
    local services=("enhanced_server:5000" "mobile_api:5001" "realtime_streaming:8765")
    
    for service_port in "${services[@]}"; do
        local service_name=$(echo $service_port | cut -d: -f1)
        local port=$(echo $service_port | cut -d: -f2)
        
        if nc -z localhost $port 2>/dev/null; then
            echo "✅ $service_name (port $port) - Running"
        else
            echo "❌ $service_name (port $port) - Not running"
        fi
    done
    
    echo ""
    echo "📁 Log files:"
    ls -la $LOG_DIR/ 2>/dev/null || echo "No log files found"
}

# Function to show logs
show_logs() {
    echo "📋 Recent logs:"
    echo "==============="
    
    for log_file in $LOG_DIR/*.log; do
        if [ -f "$log_file" ]; then
            echo "--- $(basename $log_file) ---"
            tail -n 10 "$log_file"
            echo ""
        fi
    done
}

# Trap to cleanup on exit
trap stop_services EXIT

# Main execution
case "$TEST_MODE" in
    "--test")
        check_prerequisites
        
        # Start services
        start_service "enhanced_server.py" "enhanced_server" "5000"
        start_service "mobile_api.py" "mobile_api" "5001"
        start_service "realtime_streaming.py" "realtime_streaming" "8765"
        
        # Wait a moment for services to fully initialize
        sleep 5
        
        # Run tests
        run_tests
        test_result=$?
        
        # Show final status
        show_status
        
        exit $test_result
        ;;
        
    "--start")
        check_prerequisites
        
        # Start services
        start_service "enhanced_server.py" "enhanced_server" "5000"
        start_service "mobile_api.py" "mobile_api" "5001"
        start_service "realtime_streaming.py" "realtime_streaming" "8765"
        
        show_status
        echo "🎉 All services started successfully!"
        echo "Press Ctrl+C to stop all services"
        
        # Keep script running
        while true; do
            sleep 10
        done
        ;;
        
    "--stop")
        stop_services
        ;;
        
    "--status")
        show_status
        ;;
        
    "--logs")
        show_logs
        ;;
        
    "--interactive"|*)
        echo "SmartRover Backend Testing Options:"
        echo "=================================="
        echo "1. Start services and run tests"
        echo "2. Start services only"
        echo "3. Show service status"
        echo "4. Show recent logs"
        echo "5. Stop all services"
        echo "6. Exit"
        echo ""
        
        while true; do
            read -p "Select option (1-6): " choice
            
            case $choice in
                1)
                    $0 --test
                    break
                    ;;
                2)
                    $0 --start
                    break
                    ;;
                3)
                    show_status
                    ;;
                4)
                    show_logs
                    ;;
                5)
                    stop_services
                    break
                    ;;
                6)
                    echo "Goodbye!"
                    break
                    ;;
                *)
                    echo "Invalid option. Please select 1-6."
                    ;;
            esac
        done
        ;;
esac
