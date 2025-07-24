#!/usr/bin/env python3
"""
Enhanced SmartRover Mining Vehicle Server
Handles vehicle control, waypoint navigation, mining operations, Bluetooth and WiFi connectivity
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
import time
import json
import logging
import os
import psutil
import platform
from pathlib import Path
from vehicle_controller import VehicleController
from bluetooth_server import BluetoothServer
from wifi_discovery_server import WiFiDiscoveryServer
import sqlite3
from datetime import datetime
import eventlet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/enhanced_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Use eventlet for better WebSocket performance
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smartrover_secret_key_2024'
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Global instances
vehicle_controller = None
bluetooth_server = None
wifi_discovery_server = None
vehicle_thread = None
bluetooth_thread = None
wifi_thread = None
database_path = '/var/lib/smartrover/mining_data.db'

# Real-time data streaming
streaming_clients = set()
data_stream_thread = None
stream_active = False

class MiningDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the mining database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Waypoints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waypoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                type TEXT DEFAULT 'mining',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL
            )
        ''')
        
        # Mining sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mining_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP NULL,
                waypoints_completed INTEGER DEFAULT 0,
                total_distance REAL DEFAULT 0,
                minerals_collected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # System logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT DEFAULT 'server'
            )
        ''')
        
        # Connection logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                connection_type TEXT NOT NULL,
                client_address TEXT,
                event_type TEXT NOT NULL,
                details TEXT
            )
        ''')
        
        # Insert docking station if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO waypoints (id, name, x, y, type, status, priority)
            VALUES (1, 'Docking Station', 1000, 1000, 'dock', 'completed', 0)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Enhanced mining database initialized")

# Initialize database
db = MiningDatabase(database_path)

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info(f"🌐 WebSocket client connected: {request.sid}")
    log_connection_event('websocket', request.sid, 'connect', 'Client connected via WebSocket')
    
    # Send welcome message
    emit('welcome', {
        'message': 'Connected to SmartRover Enhanced Server',
        'timestamp': time.time(),
        'features': [
            'Real-time vehicle control',
            'Live sensor data streaming',
            'Mining operation management',
            'Bluetooth connectivity',
            'WiFi discovery'
        ]
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info(f"🌐 WebSocket client disconnected: {request.sid}")
    log_connection_event('websocket', request.sid, 'disconnect', 'Client disconnected from WebSocket')
    
    # Remove from streaming clients
    streaming_clients.discard(request.sid)

@socketio.on('join_data_stream')
def handle_join_stream():
    """Client wants to receive real-time data"""
    streaming_clients.add(request.sid)
    join_room('data_stream')
    logger.info(f"🌐 Client {request.sid} joined data stream")
    
    # Start streaming if not already active
    start_data_streaming()
    
    emit('stream_status', {
        'streaming': True,
        'rate': '2 Hz',
        'timestamp': time.time()
    })

@socketio.on('leave_data_stream')
def handle_leave_stream():
    """Client wants to stop receiving real-time data"""
    streaming_clients.discard(request.sid)
    leave_room('data_stream')
    logger.info(f"🌐 Client {request.sid} left data stream")
    
    emit('stream_status', {
        'streaming': False,
        'timestamp': time.time()
    })

@socketio.on('vehicle_command')
def handle_vehicle_command(data):
    """Handle vehicle control commands via WebSocket"""
    try:
        command = data.get('command')
        logger.info(f"🌐 WebSocket command received: {command} from {request.sid}")
        
        if not vehicle_controller:
            emit('command_response', {
                'success': False,
                'error': 'Vehicle controller not initialized',
                'timestamp': time.time()
            })
            return
        
        result = execute_vehicle_command(command)
        emit('command_response', result)
        
        # Broadcast command to all clients
        socketio.emit('vehicle_event', {
            'type': 'command_executed',
            'command': command,
            'result': result,
            'timestamp': time.time()
        }, room='data_stream')
        
    except Exception as e:
        logger.error(f"Error handling WebSocket command: {e}")
        emit('command_response', {
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        })

# HTTP API Routes
@app.route('/api/vehicle-status', methods=['GET'])
def get_vehicle_status():
    """Get current vehicle status"""
    try:
        if vehicle_controller:
            status_data = vehicle_controller.get_status_data()
            
            # Add connectivity information
            status_data['connectivity'] = {
                'bluetooth_clients': len(bluetooth_server.clients) if bluetooth_server else 0,
                'websocket_clients': len(streaming_clients),
                'wifi_clients': len(wifi_discovery_server.connected_clients) if wifi_discovery_server else 0,
                'wifi_discoverable': wifi_discovery_server.running if wifi_discovery_server else False,
                'server_ip': wifi_discovery_server.ip_address if wifi_discovery_server else 'unknown',
                'hostname': wifi_discovery_server.hostname if wifi_discovery_server else 'unknown'
            }
            
            return jsonify({
                'success': True,
                'data': status_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not initialized'
            }), 500
    except Exception as e:
        logger.error(f"Error getting vehicle status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/vehicle-control', methods=['POST'])
def control_vehicle():
    """Control vehicle remotely"""
    try:
        data = request.get_json()
        command = data.get('command')
        
        result = execute_vehicle_command(command)
        
        # Broadcast to WebSocket clients
        socketio.emit('vehicle_event', {
            'type': 'command_executed',
            'command': command,
            'result': result,
            'source': 'http',
            'timestamp': time.time()
        }, room='data_stream')
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error controlling vehicle: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/connectivity-status', methods=['GET'])
def get_connectivity_status():
    """Get connectivity status for all interfaces"""
    try:
        bluetooth_clients = []
        if bluetooth_server:
            bluetooth_clients = bluetooth_server.get_connected_clients()
        
        wifi_info = {}
        wifi_clients = []
        if wifi_discovery_server:
            wifi_info = {
                'ip_address': wifi_discovery_server.ip_address,
                'hostname': wifi_discovery_server.hostname,
                'udp_port': wifi_discovery_server.port,
                'tcp_port': wifi_discovery_server.port + 1,
                'mdns_enabled': wifi_discovery_server.zeroconf is not None
            }
            wifi_clients = wifi_discovery_server.get_connected_clients()
        
        return jsonify({
            'success': True,
            'data': {
                'bluetooth': {
                    'enabled': bluetooth_server.running if bluetooth_server else False,
                    'clients': bluetooth_clients,
                    'discoverable': True
                },
                'wifi': {
                    'enabled': wifi_discovery_server.running if wifi_discovery_server else False,
                    'info': wifi_info,
                    'clients': wifi_clients
                },
                'websocket': {
                    'enabled': True,
                    'clients': len(streaming_clients),
                    'streaming_active': stream_active
                },
                'timestamp': time.time()
            }
        })
    except Exception as e:
        logger.error(f"Error getting connectivity status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/network-scan', methods=['GET'])
def scan_networks():
    """Scan for available WiFi networks"""
    try:
        if wifi_discovery_server:
            result = wifi_discovery_server.scan_wifi_networks()
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'error': 'WiFi discovery server not available'
            }), 500
    except Exception as e:
        logger.error(f"Error scanning networks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/waypoints', methods=['GET'])
def get_waypoints():
    """Get all waypoints"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, x, y, type, status, priority, created_at, completed_at
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
                'created_at': row[7],
                'completed_at': row[8]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': waypoints
        })
    except Exception as e:
        logger.error(f"Error getting waypoints: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/waypoints', methods=['POST'])
def add_waypoint():
    """Add a new waypoint"""
    try:
        data = request.get_json()
        name = data.get('name')
        x = data.get('x')
        y = data.get('y')
        waypoint_type = data.get('type', 'mining')
        priority = data.get('priority', 1)
        
        if not all([name, x is not None, y is not None]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: name, x, y'
            }), 400
        
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO waypoints (name, x, y, type, priority)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, x, y, waypoint_type, priority))
        
        waypoint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Notify vehicle controller of new waypoint
        if vehicle_controller:
            vehicle_controller.reload_waypoints()
        
        log_system_event('INFO', f'New waypoint added: {name} at ({x}, {y})')
        
        # Broadcast to WebSocket clients
        socketio.emit('waypoint_event', {
            'type': 'waypoint_added',
            'waypoint': {
                'id': waypoint_id,
                'name': name,
                'x': x,
                'y': y,
                'type': waypoint_type,
                'priority': priority
            },
            'timestamp': time.time()
        }, room='data_stream')
        
        return jsonify({
            'success': True,
            'data': {
                'id': waypoint_id,
                'message': 'Waypoint added successfully'
            }
        })
    except Exception as e:
        logger.error(f"Error adding waypoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system-info', methods=['GET'])
def get_system_info():
    """Get system information"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'platform': platform.platform(),
                'hostname': platform.node(),
                'cpu': {
                    'percent': psutil.cpu_percent(),
                    'count': psutil.cpu_count(),
                    'temperature': get_cpu_temperature()
                },
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available,
                    'percent': psutil.virtual_memory().percent,
                    'used': psutil.virtual_memory().used
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'free': psutil.disk_usage('/').free,
                    'percent': psutil.disk_usage('/').percent
                },
                'uptime': time.time() - psutil.boot_time(),
                'vehicle_running': vehicle_controller.running if vehicle_controller else False,
                'services': {
                    'bluetooth': bluetooth_server.running if bluetooth_server else False,
                    'wifi_discovery': wifi_discovery_server.running if wifi_discovery_server else False,
                    'websocket': True,
                    'data_streaming': stream_active
                },
                'network': {
                    'ip_address': wifi_discovery_server.ip_address if wifi_discovery_server else 'unknown',
                    'hostname': wifi_discovery_server.hostname if wifi_discovery_server else 'unknown'
                },
                'timestamp': time.time()
            }
        })
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get system logs"""
    try:
        lines = int(request.args.get('lines', 50))
        
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, level, message, component
            FROM system_logs ORDER BY timestamp DESC LIMIT ?
        ''', (lines,))
        
        logs = []
        for row in cursor.fetchall():
            logs.append(f"[{row[0]}] {row[1]} - {row[3]}: {row[2]}")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {'logs': logs}
        })
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'services': {
            'vehicle_controller': vehicle_controller is not None,
            'bluetooth_server': bluetooth_server.running if bluetooth_server else False,
            'wifi_discovery': wifi_discovery_server.running if wifi_discovery_server else False,
            'database': check_database_health(),
            'websocket': True
        },
        'version': '2.0.0'
    })

@app.route('/api/system-status', methods=['GET'])
def get_system_status():
    """Get basic system status for discovery"""
    return jsonify({
        'success': True,
        'data': {
            'server_running': True,
            'timestamp': time.time(),
            'version': '2.0.0',
            'device_type': 'mining_vehicle',
            'hostname': platform.node(),
            'features': [
                'autonomous_mining',
                'real_time_control',
                'bluetooth_connectivity',
                'wifi_discovery',
                'websocket_streaming'
            ]
        }
    })

@app.route('/')
def serve_info():
    """Serve API information"""
    return jsonify({
        'message': 'SmartRover Enhanced Mining Vehicle Server',
        'version': '2.0.0',
        'status': 'operational',
        'connectivity': {
            'http_api': True,
            'websocket': True,
            'bluetooth': bluetooth_server.running if bluetooth_server else False,
            'wifi_discovery': wifi_discovery_server.running if wifi_discovery_server else False
        },
        'endpoints': [
            '/api/vehicle-status',
            '/api/vehicle-control',
            '/api/connectivity-status',
            '/api/network-scan',
            '/api/waypoints',
            '/api/system-info',
            '/api/logs',
            '/health'
        ]
    })

# Helper Functions
def execute_vehicle_command(command):
    """Execute vehicle command"""
    try:
        if not vehicle_controller:
            return {
                'success': False,
                'error': 'Vehicle controller not initialized'
            }
            
        if command == 'emergency_stop':
            vehicle_controller.emergency_stop()
            log_system_event('CRITICAL', 'Emergency stop activated')
            return {
                'success': True,
                'message': 'Emergency stop activated'
            }
        elif command == 'start_mining':
            vehicle_controller.start_mining_operation()
            log_system_event('INFO', 'Mining operation started')
            return {
                'success': True,
                'message': 'Mining operation started'
            }
        elif command == 'stop_mining':
            vehicle_controller.stop_mining_operation()
            log_system_event('INFO', 'Mining operation stopped')
            return {
                'success': True,
                'message': 'Mining operation stopped'
            }
        elif command == 'return_to_dock':
            vehicle_controller.return_to_dock()
            log_system_event('INFO', 'Return to dock initiated')
            return {
                'success': True,
                'message': 'Returning to docking station'
            }
        elif command == 'start':
            if not vehicle_controller.running:
                start_vehicle_thread()
            return {
                'success': True,
                'message': 'Vehicle started'
            }
        elif command == 'stop':
            vehicle_controller.running = False
            return {
                'success': True,
                'message': 'Vehicle stopped'
            }
        else:
            return {
                'success': False,
                'error': 'Unknown command'
            }
    except Exception as e:
        logger.error(f"Error executing vehicle command: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def get_cpu_temperature():
    """Get CPU temperature on Raspberry Pi"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
            return temp
    except:
        return None

def log_system_event(level, message, component='server'):
    """Log system event to database"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO system_logs (level, message, component)
            VALUES (?, ?, ?)
        ''', (level, message, component))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging system event: {e}")

def log_connection_event(connection_type, client_address, event_type, details):
    """Log connection event to database"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO connection_logs (connection_type, client_address, event_type, details)
            VALUES (?, ?, ?, ?)
        ''', (connection_type, client_address, event_type, details))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging connection event: {e}")

def start_vehicle_thread():
    """Start vehicle controller in separate thread"""
    global vehicle_thread, vehicle_controller
    
    if vehicle_thread and vehicle_thread.is_alive():
        logger.info("Vehicle thread already running")
        return
    
    def run_vehicle():
        global vehicle_controller
        try:
            vehicle_controller = VehicleController(database_path)
            vehicle_controller.main_loop()
        except Exception as e:
            logger.error(f"Vehicle thread error: {e}")
            log_system_event('ERROR', f'Vehicle thread error: {e}', 'vehicle')
    
    vehicle_thread = threading.Thread(target=run_vehicle, daemon=True)
    vehicle_thread.start()
    logger.info("Vehicle thread started")
    log_system_event('INFO', 'Vehicle controller started', 'vehicle')

def start_bluetooth_thread():
    """Start Bluetooth server in separate thread"""
    global bluetooth_thread, bluetooth_server
    
    if bluetooth_thread and bluetooth_thread.is_alive():
        logger.info("Bluetooth thread already running")
        return
    
    def run_bluetooth():
        global bluetooth_server
        try:
            bluetooth_server = BluetoothServer(vehicle_controller)
            bluetooth_server.start_server()
        except Exception as e:
            logger.error(f"Bluetooth thread error: {e}")
            log_system_event('ERROR', f'Bluetooth thread error: {e}', 'bluetooth')
    
    bluetooth_thread = threading.Thread(target=run_bluetooth, daemon=True)
    bluetooth_thread.start()
    logger.info("Bluetooth thread started")
    log_system_event('INFO', 'Bluetooth server started', 'bluetooth')

def start_wifi_thread():
    """Start WiFi discovery server in separate thread"""
    global wifi_thread, wifi_discovery_server
    
    if wifi_thread and wifi_thread.is_alive():
        logger.info("WiFi discovery thread already running")
        return
    
    def run_wifi():
        global wifi_discovery_server
        try:
            wifi_discovery_server = WiFiDiscoveryServer(vehicle_controller=vehicle_controller)
            wifi_discovery_server.start_server()
        except Exception as e:
            logger.error(f"WiFi discovery thread error: {e}")
            log_system_event('ERROR', f'WiFi discovery thread error: {e}', 'wifi')
    
    wifi_thread = threading.Thread(target=run_wifi, daemon=True)
    wifi_thread.start()
    logger.info("WiFi discovery thread started")
    log_system_event('INFO', 'WiFi discovery server started', 'wifi')

def start_data_streaming():
    """Start real-time data streaming"""
    global data_stream_thread, stream_active
    
    if stream_active:
        logger.info("Data streaming already active")
        return
    
    def stream_data():
        global stream_active
        stream_active = True
        while stream_active and streaming_clients:
            try:
                if vehicle_controller:
                    status_data = vehicle_controller.get_status_data()
                    status_data['connectivity'] = {
                        'bluetooth_clients': len(bluetooth_server.clients) if bluetooth_server else 0,
                        'websocket_clients': len(streaming_clients),
                        'wifi_clients': len(wifi_discovery_server.connected_clients) if wifi_discovery_server else 0,
                        'wifi_discoverable': wifi_discovery_server.running if wifi_discovery_server else False
                    }
                    
                    socketio.emit('real_time_data', {
                        'data': status_data,
                        'timestamp': time.time()
                    }, room='data_stream')
                
                time.sleep(0.5)  # Stream at 2 Hz
            except Exception as e:
                logger.error(f"Error streaming data: {e}")
                time.sleep(1)
        
        stream_active = False
        logger.info("Data streaming stopped")
    
    data_stream_thread = threading.Thread(target=stream_data, daemon=True)
    data_stream_thread.start()
    logger.info("Data streaming started")
    log_system_event('INFO', 'Data streaming started', 'server')

def check_database_health():
    """Check database connectivity"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        return True
    except:
        return False

if __name__ == '__main__':
    logger.info("🚀 Starting SmartRover Enhanced Mining Vehicle Server v2.0...")
    log_system_event('INFO', 'Server starting up', 'server')
    
    # Create log directory
    os.makedirs('/var/log/smartrover', exist_ok=True)
    
    # Start vehicle controller thread
    start_vehicle_thread()
    
    # Start Bluetooth server thread
    start_bluetooth_thread()
    
    # Start WiFi discovery server thread
    start_wifi_thread()
    
    # Start Flask server with SocketIO
    try:
        logger.info("🌐 Starting web server on 0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        log_system_event('CRITICAL', f'Server startup failed: {e}', 'server')
