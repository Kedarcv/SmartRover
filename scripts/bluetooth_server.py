#!/usr/bin/env python3
"""
SmartRover Bluetooth Server
Provides Bluetooth connectivity for vehicle control and data streaming
"""

import json
import time
import threading
import logging
import socket
import struct
from datetime import datetime
import sys
import os
import sqlite3

# Try to import bluetooth libraries with fallback
try:
    import bluetooth
    BLUETOOTH_AVAILABLE = True
    print("✅ Using pybluez for Bluetooth")
except ImportError:
    try:
        import bleak
        BLUETOOTH_AVAILABLE = True
        print("✅ Using bleak for Bluetooth")
    except ImportError:
        BLUETOOTH_AVAILABLE = False
        print("⚠️  No Bluetooth library available - running in simulation mode")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/bluetooth.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BluetoothServer:
    def __init__(self, port=1, vehicle_controller=None):
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = []
        self.authenticated_clients = set()
        self.vehicle_controller = vehicle_controller
        self.data_streaming = False
        self.stream_thread = None
        
        # Authentication credentials
        self.valid_credentials = {
            "cvlised360@gmail.com": "Cvlised@360",
            "admin@smartrover.com": "admin123",
            "operator@smartrover.com": "operator123",
            "bluetooth": "smartrover2024"
        }
        
        # Database for logging
        self.database_path = '/var/lib/smartrover/mining_data.db'
        
    def start_server(self):
        """Start the Bluetooth server"""
        if not BLUETOOTH_AVAILABLE:
            logger.error("Bluetooth not available - running in simulation mode")
            self.simulate_bluetooth_server()
            return
            
        try:
            # Create Bluetooth socket
            self.server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_socket.bind(("", self.port))
            self.server_socket.listen(5)
            
            logger.info(f"Bluetooth server listening on port {self.port}")
            
            # Make device discoverable
            bluetooth.advertise_service(
                self.server_socket,
                "SmartRover-Mining-Vehicle",
                service_id="1e0ca4ea-299d-4335-93eb-27fcfe7fa848",
                service_classes=[bluetooth.SERIAL_PORT_CLASS],
                profiles=[bluetooth.SERIAL_PORT_PROFILE],
                description="SmartRover Autonomous Mining Vehicle Control"
            )
            
            self.running = True
            logger.info("🔵 Bluetooth server started - Device is discoverable as 'SmartRover-Mining-Vehicle'")
            
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"🔵 Bluetooth connection from {client_address}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except bluetooth.BluetoothError as e:
                    if self.running:
                        logger.error(f"Bluetooth error: {e}")
                        time.sleep(1)
                        
        except Exception as e:
            logger.error(f"Failed to start Bluetooth server: {e}")
            self.simulate_bluetooth_server()
            
    def simulate_bluetooth_server(self):
        """Simulate Bluetooth server when hardware is not available"""
        logger.info("🔵 Running Bluetooth server in simulation mode")
        self.running = True
        
        while self.running:
            logger.info("🔵 Bluetooth simulation: Waiting for connections...")
            time.sleep(30)
            
    def handle_client(self, client_socket, client_address):
        """Handle individual Bluetooth client"""
        try:
            # Send welcome message
            welcome_msg = {
                "type": "welcome",
                "message": "SmartRover Mining Vehicle Bluetooth Server",
                "timestamp": datetime.now().isoformat(),
                "requires_auth": True,
                "features": [
                    "Real-time vehicle control",
                    "Live sensor data streaming", 
                    "Mining operation management",
                    "System monitoring"
                ]
            }
            self.send_message(client_socket, welcome_msg)
            
            authenticated = False
            client_info = {
                'socket': client_socket,
                'address': client_address,
                'authenticated': False,
                'last_seen': time.time(),
                'data_stream': False
            }
            
            self.clients.append(client_info)
            
            while self.running:
                try:
                    # Receive data with timeout
                    client_socket.settimeout(30.0)
                    data = client_socket.recv(1024)
                    if not data:
                        break
                        
                    try:
                        message = json.loads(data.decode().strip())
                        response = self.process_message(message, client_address, authenticated)
                        
                        if message.get('type') == 'auth' and response.get('success'):
                            authenticated = True
                            client_info['authenticated'] = True
                            self.authenticated_clients.add(client_address)
                            logger.info(f"🔵 Client {client_address} authenticated successfully")
                            
                        self.send_message(client_socket, response)
                        client_info['last_seen'] = time.time()
                        
                    except json.JSONDecodeError:
                        error_response = {
                            "success": False,
                            "error": "Invalid JSON format",
                            "timestamp": datetime.now().isoformat()
                        }
                        self.send_message(client_socket, error_response)
                        
                except socket.timeout:
                    # Send keepalive
                    if authenticated:
                        keepalive = {
                            "type": "keepalive",
                            "timestamp": datetime.now().isoformat(),
                            "server_status": "running"
                        }
                        self.send_message(client_socket, keepalive)
                except bluetooth.BluetoothError:
                    break
                    
        except Exception as e:
            logger.error(f"Error handling Bluetooth client {client_address}: {e}")
        finally:
            try:
                client_socket.close()
                if client_address in self.authenticated_clients:
                    self.authenticated_clients.remove(client_address)
                self.clients = [c for c in self.clients if c['address'] != client_address]
                logger.info(f"🔵 Bluetooth client {client_address} disconnected")
            except:
                pass
                
    def send_message(self, client_socket, message):
        """Send JSON message to client"""
        try:
            json_data = json.dumps(message) + '\n'
            client_socket.send(json_data.encode())
        except Exception as e:
            logger.error(f"Error sending message: {e}")
                
    def process_message(self, message, client_address, authenticated):
        """Process incoming Bluetooth message"""
        msg_type = message.get('type', 'unknown')
        
        if msg_type == 'auth':
            return self.handle_authentication(message)
        elif not authenticated:
            return {
                "success": False,
                "error": "Authentication required",
                "timestamp": datetime.now().isoformat()
            }
        elif msg_type == 'get_status':
            return self.get_vehicle_status()
        elif msg_type == 'control':
            return self.handle_vehicle_control(message)
        elif msg_type == 'start_data_stream':
            return self.start_data_stream(client_address)
        elif msg_type == 'stop_data_stream':
            return self.stop_data_stream(client_address)
        elif msg_type == 'get_waypoints':
            return self.get_waypoints()
        elif msg_type == 'add_waypoint':
            return self.add_waypoint(message)
        elif msg_type == 'ping':
            return {
                "success": True,
                "message": "pong",
                "timestamp": datetime.now().isoformat(),
                "server_time": time.time()
            }
        else:
            return {
                "success": False,
                "error": f"Unknown message type: {msg_type}",
                "timestamp": datetime.now().isoformat()
            }
            
    def handle_authentication(self, message):
        """Handle Bluetooth authentication"""
        username = message.get('username', '').lower().strip()
        password = message.get('password', '')
        
        if username in self.valid_credentials and self.valid_credentials[username] == password:
            logger.info(f"🔵 Bluetooth authentication successful for {username}")
            return {
                "success": True,
                "message": "Authentication successful",
                "user": username,
                "timestamp": datetime.now().isoformat(),
                "permissions": ["control", "monitor", "configure"]
            }
        else:
            logger.warning(f"🔵 Bluetooth authentication failed for {username}")
            return {
                "success": False,
                "error": "Invalid credentials",
                "timestamp": datetime.now().isoformat()
            }
            
    def get_vehicle_status(self):
        """Get current vehicle status via Bluetooth"""
        try:
            if self.vehicle_controller:
                status = self.vehicle_controller.get_status_data()
                return {
                    "success": True,
                    "data": status,
                    "timestamp": datetime.now().isoformat(),
                    "source": "bluetooth"
                }
            else:
                return {
                    "success": False,
                    "error": "Vehicle controller not available",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting vehicle status: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    def handle_vehicle_control(self, message):
        """Handle vehicle control commands via Bluetooth"""
        try:
            command = message.get('command', '')
            
            if not self.vehicle_controller:
                return {
                    "success": False,
                    "error": "Vehicle controller not available",
                    "timestamp": datetime.now().isoformat()
                }
            
            result = None
            if command == 'start_mining':
                self.vehicle_controller.start_mining_operation()
                result = "Mining operation started"
            elif command == 'stop_mining':
                self.vehicle_controller.stop_mining_operation()
                result = "Mining operation stopped"
            elif command == 'return_to_dock':
                self.vehicle_controller.return_to_dock()
                result = "Returning to docking station"
            elif command == 'emergency_stop':
                self.vehicle_controller.emergency_stop()
                result = "Emergency stop activated"
            elif command == 'start':
                self.vehicle_controller.running = True
                result = "Vehicle started"
            elif command == 'stop':
                self.vehicle_controller.running = False
                result = "Vehicle stopped"
            else:
                return {
                    "success": False,
                    "error": f"Unknown command: {command}",
                    "timestamp": datetime.now().isoformat()
                }
                
            # Log command execution
            self.log_command(command, "bluetooth")
                
            return {
                "success": True,
                "message": f"Command '{command}' executed",
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "source": "bluetooth"
            }
            
        except Exception as e:
            logger.error(f"Error executing vehicle control: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_waypoints(self):
        """Get waypoints from database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, x, y, type, status, priority, created_at
                FROM waypoints ORDER BY priority DESC, created_at ASC
            ''')
            
            waypoints = []
            for row in cursor.fetchall():
                waypoints.append({
                    'id': row[0],
                    'name': row[1],
                    'x': row[2],
                    'y': row[3],
                    'type': row[4],
                    'status': row[5],
                    'priority': row[6],
                    'created_at': row[7]
                })
            
            conn.close()
            
            return {
                "success": True,
                "data": waypoints,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def add_waypoint(self, message):
        """Add waypoint via Bluetooth"""
        try:
            waypoint_data = message.get('waypoint', {})
            name = waypoint_data.get('name')
            x = waypoint_data.get('x')
            y = waypoint_data.get('y')
            waypoint_type = waypoint_data.get('type', 'mining')
            priority = waypoint_data.get('priority', 1)
            
            if not all([name, x is not None, y is not None]):
                return {
                    "success": False,
                    "error": "Missing required fields: name, x, y",
                    "timestamp": datetime.now().isoformat()
                }
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO waypoints (name, x, y, type, priority)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, x, y, waypoint_type, priority))
            
            waypoint_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Notify vehicle controller
            if self.vehicle_controller:
                self.vehicle_controller.reload_waypoints()
            
            return {
                "success": True,
                "message": "Waypoint added successfully",
                "waypoint_id": waypoint_id,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def start_data_stream(self, client_address):
        """Start real-time data streaming to client"""
        try:
            # Find client
            client = next((c for c in self.clients if c['address'] == client_address), None)
            if client:
                client['data_stream'] = True
                
                if not self.data_streaming:
                    self.data_streaming = True
                    self.stream_thread = threading.Thread(target=self.data_stream_worker)
                    self.stream_thread.daemon = True
                    self.stream_thread.start()
                
                return {
                    "success": True,
                    "message": "Data streaming started",
                    "stream_rate": "2 Hz",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Client not found",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def stop_data_stream(self, client_address):
        """Stop data streaming to client"""
        try:
            client = next((c for c in self.clients if c['address'] == client_address), None)
            if client:
                client['data_stream'] = False
                
                # Check if any clients still want streaming
                streaming_clients = [c for c in self.clients if c.get('data_stream', False)]
                if not streaming_clients:
                    self.data_streaming = False
                
                return {
                    "success": True,
                    "message": "Data streaming stopped",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Client not found",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def data_stream_worker(self):
        """Worker thread for streaming real-time data"""
        logger.info("🔵 Started Bluetooth data streaming")
        
        while self.data_streaming and self.running:
            try:
                # Get current vehicle data
                if self.vehicle_controller:
                    vehicle_data = self.vehicle_controller.get_status_data()
                    
                    stream_message = {
                        "type": "data_stream",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "position": vehicle_data.get('position', [0, 0]),
                            "heading": vehicle_data.get('heading', 0),
                            "speed": vehicle_data.get('action_data', {}).get('speed', 0),
                            "action": vehicle_data.get('action_data', {}).get('action', 'stop'),
                            "sensors": vehicle_data.get('sensor_data', {}).get('ultrasonic', [0, 0, 0, 0]),
                            "mining_active": vehicle_data.get('system_status', {}).get('mining_active', False),
                            "waypoints_completed": vehicle_data.get('system_status', {}).get('waypoints_completed', 0),
                            "minerals_collected": vehicle_data.get('system_status', {}).get('minerals_collected', 0),
                            "obstacle_detected": vehicle_data.get('action_data', {}).get('obstacle_detected', False)
                        }
                    }
                    
                    # Send to all streaming clients
                    for client in self.clients:
                        if client.get('data_stream', False) and client.get('authenticated', False):
                            try:
                                self.send_message(client['socket'], stream_message)
                            except Exception as e:
                                logger.error(f"Error streaming to client {client['address']}: {e}")
                                client['data_stream'] = False
                
                time.sleep(0.5)  # 2 Hz streaming rate
                
            except Exception as e:
                logger.error(f"Error in data streaming: {e}")
                time.sleep(1)
        
        logger.info("🔵 Stopped Bluetooth data streaming")
    
    def log_command(self, command, source):
        """Log command execution to database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO system_logs (level, message, component)
                VALUES (?, ?, ?)
            ''', ('INFO', f'Command executed: {command}', f'bluetooth_{source}'))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging command: {e}")
    
    def get_connected_clients(self):
        """Get list of connected clients"""
        return [
            {
                'address': str(client['address']),
                'authenticated': client.get('authenticated', False),
                'data_stream': client.get('data_stream', False),
                'last_seen': client.get('last_seen', 0)
            }
            for client in self.clients
        ]
            
    def stop_server(self):
        """Stop the Bluetooth server"""
        logger.info("🔵 Stopping Bluetooth server...")
        self.running = False
        self.data_streaming = False
        
        # Close all client connections
        for client in self.clients:
            try:
                client['socket'].close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        logger.info("🔵 Bluetooth server stopped")

def main():
    """Main function for standalone Bluetooth server"""
    logger.info("🔵 Starting SmartRover Bluetooth Server...")
    
    server = BluetoothServer()
    
    try:
        server.start_server()
    except KeyboardInterrupt:
        logger.info("🔵 Received interrupt signal")
    except Exception as e:
        logger.error(f"🔵 Bluetooth server error: {e}")
    finally:
        server.stop_server()

if __name__ == "__main__":
    main()
