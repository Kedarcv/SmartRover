#!/usr/bin/env python3
"""
Standalone SmartRover Vehicle Server
This server runs independently and provides API endpoints for vehicle control
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import json
import logging
import os
import psutil
import platform
from pathlib import Path
from vehicle_controller import VehicleController
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/standalone.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global vehicle controller instance
vehicle_controller = None
vehicle_thread = None
database_path = '/var/lib/smartrover/mining_data.db'

def ensure_database():
    """Ensure database exists and is initialized"""
    os.makedirs(os.path.dirname(database_path), exist_ok=True)
    
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            component TEXT DEFAULT 'server'
        )
    ''')
    
    # Insert default docking station if not exists
    cursor.execute('''
        INSERT OR IGNORE INTO waypoints (id, name, x, y, type, status, priority)
        VALUES (1, 'Docking Station', 1000, 1000, 'dock', 'completed', 0)
    ''')
    
    conn.commit()
    conn.close()

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
            log_system_event('CRITICAL', 'Emergency stop activated')
            return jsonify({
                'success': True,
                'message': 'Emergency stop activated'
            })
        elif command == 'start_mining':
            vehicle_controller.start_mining_operation()
            log_system_event('INFO', 'Mining operation started')
            return jsonify({
                'success': True,
                'message': 'Mining operation started'
            })
        elif command == 'stop_mining':
            vehicle_controller.stop_mining_operation()
            log_system_event('INFO', 'Mining operation stopped')
            return jsonify({
                'success': True,
                'message': 'Mining operation stopped'
            })
        elif command == 'return_to_dock':
            vehicle_controller.return_to_dock()
            log_system_event('INFO', 'Return to dock initiated')
            return jsonify({
                'success': True,
                'message': 'Returning to docking station'
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

@app.route('/api/waypoints/<int:waypoint_id>', methods=['DELETE'])
def delete_waypoint(waypoint_id):
    """Delete a waypoint"""
    try:
        if waypoint_id == 1:  # Protect docking station
            return jsonify({
                'success': False,
                'error': 'Cannot delete docking station'
            }), 400
        
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM waypoints WHERE id = ?', (waypoint_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Waypoint not found'
            }), 404
        
        conn.commit()
        conn.close()
        
        # Notify vehicle controller
        if vehicle_controller:
            vehicle_controller.reload_waypoints()
        
        log_system_event('INFO', f'Waypoint {waypoint_id} deleted')
        
        return jsonify({
            'success': True,
            'message': 'Waypoint deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting waypoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/mining-sessions', methods=['GET'])
def get_mining_sessions():
    """Get mining session history"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, start_time, end_time, waypoints_completed, 
                   total_distance, minerals_collected, status
            FROM mining_sessions ORDER BY start_time DESC LIMIT 50
        ''')
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'waypoints_completed': row[3],
                'total_distance': row[4],
                'minerals_collected': row[5],
                'status': row[6]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': sessions
        })
    except Exception as e:
        logger.error(f"Error getting mining sessions: {e}")
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
                'bluetooth_clients': 0,
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
        'vehicle_running': vehicle_controller.running if vehicle_controller else False,
        'services': {
            'database': check_database_health(),
            'vehicle_controller': vehicle_controller is not None
        }
    })

@app.route('/api/system-status', methods=['GET'])
def get_system_status():
    """Get basic system status"""
    return jsonify({
        'success': True,
        'data': {
            'server_running': True,
            'timestamp': time.time(),
            'version': '2.0.0'
        }
    })

@app.route('/')
def serve_info():
    """Serve API information"""
    return jsonify({
        'message': 'SmartRover Mining Vehicle Server',
        'version': '2.0.0',
        'status': 'operational',
        'features': [
            'Autonomous navigation',
            'Waypoint-based mining',
            'Real-time mapping',
            'Remote control'
        ]
    })

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

if __name__ == '__main__':
    logger.info("Starting SmartRover Standalone Server...")
    
    # Ensure database exists
    ensure_database()
    log_system_event('INFO', 'Server starting up', 'server')
    
    # Start vehicle controller thread
    start_vehicle_thread()
    
    # Start Flask server
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        log_system_event('CRITICAL', f'Server startup failed: {e}', 'server')
