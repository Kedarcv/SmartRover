from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_session import Session
import threading
import time
import json
import logging
import hashlib
import secrets
from vehicle_controller import VehicleController
import os
import psutil
import platform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/vehicle.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = '/tmp/flask_sessions'

Session(app)
CORS(app, supports_credentials=True, origins=['*'])

# Global instances
vehicle_controller = None
vehicle_thread = None

@app.route('/api/system-status', methods=['GET'])
def get_system_status():
    """Get basic system status without authentication - for discovery"""
    return jsonify({
        'success': True,
        'data': {
            'server_running': True,
            'timestamp': time.time(),
            'version': '2.0.0',
            'vehicle_type': 'mining_rover',
            'hostname': platform.node()
        }
    })

@app.route('/api/vehicle-status', methods=['GET'])
def get_vehicle_status():
    """Get current vehicle status"""
    try:
        if vehicle_controller:
            status_data = vehicle_controller.get_status_data()
            
            # Add connection info
            status_data['connection_info'] = {
                'wifi_connected': True,
                'bluetooth_connected': False,  # Simplified for now
                'last_update': time.time()
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
        
        logger.info(f"Executing command: {command}")
        
        if not vehicle_controller:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not initialized'
            }), 500
        
        if command == 'emergency_stop':
            vehicle_controller.emergency_stop()
            logger.critical(f"EMERGENCY STOP activated")
            return jsonify({
                'success': True,
                'message': 'Emergency stop activated'
            })
        elif command == 'start':
            if not vehicle_controller.running:
                start_vehicle_thread()
            return jsonify({
                'success': True,
                'message': 'Vehicle started'
            })
        elif command == 'stop':
            vehicle_controller.running = False
            return jsonify({
                'success': True,
                'message': 'Vehicle stopped'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unknown command'
            }), 400
            
    except Exception as e:
        logger.error(f"Error controlling vehicle: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system-info', methods=['GET'])
def get_system_info():
    """Get comprehensive system information"""
    try:
        # CPU temperature
        temp = get_cpu_temperature()
        
        # Network info
        network_info = get_network_info()
        
        # Disk usage
        disk_usage = psutil.disk_usage('/')
        
        # Memory info
        memory = psutil.virtual_memory()
        
        # System uptime
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time
        
        return jsonify({
            'success': True,
            'data': {
                'platform': platform.platform(),
                'hostname': platform.node(),
                'cpu': {
                    'percent': psutil.cpu_percent(interval=1),
                    'count': psutil.cpu_count(),
                    'temperature': temp
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk_usage.total,
                    'used': disk_usage.used,
                    'free': disk_usage.free,
                    'percent': (disk_usage.used / disk_usage.total) * 100
                },
                'network': network_info,
                'uptime': uptime,
                'vehicle_running': vehicle_controller.running if vehicle_controller else False,
                'bluetooth_clients': 0,  # Simplified for now
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
        lines = int(request.args.get('lines', 100))
        log_file = '/var/log/smartrover/vehicle.log'
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_lines = f.readlines()[-lines:]
            
            return jsonify({
                'success': True,
                'data': {
                    'logs': [line.strip() for line in log_lines],
                    'total_lines': len(log_lines),
                    'timestamp': time.time()
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'logs': ['Log file not found'],
                    'total_lines': 0,
                    'timestamp': time.time()
                }
            })
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_cpu_temperature():
    """Get CPU temperature on Raspberry Pi"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
            return temp
    except:
        return None

def get_network_info():
    """Get network interface information"""
    try:
        interfaces = {}
        net_io = psutil.net_io_counters(pernic=True)
        
        for interface, stats in net_io.items():
            if interface != 'lo':  # Skip loopback
                interfaces[interface] = {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv,
                    'packets_sent': stats.packets_sent,
                    'packets_recv': stats.packets_recv
                }
        
        return interfaces
    except:
        return {}

def start_vehicle_thread():
    """Start vehicle controller in separate thread"""
    global vehicle_thread, vehicle_controller
    
    if vehicle_thread and vehicle_thread.is_alive():
        logger.info("Vehicle thread already running")
        return
    
    def run_vehicle():
        global vehicle_controller
        try:
            if not vehicle_controller:
                vehicle_controller = VehicleController()
            vehicle_controller.main_loop()
        except Exception as e:
            logger.error(f"Vehicle thread error: {e}")
    
    vehicle_thread = threading.Thread(target=run_vehicle, daemon=True)
    vehicle_thread.start()
    logger.info("Vehicle thread started")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '2.0.0',
        'services': {
            'vehicle_controller': vehicle_controller is not None
        }
    })

if __name__ == '__main__':
    logger.info("Starting Standalone Mining Vehicle Server v2.0.0...")
    
    # Create log directory
    os.makedirs('/var/log/smartrover', exist_ok=True)
    os.makedirs('/tmp/flask_sessions', exist_ok=True)
    
    # Initialize vehicle controller
    vehicle_controller = VehicleController()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
