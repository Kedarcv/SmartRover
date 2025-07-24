# SmartRover Backend Testing Guide

## System Architecture Overview

The SmartRover backend consists of multiple interconnected services:

### Core Services
- **Enhanced Server** (`enhanced_server.py`) - Main orchestration service
- **Vehicle Controller** (`vehicle_controller.py`) - Autonomous control logic
- **GPS Integration** (`gps_integration.py`) - Location services
- **Path Planning** (`path_planning.py`) - Route optimization
- **Safety Protocols** (`safety_protocols.py`) - Emergency systems
- **Real-time Streaming** (`realtime_streaming.py`) - WebSocket data
- **Mobile API** (`mobile_api.py`) - Mobile app interface

### Communication Protocols
- HTTP REST API (Port 5000)
- WebSocket (Port 8765)
- Mobile API (Port 5001)
- Bluetooth RFCOMM
- WiFi Discovery (UDP/TCP)

## Quick Start Testing

### 1. Prerequisites Check
\`\`\`bash
# Verify Python dependencies
python3 -c "import RPi.GPIO, cv2, sqlite3, websockets, bluetooth; print('All dependencies OK')"

# Check hardware connections
python3 scripts/test_hardware.py

# Verify database setup
ls -la /var/lib/smartrover/mining_data.db
\`\`\`

### 2. Start Backend Services
\`\`\`bash
# Start main server
python3 scripts/enhanced_server.py &

# Start mobile API
python3 scripts/mobile_api.py &

# Start real-time streaming
python3 scripts/realtime_streaming.py &
\`\`\`

### 3. Basic Health Checks
\`\`\`bash
# Test main API
curl http://localhost:5000/health

# Test vehicle status
curl http://localhost:5000/api/vehicle-status

# Test mobile API
curl http://localhost:5001/api/health
\`\`\`

## Comprehensive Testing Scenarios

### Scenario 1: Autonomous Mining Operation
1. Start mining session
2. Monitor waypoint navigation
3. Verify sensor data collection
4. Check safety protocol activation
5. Complete mining and return to dock

### Scenario 2: Emergency Response
1. Trigger emergency stop
2. Verify immediate system shutdown
3. Test manual override capabilities
4. Check safety log entries

### Scenario 3: Multi-Client Connectivity
1. Connect web dashboard
2. Connect mobile app
3. Connect Bluetooth client
4. Verify data synchronization

### Scenario 4: Hardware Failure Simulation
1. Simulate GPS failure
2. Simulate camera disconnection
3. Simulate motor malfunction
4. Verify graceful degradation

## Performance Monitoring

### Key Metrics to Monitor
- CPU usage (should stay < 80%)
- Memory usage (should stay < 70%)
- Network latency (< 100ms)
- Database response time (< 50ms)
- WebSocket connection count
- Active mining sessions

### Log File Locations
- Main server: `/var/log/smartrover/enhanced_server.log`
- Safety system: `/var/log/smartrover/safety.log`
- GPS system: `/var/log/smartrover/gps.log`
- Mobile API: `/var/log/smartrover/mobile_api.log`

## Troubleshooting Guide

### Common Issues
1. **GPIO Permission Denied**: Add user to gpio group
2. **Database Locked**: Check for zombie processes
3. **Camera Not Found**: Verify /dev/video0 exists
4. **Bluetooth Pairing Failed**: Reset Bluetooth adapter
5. **WiFi Discovery Timeout**: Check network configuration

### Debug Commands
\`\`\`bash
# Check running processes
ps aux | grep python3

# Monitor system resources
htop

# Check network connections
netstat -tulpn | grep :5000

# View recent logs
journalctl -u smartrover -f
