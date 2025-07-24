#!/usr/bin/env python3
"""
Comprehensive Backend Test Suite for SmartRover
Tests all backend components and integration points
"""

import asyncio
import json
import requests
import sqlite3
import subprocess
import sys
import time
import websockets
from datetime import datetime
from pathlib import Path

class BackendTestSuite:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.mobile_url = "http://localhost:5001"
        self.websocket_url = "ws://localhost:8765"
        self.test_results = []
        
    def log_test(self, test_name, status, message=""):
        """Log test result"""
        result = {
            'test': test_name,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} {test_name}: {message}")
        
    def test_service_health(self):
        """Test basic service health endpoints"""
        print("\n🔍 Testing Service Health...")
        
        # Test main API health
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                self.log_test("Main API Health", "PASS", "Service responding")
            else:
                self.log_test("Main API Health", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Main API Health", "FAIL", str(e))
            
        # Test mobile API health
        try:
            response = requests.get(f"{self.mobile_url}/api/health", timeout=5)
            if response.status_code == 200:
                self.log_test("Mobile API Health", "PASS", "Service responding")
            else:
                self.log_test("Mobile API Health", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Mobile API Health", "FAIL", str(e))
            
    def test_vehicle_control_api(self):
        """Test vehicle control endpoints"""
        print("\n🚗 Testing Vehicle Control API...")
        
        # Test vehicle status
        try:
            response = requests.get(f"{self.base_url}/api/vehicle-status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'status' in data:
                    self.log_test("Vehicle Status", "PASS", f"Status: {data['status']}")
                else:
                    self.log_test("Vehicle Status", "FAIL", "Missing status field")
            else:
                self.log_test("Vehicle Status", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Vehicle Status", "FAIL", str(e))
            
        # Test vehicle control commands
        test_commands = ["stop", "start_mining", "return_to_dock"]
        for command in test_commands:
            try:
                payload = {"command": command}
                response = requests.post(
                    f"{self.base_url}/api/vehicle-control",
                    json=payload,
                    timeout=5
                )
                if response.status_code == 200:
                    self.log_test(f"Command: {command}", "PASS", "Command accepted")
                else:
                    self.log_test(f"Command: {command}", "FAIL", f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"Command: {command}", "FAIL", str(e))
                
    def test_waypoint_management(self):
        """Test waypoint management endpoints"""
        print("\n📍 Testing Waypoint Management...")
        
        # Test adding waypoint
        try:
            waypoint = {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 10.0,
                "action": "mine"
            }
            response = requests.post(
                f"{self.base_url}/api/waypoints",
                json=waypoint,
                timeout=5
            )
            if response.status_code == 201:
                self.log_test("Add Waypoint", "PASS", "Waypoint created")
            else:
                self.log_test("Add Waypoint", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Add Waypoint", "FAIL", str(e))
            
        # Test getting waypoints
        try:
            response = requests.get(f"{self.base_url}/api/waypoints", timeout=5)
            if response.status_code == 200:
                waypoints = response.json()
                self.log_test("Get Waypoints", "PASS", f"Found {len(waypoints)} waypoints")
            else:
                self.log_test("Get Waypoints", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get Waypoints", "FAIL", str(e))
            
    async def test_websocket_connection(self):
        """Test WebSocket real-time data streaming"""
        print("\n🔌 Testing WebSocket Connection...")
        
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                # Send test message
                test_message = {"type": "ping", "timestamp": time.time()}
                await websocket.send(json.dumps(test_message))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get('type') == 'pong':
                    self.log_test("WebSocket Ping/Pong", "PASS", "Connection working")
                else:
                    self.log_test("WebSocket Ping/Pong", "PASS", f"Received: {data.get('type')}")
                    
        except asyncio.TimeoutError:
            self.log_test("WebSocket Connection", "FAIL", "Connection timeout")
        except Exception as e:
            self.log_test("WebSocket Connection", "FAIL", str(e))
            
    def test_database_operations(self):
        """Test database connectivity and operations"""
        print("\n🗄️ Testing Database Operations...")
        
        db_path = "/var/lib/smartrover/mining_data.db"
        
        try:
            # Test database connection
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Test basic query
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            if tables:
                self.log_test("Database Connection", "PASS", f"Found {len(tables)} tables")
            else:
                self.log_test("Database Connection", "WARN", "No tables found")
                
            # Test waypoints table
            cursor.execute("SELECT COUNT(*) FROM waypoints;")
            waypoint_count = cursor.fetchone()[0]
            self.log_test("Waypoints Table", "PASS", f"{waypoint_count} waypoints")
            
            # Test mining_sessions table
            cursor.execute("SELECT COUNT(*) FROM mining_sessions;")
            session_count = cursor.fetchone()[0]
            self.log_test("Mining Sessions Table", "PASS", f"{session_count} sessions")
            
            conn.close()
            
        except Exception as e:
            self.log_test("Database Operations", "FAIL", str(e))
            
    def test_hardware_interfaces(self):
        """Test hardware interface availability"""
        print("\n🔧 Testing Hardware Interfaces...")
        
        # Test GPIO availability
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            self.log_test("GPIO Interface", "PASS", "GPIO library available")
        except Exception as e:
            self.log_test("GPIO Interface", "FAIL", str(e))
            
        # Test camera availability
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                self.log_test("Camera Interface", "PASS", "Camera available")
                cap.release()
            else:
                self.log_test("Camera Interface", "FAIL", "Camera not accessible")
        except Exception as e:
            self.log_test("Camera Interface", "FAIL", str(e))
            
        # Test I2C availability
        try:
            import smbus
            bus = smbus.SMBus(1)
            self.log_test("I2C Interface", "PASS", "I2C bus available")
        except Exception as e:
            self.log_test("I2C Interface", "FAIL", str(e))
            
    def test_safety_protocols(self):
        """Test safety protocol activation"""
        print("\n🛡️ Testing Safety Protocols...")
        
        # Test emergency stop
        try:
            payload = {"command": "emergency_stop"}
            response = requests.post(
                f"{self.base_url}/api/vehicle-control",
                json=payload,
                timeout=5
            )
            if response.status_code == 200:
                self.log_test("Emergency Stop", "PASS", "Emergency stop activated")
            else:
                self.log_test("Emergency Stop", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Emergency Stop", "FAIL", str(e))
            
        # Test safety status
        try:
            response = requests.get(f"{self.base_url}/api/safety-status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_test("Safety Status", "PASS", f"Safety: {data.get('status', 'unknown')}")
            else:
                self.log_test("Safety Status", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Safety Status", "FAIL", str(e))
            
    def test_mobile_api_authentication(self):
        """Test mobile API authentication"""
        print("\n📱 Testing Mobile API Authentication...")
        
        # Test login endpoint
        try:
            credentials = {"username": "admin", "password": "smartrover123"}
            response = requests.post(
                f"{self.mobile_url}/api/auth/login",
                json=credentials,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if 'token' in data:
                    self.log_test("Mobile Login", "PASS", "Authentication successful")
                    return data['token']
                else:
                    self.log_test("Mobile Login", "FAIL", "No token returned")
            else:
                self.log_test("Mobile Login", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Mobile Login", "FAIL", str(e))
            
        return None
        
    def generate_report(self):
        """Generate test report"""
        print("\n📊 Test Report Summary")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        failed_tests = len([r for r in self.test_results if r['status'] == 'FAIL'])
        warning_tests = len([r for r in self.test_results if r['status'] == 'WARN'])
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Warnings: {warning_tests} ⚠️")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Save detailed report
        report_file = f"/tmp/smartrover_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed report saved to: {report_file}")
        
        return failed_tests == 0
        
    async def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting SmartRover Backend Test Suite")
        print("=" * 50)
        
        # Run synchronous tests
        self.test_service_health()
        self.test_vehicle_control_api()
        self.test_waypoint_management()
        self.test_database_operations()
        self.test_hardware_interfaces()
        self.test_safety_protocols()
        self.test_mobile_api_authentication()
        
        # Run asynchronous tests
        await self.test_websocket_connection()
        
        # Generate report
        success = self.generate_report()
        
        return success

async def main():
    """Main test runner"""
    test_suite = BackendTestSuite()
    
    try:
        success = await test_suite.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
