from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import time
import json
import logging
from vehicle_controller import VehicleController
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global vehicle controller instance
vehicle_controller = None
vehicle_thread = None

@app.route('/api/vehicle-status', methods=['GET'])
def get_vehicle_status():
    """Get current vehicle status"""
    try:
        if vehicle_controller:
            status_data = vehicle_controller.get_status_data()
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
        
        if not vehicle_controller:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not initialized'
            }), 500
        
        if command == 'emergency_stop':
            vehicle_controller.emergency_stop()
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

@app.route('/api/map-data', methods=['GET'])
def get_map_data():
    """Get current map data"""
    try:
        if vehicle_controller:
            map_data = vehicle_controller.slam_mapper.export_map_data()
            return jsonify({
                'success': True,
                'data': map_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not initialized'
            }), 500
    except Exception as e:
        logger.error(f"Error getting map data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sensor-data', methods=['GET'])
def get_sensor_data():
    """Get current sensor readings"""
    try:
        if vehicle_controller:
            readings = vehicle_controller.sensor_array.read_all_sensors()
            return jsonify({
                'success': True,
                'data': {
                    'ultrasonic': readings,
                    'timestamp': time.time(),
                    'camera_available': vehicle_controller.camera_available
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not initialized'
            }), 500
    except Exception as e:
        logger.error(f"Error getting sensor data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system-info', methods=['GET'])
def get_system_info():
    """Get system information"""
    try:
        import psutil
        import platform
        
        return jsonify({
            'success': True,
            'data': {
                'platform': platform.platform(),
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'temperature': get_cpu_temperature(),
                'uptime': time.time() - psutil.boot_time(),
                'vehicle_running': vehicle_controller.running if vehicle_controller else False
            }
        })
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
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

def start_vehicle_thread():
    """Start vehicle controller in separate thread"""
    global vehicle_thread, vehicle_controller
    
    if vehicle_thread and vehicle_thread.is_alive():
        logger.info("Vehicle thread already running")
        return
    
    def run_vehicle():
        global vehicle_controller
        try:
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
        'vehicle_running': vehicle_controller.running if vehicle_controller else False
    })

@app.route('/')
def serve_dashboard():
    """Serve dashboard (if you want to serve static files)"""
    return jsonify({
        'message': 'Mining Vehicle Server',
        'version': '1.0.0',
        'endpoints': [
            '/api/vehicle-status',
            '/api/vehicle-control',
            '/api/map-data',
            '/api/sensor-data',
            '/api/system-info',
            '/health'
        ]
    })

if __name__ == '__main__':
    logger.info("Starting Mining Vehicle Server...")
    
    # Start vehicle controller thread
    start_vehicle_thread()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
