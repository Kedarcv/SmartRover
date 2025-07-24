#!/usr/bin/env python3
"""
SmartRover WiFi Discovery Server
Provides WiFi network discovery and connection management with mDNS service
"""

import socket
import json
import threading
import time
import logging
import subprocess
import netifaces
from zeroconf import ServiceInfo, Zeroconf
import struct
import os
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/wifi_discovery.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WiFiDiscoveryServer:
    def __init__(self, port=8888, vehicle_controller=None):
        self.port = port
        self.vehicle_controller = vehicle_controller
        self.running = False
        self.udp_socket = None
        self.tcp_socket = None
        self.zeroconf = None
        self.service_info = None
        self.connected_clients = {}
        
        # Get network information
        self.hostname = socket.gethostname()
        self.ip_address = self.get_local_ip()
        
        # Create log directory
        os.makedirs('/var/log/smartrover', exist_ok=True)
        
    def get_local_ip(self):
        """Get local IP address"""
        try:
            # Get all network interfaces
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                if interface.startswith('wlan') or interface.startswith('eth'):
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr['addr']
                            if not ip.startswith('127.') and not ip.startswith('169.254'):
                                logger.info(f"🌐 Found IP address {ip} on interface {interface}")
                                return ip
            
            # Fallback method
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            logger.info(f"🌐 Using fallback IP address: {ip}")
            return ip
        except Exception as e:
            logger.error(f"Error getting local IP: {e}")
            return "192.168.1.100"  # Default fallback
    
    def start_server(self):
        """Start WiFi discovery server"""
        logger.info(f"🌐 Starting WiFi Discovery Server on {self.ip_address}:{self.port}")
        
        self.running = True
        
        # Start UDP broadcast listener
        udp_thread = threading.Thread(target=self.start_udp_server, name="UDP-Server")
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP connection server
        tcp_thread = threading.Thread(target=self.start_tcp_server, name="TCP-Server")
        tcp_thread.daemon = True
        tcp_thread.start()
        
        # Start mDNS/Bonjour service
        mdns_thread = threading.Thread(target=self.start_mdns_service, name="mDNS-Service")
        mdns_thread.daemon = True
        mdns_thread.start()
        
        # Start network scanner
        scanner_thread = threading.Thread(target=self.network_scanner, name="Network-Scanner")
        scanner_thread.daemon = True
        scanner_thread.start()
        
        logger.info("🌐 WiFi Discovery Server started successfully")
        logger.info(f"🌐 Device discoverable as: {self.hostname}.local")
        logger.info(f"🌐 UDP Discovery Port: {self.port}")
        logger.info(f"🌐 TCP Control Port: {self.port + 1}")
        
    def start_udp_server(self):
        """Start UDP broadcast server for device discovery"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.bind(('', self.port))
            self.udp_socket.settimeout(1.0)
            
            logger.info(f"🌐 UDP Discovery server listening on port {self.port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(1024)
                    message = data.decode('utf-8').strip()
                    
                    if message == "SMARTROVER_DISCOVERY":
                        # Respond with device information
                        response = {
                            "type": "smartrover_response",
                            "hostname": self.hostname,
                            "ip_address": self.ip_address,
                            "tcp_port": self.port + 1,
                            "http_port": 5000,
                            "device_type": "mining_vehicle",
                            "version": "2.0.0",
                            "status": "online",
                            "features": [
                                "autonomous_mining",
                                "real_time_control",
                                "sensor_monitoring",
                                "waypoint_navigation",
                                "bluetooth_connectivity",
                                "wifi_discovery"
                            ],
                            "timestamp": time.time()
                        }
                        
                        response_data = json.dumps(response).encode('utf-8')
                        self.udp_socket.sendto(response_data, addr)
                        logger.info(f"🌐 Discovery response sent to {addr[0]}:{addr[1]}")
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"UDP server error: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to start UDP server: {e}")
        finally:
            if self.udp_socket:
                self.udp_socket.close()
    
    def start_tcp_server(self):
        """Start TCP server for direct connections"""
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_socket.bind((self.ip_address, self.port + 1))
            self.tcp_socket.listen(5)
            self.tcp_socket.settimeout(1.0)
            
            logger.info(f"🌐 TCP Control server listening on {self.ip_address}:{self.port + 1}")
            
            while self.running:
                try:
                    client_socket, client_address = self.tcp_socket.accept()
                    logger.info(f"🌐 TCP connection from {client_address[0]}:{client_address[1]}")
                    
                    # Add to connected clients
                    client_id = f"{client_address[0]}:{client_address[1]}"
                    self.connected_clients[client_id] = {
                        'socket': client_socket,
                        'address': client_address,
                        'connected_at': time.time(),
                        'last_activity': time.time()
                    }
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_tcp_client,
                        args=(client_socket, client_address, client_id),
                        name=f"TCP-Client-{client_address[0]}"
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"TCP server error: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to start TCP server: {e}")
        finally:
            if self.tcp_socket:
                self.tcp_socket.close()
    
    def handle_tcp_client(self, client_socket, client_address, client_id):
        """Handle TCP client connection"""
        try:
            # Send welcome message
            welcome = {
                "type": "welcome",
                "message": "SmartRover WiFi Control Interface",
                "hostname": self.hostname,
                "ip_address": self.ip_address,
                "timestamp": time.time(),
                "commands": [
                    "get_status",
                    "control_vehicle",
                    "get_waypoints",
                    "add_waypoint",
                    "get_network_info",
                    "scan_networks",
                    "ping"
                ]
            }
            
            self.send_tcp_message(client_socket, welcome)
            
            while self.running and client_id in self.connected_clients:
                try:
                    client_socket.settimeout(30.0)
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    
                    # Update last activity
                    self.connected_clients[client_id]['last_activity'] = time.time()
                    
                    try:
                        message = json.loads(data.decode('utf-8').strip())
                        response = self.process_tcp_message(message, client_address)
                        self.send_tcp_message(client_socket, response)
                        
                    except json.JSONDecodeError:
                        error_response = {
                            "success": False,
                            "error": "Invalid JSON format",
                            "timestamp": time.time()
                        }
                        self.send_tcp_message(client_socket, error_response)
                        
                except socket.timeout:
                    # Send keepalive
                    keepalive = {
                        "type": "keepalive",
                        "timestamp": time.time(),
                        "server_status": "running",
                        "connected_clients": len(self.connected_clients)
                    }
                    self.send_tcp_message(client_socket, keepalive)
                except Exception as e:
                    logger.error(f"Error handling TCP client {client_id}: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"TCP client handler error for {client_id}: {e}")
        finally:
            try:
                client_socket.close()
                if client_id in self.connected_clients:
                    del self.connected_clients[client_id]
                logger.info(f"🌐 TCP client {client_id} disconnected")
            except:
                pass
    
    def send_tcp_message(self, client_socket, message):
        """Send JSON message via TCP"""
        try:
            json_data = json.dumps(message) + '\n'
            client_socket.send(json_data.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error sending TCP message: {e}")
    
    def process_tcp_message(self, message, client_address):
        """Process TCP message"""
        msg_type = message.get('type', 'unknown')
        
        if msg_type == 'get_status':
            return self.get_vehicle_status()
        elif msg_type == 'control_vehicle':
            return self.handle_vehicle_control(message)
        elif msg_type == 'get_network_info':
            return self.get_network_info()
        elif msg_type == 'scan_networks':
            return self.scan_wifi_networks()
        elif msg_type == 'get_waypoints':
            return self.get_waypoints()
        elif msg_type == 'add_waypoint':
            return self.add_waypoint(message)
        elif msg_type == 'ping':
            return {
                "success": True,
                "message": "pong",
                "timestamp": time.time(),
                "server_ip": self.ip_address,
                "client_ip": client_address[0]
            }
        else:
            return {
                "success": False,
                "error": f"Unknown message type: {msg_type}",
                "timestamp": time.time()
            }
    
    def get_vehicle_status(self):
        """Get vehicle status"""
        try:
            if self.vehicle_controller:
                status = self.vehicle_controller.get_status_data()
                status['connectivity'] = {
                    'wifi_clients': len(self.connected_clients),
                    'server_ip': self.ip_address,
                    'hostname': self.hostname
                }
                return {
                    "success": True,
                    "data": status,
                    "timestamp": time.time(),
                    "source": "wifi"
                }
            else:
                return {
                    "success": False,
                    "error": "Vehicle controller not available",
                    "timestamp": time.time()
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def handle_vehicle_control(self, message):
        """Handle vehicle control via WiFi"""
        try:
            command = message.get('command', '')
            
            if not self.vehicle_controller:
                return {
                    "success": False,
                    "error": "Vehicle controller not available",
                    "timestamp": time.time()
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
            else:
                return {
                    "success": False,
                    "error": f"Unknown command: {command}",
                    "timestamp": time.time()
                }
            
            return {
                "success": True,
                "message": f"Command '{command}' executed",
                "result": result,
                "timestamp": time.time(),
                "source": "wifi"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_waypoints(self):
        """Get waypoints from database"""
        try:
            # This would typically connect to the database
            # For now, return mock data
            return {
                "success": True,
                "data": [
                    {"id": 1, "name": "Docking Station", "x": 1000, "y": 1000, "type": "dock", "status": "completed"},
                    {"id": 2, "name": "Mining Point 1", "x": 500, "y": 300, "type": "mining", "status": "pending"}
                ],
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def add_waypoint(self, message):
        """Add waypoint"""
        try:
            waypoint_data = message.get('waypoint', {})
            name = waypoint_data.get('name', 'Unknown')
            x = waypoint_data.get('x', 0)
            y = waypoint_data.get('y', 0)
            
            # This would typically add to database
            logger.info(f"🌐 Waypoint added via WiFi: {name} at ({x}, {y})")
            
            return {
                "success": True,
                "message": f"Waypoint '{name}' added successfully",
                "waypoint_id": int(time.time()),  # Mock ID
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_network_info(self):
        """Get network interface information"""
        try:
            network_info = {}
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                if interface != 'lo':  # Skip loopback
                    try:
                        addrs = netifaces.ifaddresses(interface)
                        interface_info = {
                            'name': interface,
                            'addresses': {}
                        }
                        
                        if netifaces.AF_INET in addrs:
                            interface_info['addresses']['ipv4'] = addrs[netifaces.AF_INET]
                        
                        if netifaces.AF_INET6 in addrs:
                            interface_info['addresses']['ipv6'] = addrs[netifaces.AF_INET6]
                        
                        network_info[interface] = interface_info
                    except Exception as e:
                        logger.error(f"Error getting info for interface {interface}: {e}")
            
            return {
                "success": True,
                "data": {
                    "hostname": self.hostname,
                    "primary_ip": self.ip_address,
                    "interfaces": network_info,
                    "connected_clients": len(self.connected_clients)
                },
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def scan_wifi_networks(self):
        """Scan for available WiFi networks"""
        try:
            networks = []
            
            # Try different scanning methods
            scan_methods = [
                ['iwlist', 'wlan0', 'scan'],
                ['nmcli', 'dev', 'wifi', 'list'],
                ['iw', 'dev', 'wlan0', 'scan']
            ]
            
            for method in scan_methods:
                try:
                    result = subprocess.run(method, capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0 and method[0] == 'iwlist':
                        networks = self.parse_iwlist_output(result.stdout)
                        break
                    elif result.returncode == 0 and method[0] == 'nmcli':
                        networks = self.parse_nmcli_output(result.stdout)
                        break
                    elif result.returncode == 0 and method[0] == 'iw':
                        networks = self.parse_iw_output(result.stdout)
                        break
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"WiFi scan timeout with method: {method[0]}")
                    continue
                except Exception as e:
                    logger.warning(f"WiFi scan failed with method {method[0]}: {e}")
                    continue
            
            return {
                "success": True,
                "data": {
                    "networks": networks,
                    "scan_time": time.time(),
                    "method_used": "system_scan"
                },
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def parse_iwlist_output(self, output):
        """Parse iwlist scan output"""
        networks = []
        lines = output.split('\n')
        current_network = {}
        
        for line in lines:
            line = line.strip()
            if 'ESSID:' in line:
                essid = line.split('ESSID:')[1].strip('"')
                if essid and essid != '':
                    current_network['ssid'] = essid
            elif 'Quality=' in line:
                try:
                    quality_part = line.split('Quality=')[1].split(' ')[0]
                    current_network['quality'] = quality_part
                except:
                    pass
            elif 'Encryption key:' in line:
                encrypted = 'on' in line
                current_network['encrypted'] = encrypted
                
                if current_network.get('ssid'):
                    networks.append(current_network.copy())
                current_network = {}
        
        return networks
    
    def parse_nmcli_output(self, output):
        """Parse nmcli output"""
        networks = []
        lines = output.split('\n')[1:]  # Skip header
        
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 3:
                    networks.append({
                        'ssid': parts[0],
                        'quality': parts[2] if len(parts) > 2 else 'Unknown',
                        'encrypted': '--' not in parts[1] if len(parts) > 1 else True
                    })
        
        return networks
    
    def parse_iw_output(self, output):
        """Parse iw scan output"""
        networks = []
        lines = output.split('\n')
        current_network = {}
        
        for line in lines:
            line = line.strip()
            if 'SSID:' in line:
                ssid = line.split('SSID:')[1].strip()
                if ssid:
                    current_network['ssid'] = ssid
            elif 'signal:' in line:
                signal = line.split('signal:')[1].strip()
                current_network['quality'] = signal
            elif 'Privacy:' in line:
                current_network['encrypted'] = True
                
                if current_network.get('ssid'):
                    networks.append(current_network.copy())
                current_network = {}
        
        return networks
    
    def start_mdns_service(self):
        """Start mDNS/Bonjour service for easy discovery"""
        try:
            self.zeroconf = Zeroconf()
            
            # Create service info
            service_type = "_smartrover._tcp.local."
            service_name = f"{self.hostname}.{service_type}"
            
            properties = {
                'version': '2.0.0',
                'device_type': 'mining_vehicle',
                'features': 'autonomous_mining,real_time_control,sensor_monitoring,bluetooth,wifi',
                'http_port': '5000',
                'tcp_port': str(self.port + 1),
                'udp_port': str(self.port),
                'manufacturer': 'SmartRover Systems',
                'model': 'Mining Vehicle v2.0'
            }
            
            # Convert properties to bytes
            properties_bytes = {}
            for key, value in properties.items():
                properties_bytes[key.encode('utf-8')] = value.encode('utf-8')
            
            self.service_info = ServiceInfo(
                service_type,
                service_name,
                addresses=[socket.inet_aton(self.ip_address)],
                port=self.port + 1,
                properties=properties_bytes,
                server=f"{self.hostname}.local."
            )
            
            self.zeroconf.register_service(self.service_info)
            logger.info(f"🌐 mDNS service registered: {service_name}")
            logger.info(f"🌐 Service discoverable at: {self.hostname}.local:{self.port + 1}")
            
            # Keep the service alive
            while self.running:
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Failed to start mDNS service: {e}")
    
    def network_scanner(self):
        """Periodically scan network for other devices"""
        logger.info("🌐 Network scanner started")
        
        while self.running:
            try:
                # Get network range
                ip_parts = self.ip_address.split('.')
                if len(ip_parts) == 4:
                    network_base = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}"
                    
                    # Scan for other SmartRover devices (simplified)
                    active_devices = []
                    for i in range(1, 255):
                        if not self.running:
                            break
                        
                        target_ip = f"{network_base}.{i}"
                        if target_ip == self.ip_address:
                            continue
                        
                        # Quick ping test
                        try:
                            result = subprocess.run(
                                ['ping', '-c', '1', '-W', '1', target_ip],
                                capture_output=True,
                                timeout=2
                            )
                            if result.returncode == 0:
                                active_devices.append(target_ip)
                        except:
                            pass
                    
                    if active_devices:
                        logger.info(f"🌐 Found {len(active_devices)} active devices on network")
                
                # Sleep for 5 minutes before next scan
                for _ in range(300):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Network scanner error: {e}")
                time.sleep(60)
        
        logger.info("🌐 Network scanner stopped")
    
    def get_connected_clients(self):
        """Get list of connected clients"""
        clients = []
        current_time = time.time()
        
        # Clean up stale connections
        stale_clients = []
        for client_id, client_info in self.connected_clients.items():
            if current_time - client_info['last_activity'] > 300:  # 5 minutes
                stale_clients.append(client_id)
            else:
                clients.append({
                    'id': client_id,
                    'address': client_info['address'][0],
                    'port': client_info['address'][1],
                    'connected_at': client_info['connected_at'],
                    'last_activity': client_info['last_activity'],
                    'duration': current_time - client_info['connected_at']
                })
        
        # Remove stale connections
        for client_id in stale_clients:
            try:
                self.connected_clients[client_id]['socket'].close()
            except:
                pass
            del self.connected_clients[client_id]
            logger.info(f"🌐 Removed stale client: {client_id}")
        
        return clients
    
    def stop_server(self):
        """Stop WiFi discovery server"""
        logger.info("🌐 Stopping WiFi Discovery Server...")
        self.running = False
        
        # Close all client connections
        for client_id, client_info in self.connected_clients.items():
            try:
                client_info['socket'].close()
            except:
                pass
        self.connected_clients.clear()
        
        # Close sockets
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except:
                pass
        
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
        
        # Unregister mDNS service
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
            except:
                pass
        
        logger.info("🌐 WiFi Discovery Server stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"🌐 Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main function for standalone WiFi discovery server"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🌐 Starting SmartRover WiFi Discovery Server...")
    
    server = WiFiDiscoveryServer()
    
    try:
        server.start_server()
        
        # Keep running
        while server.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🌐 Received interrupt signal")
    except Exception as e:
        logger.error(f"🌐 WiFi discovery server error: {e}")
    finally:
        server.stop_server()

if __name__ == "__main__":
    main()
