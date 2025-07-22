import bluetooth
import threading
import json
import time
import logging
from vehicle_controller import VehicleController
import hashlib
import base64

logger = logging.getLogger(__name__)

class BluetoothServer:
    def __init__(self, vehicle_controller):
        self.vehicle_controller = vehicle_controller
        self.server_sock = None
        self.client_sock = None
        self.running = False
        self.authenticated_clients = set()
        
        # Authentication credentials
        self.valid_credentials = {
            "cvlised360@gmail.com": "Cvlised@360"
        }
        
    def start_server(self):
        """Start Bluetooth server"""
        try:
            self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_sock.bind(("", bluetooth.PORT_ANY))
            self.server_sock.listen(1)
            
            port = self.server_sock.getsockname()[1]
            
            # Advertise service
            bluetooth.advertise_service(
                self.server_sock,
                "MiningVehicleControl",
                service_id="1e0ca4ea-299d-4335-93eb-27fcfe7fa848",
                service_classes=[bluetooth.SERIAL_PORT_CLASS],
                profiles=[bluetooth.SERIAL_PORT_PROFILE]
            )
            
            logger.info(f"Bluetooth server started on port {port}")
            self.running = True
            
            while self.running:
                try:
                    logger.info("Waiting for Bluetooth connection...")
                    client_sock, client_info = self.server_sock.accept()
                    logger.info(f"Bluetooth connection from {client_info}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_sock, client_info),
                        daemon=True
                    )
                    client_thread.start()
                    
                except Exception as e:
                    logger.error(f"Error accepting Bluetooth connection: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to start Bluetooth server: {e}")
    
    def handle_client(self, client_sock, client_info):
        """Handle individual Bluetooth client"""
        client_id = f"{client_info[0]}:{client_info[1]}"
        authenticated = False
        
        try:
            while True:
                data = client_sock.recv(1024).decode('utf-8')
                if not data:
                    break
                
                try:
                    message = json.loads(data)
                    
                    if not authenticated:
                        if message.get('type') == 'auth':
                            email = message.get('email')
                            password = message.get('password')
                            
                            if self.authenticate(email, password):
                                authenticated = True
                                self.authenticated_clients.add(client_id)
                                response = {
                                    'type': 'auth_response',
                                    'success': True,
                                    'message': 'Authentication successful'
                                }
                                logger.info(f"Bluetooth client {client_id} authenticated")
                            else:
                                response = {
                                    'type': 'auth_response',
                                    'success': False,
                                    'message': 'Invalid credentials'
                                }
                        else:
                            response = {
                                'type': 'error',
                                'message': 'Authentication required'
                            }
                    else:
                        # Handle authenticated requests
                        response = self.process_request(message)
                    
                    client_sock.send(json.dumps(response).encode('utf-8'))
                    
                except json.JSONDecodeError:
                    error_response = {
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }
                    client_sock.send(json.dumps(error_response).encode('utf-8'))
                    
        except Exception as e:
            logger.error(f"Error handling Bluetooth client {client_id}: {e}")
        finally:
            if client_id in self.authenticated_clients:
                self.authenticated_clients.remove(client_id)
            client_sock.close()
            logger.info(f"Bluetooth client {client_id} disconnected")
    
    def authenticate(self, email, password):
        """Authenticate user credentials"""
        return email in self.valid_credentials and self.valid_credentials[email] == password
    
    def process_request(self, message):
        """Process authenticated client requests"""
        try:
            request_type = message.get('type')
            
            if request_type == 'get_status':
                return {
                    'type': 'status_response',
                    'success': True,
                    'data': self.vehicle_controller.get_status_data()
                }
            elif request_type == 'control':
                command = message.get('command')
                if command == 'emergency_stop':
                    self.vehicle_controller.emergency_stop()
                elif command == 'start':
                    if not self.vehicle_controller.running:
                        # Start vehicle in separate thread
                        vehicle_thread = threading.Thread(
                            target=self.vehicle_controller.main_loop,
                            daemon=True
                        )
                        vehicle_thread.start()
                elif command == 'stop':
                    self.vehicle_controller.running = False
                
                return {
                    'type': 'control_response',
                    'success': True,
                    'message': f'Command {command} executed'
                }
            else:
                return {
                    'type': 'error',
                    'message': 'Unknown request type'
                }
                
        except Exception as e:
            return {
                'type': 'error',
                'message': str(e)
            }
    
    def stop_server(self):
        """Stop Bluetooth server"""
        self.running = False
        if self.server_sock:
            self.server_sock.close()
        logger.info("Bluetooth server stopped")
