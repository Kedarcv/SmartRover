#!/usr/bin/env python3
"""
SmartRover Bluetooth Server
Provides Bluetooth connectivity as a failsafe communication method
"""

import json
import time
import threading
import logging
from datetime import datetime
import sys
import os

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
        print("⚠️  No Bluetooth library available")

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
    def __init__(self, port=1):
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = []
        self.authenticated_clients = set()
        
        # Authentication credentials
        self.valid_credentials = {
            "cvlised360@gmail.com": "Cvlised@360",
            "admin@smartrover.com": "admin123",
            "operator@smartrover.com": "operator123"
        }
        
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
                "SmartRover-Control",
                service_id="1e0ca4ea-299d-4335-93eb-27fcfe7fa848",
                service_classes=[bluetooth.SERIAL_PORT_CLASS],
                profiles=[bluetooth.SERIAL_PORT_PROFILE]
            )
            
            self.running = True
            
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"Bluetooth connection from {client_address}")
                    
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
        logger.info("Running Bluetooth server in simulation mode")
        self.running = True
        
        while self.running:
            logger.info("Bluetooth simulation: Waiting for connections...")
            time.sleep(30)
            
    def handle_client(self, client_socket, client_address):
        """Handle individual Bluetooth client"""
        try:
            # Send welcome message
            welcome_msg = {
                "type": "welcome",
                "message": "SmartRover Bluetooth Server",
                "timestamp": datetime.now().isoformat(),
                "requires_auth": True
            }
            client_socket.send(json.dumps(welcome_msg).encode() + b'\n')
            
            authenticated = False
            
            while self.running:
                try:
                    # Receive data
                    data = client_socket.recv(1024)
                    if not data:
                        break
                        
                    try:
                        message = json.loads(data.decode().strip())
                        response = self.process_message(message, client_address, authenticated)
                        
                        if message.get('type') == 'auth' and response.get('success'):
                            authenticated = True
                            self.authenticated_clients.add(client_address)
                            
                        client_socket.send(json.dumps(response).encode() + b'\n')
                        
                    except json.JSONDecodeError:
                        error_response = {
                            "success": False,
                            "error": "Invalid JSON format",
                            "timestamp": datetime.now().isoformat()
                        }
                        client_socket.send(json.dumps(error_response).encode() + b'\n')
                        
                except bluetooth.BluetoothError:
                    break
                    
        except Exception as e:
            logger.error(f"Error handling Bluetooth client {client_address}: {e}")
        finally:
            try:
                client_socket.close()
                if client_address in self.authenticated_clients:
                    self.authenticated_clients.remove(client_address)
                logger.info(f"Bluetooth client {client_address} disconnected")
            except:
                pass
                
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
        elif msg_type == 'ping':
            return {
                "success": True,
                "message": "pong",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"Unknown message type: {msg_type}",
                "timestamp": datetime.now().isoformat()
            }
            
    def handle_authentication(self, message):
        """Handle Bluetooth authentication"""
        username = message.get('username', '')
        password = message.get('password', '')
        
        if username in self.valid_credentials and self.valid_credentials[username] == password:
            logger.info(f"Bluetooth authentication successful for {username}")
            return {
                "success": True,
                "message": "Authentication successful",
                "user": username,
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.warning(f"Bluetooth authentication failed for {username}")
            return {
                "success": False,
                "error": "Invalid credentials",
                "timestamp": datetime.now().isoformat()
            }
            
    def get_vehicle_status(self):
        """Get current vehicle status via Bluetooth"""
        try:
            # Import here to avoid circular imports
            sys.path.append('/opt/smartrover/scripts')
            from vehicle_controller import VehicleController
            
            controller = VehicleController()
            status = controller.get_status()
            
            return {
                "success": True,
                "data": status,
                "timestamp": datetime.now().isoformat(),
                "source": "bluetooth"
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
            
            # Import here to avoid circular imports
            sys.path.append('/opt/smartrover/scripts')
            from vehicle_controller import VehicleController
            
            controller = VehicleController()
            
            if command == 'start':
                result = controller.start()
            elif command == 'stop':
                result = controller.stop()
            elif command == 'emergency_stop':
                result = controller.emergency_stop()
            else:
                return {
                    "success": False,
                    "error": f"Unknown command: {command}",
                    "timestamp": datetime.now().isoformat()
                }
                
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
            
    def stop_server(self):
        """Stop the Bluetooth server"""
        logger.info("Stopping Bluetooth server...")
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        logger.info("Bluetooth server stopped")

def main():
    """Main function"""
    logger.info("Starting SmartRover Bluetooth Server...")
    
    server = BluetoothServer()
    
    try:
        server.start_server()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Bluetooth server error: {e}")
    finally:
        server.stop_server()

if __name__ == "__main__":
    main()
