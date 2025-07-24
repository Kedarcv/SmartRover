#!/usr/bin/env python3
"""
SmartRover Mobile API Module
Provides REST API endpoints optimized for mobile applications
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import json
import time
import logging
import os
import sqlite3
import base64
import io
from PIL import Image
import qrcode
import hashlib
import jwt
from datetime import datetime, timedelta
from functools import wraps
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/mobile_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smartrover_mobile_secret_2024'
CORS(app, origins="*")

# Global variables
vehicle_controller = None
stream_manager = None
database_path = '/var/lib/smartrover/mining_data.db'

# Authentication settings
JWT_SECRET = 'smartrover_jwt_secret_2024'
JWT_EXPIRATION_HOURS = 24

# Mobile-specific settings
MOBILE_IMAGE_SIZE = (640, 480)
THUMBNAIL_SIZE = (160, 120)

def token_required(f):
    """Decorator for JWT token authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user = data['user']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/mobile/auth/login', methods=['POST'])
def mobile_login():
    """Mobile authentication endpoint"""
    try:
        data = request.get_json()
        username = data.get('username', '').lower().strip()
        password = data.get('password', '')
        device_id = data.get('device_id', '')
        device_name = data.get('device_name', 'Unknown Device')
        
        # Simple authentication (in production, use proper password hashing)
        valid_users = {
            'cvlised360@gmail.com': 'Cvlised@360',
            'admin@smartrover.com': 'admin123',
            'operator@smartrover.com': 'operator123',
            'mobile': 'smartrover2024'
        }
        
        if username in valid_users and valid_users[username] == password:
            # Generate JWT token
            payload = {
                'user': username,
                'device_id': device_id,
                'device_name': device_name,
                'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
                'iat': datetime.utcnow()
            }
            
            token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
            
            # Log successful login
            log_mobile_event('login', username, device_id, f'Successful login from {device_name}')
            
            return jsonify({
                'success': True,
                'token': token,
                'user': {
                    'username': username,
                    'expires_in': JWT_EXPIRATION_HOURS * 3600
                },
                'server_info': {
                    'version': '2.0.0',
                    'features': [
                        'real_time_control',
                        'live_streaming',
                        'waypoint_management',
                        'mining_operations'
                    ]
                }
            })
        else:
            log_mobile_event('login_failed', username, device_id, 'Invalid credentials')
            return jsonify({
                'success': False,
                'error': 'Invalid credentials'
            }), 401
            
    except Exception as e:
        logger.error(f"Mobile login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500

@app.route('/mobile/auth/refresh', methods=['POST'])
@token_required
def refresh_token(current_user):
    """Refresh JWT token"""
    try:
        data = request.get_json()
        device_id = data.get('device_id', '')
        device_name = data.get('device_name', 'Unknown Device')
        
        # Generate new token
        payload = {
            'user': current_user,
            'device_id': device_id,
            'device_name': device_name,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'expires_in': JWT_EXPIRATION_HOURS * 3600
        })
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({
            'success': False,
            'error': 'Token refresh failed'
        }), 500

@app.route('/mobile/vehicle/status', methods=['GET'])
@token_required
def get_mobile_vehicle_status(current_user):
    """Get vehicle status optimized for mobile"""
    try:
        if not vehicle_controller:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not available'
            }), 503
        
        # Get basic status
        status = vehicle_controller.get_status_data()
        
        # Optimize for mobile (reduce data size)
        mobile_status = {
            'timestamp': status.get('timestamp', time.time()),
            'position': status.get('position', [0, 0]),
            'heading': round(status.get('heading', 0), 1),
            'speed': round(status.get('action_data', {}).get('speed', 0) * 100, 1),  # Convert to percentage
            'action': status.get('action_data', {}).get('action', 'stop'),
            'obstacle_detected': status.get('action_data', {}).get('obstacle_detected', False),
            'sensors': {
                'ultrasonic': [round(x, 1) for x in status.get('sensor_data', {}).get('ultrasonic', [0, 0, 0, 0])],
                'camera_available': status.get('sensor_data', {}).get('camera_available', False)
            },
            'system': {
                'running': status.get('system_status', {}).get('running', False),
                'mining_active': status.get('system_status', {}).get('mining_active', False),
                'returning_to_dock': status.get('system_status', {}).get('returning_to_dock', False),
                'emergency_stop': status.get('system_status', {}).get('emergency_stop', False)
            },
            'mining': {
                'waypoints_completed': status.get('system_status', {}).get('waypoints_completed', 0),
                'minerals_collected': status.get('system_status', {}).get('minerals_collected', 0),
                'total_distance': round(status.get('system_status', {}).get('total_distance', 0), 1)
            },
            'connectivity': {
                'signal_strength': 'good',  # Would be calculated from actual signal
                'last_update': time.time()
            }
        }
        
        return jsonify({
            'success': True,
            'data': mobile_status
        })
        
    except Exception as e:
        logger.error(f"Mobile vehicle status error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get vehicle status'
        }), 500

@app.route('/mobile/vehicle/control', methods=['POST'])
@token_required
def mobile_vehicle_control(current_user):
    """Vehicle control optimized for mobile"""
    try:
        data = request.get_json()
        command = data.get('command')
        
        if not vehicle_controller:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not available'
            }), 503
        
        # Execute command
        result = execute_mobile_command(command, current_user)
        
        # Log command
        log_mobile_event('command', current_user, data.get('device_id', ''), f'Command: {command}')
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Mobile vehicle control error: {e}")
        return jsonify({
            'success': False,
            'error': 'Command execution failed'
        }), 500

@app.route('/mobile/camera/stream', methods=['GET'])
@token_required
def mobile_camera_stream(current_user):
    """Get camera frame for mobile"""
    try:
        if not vehicle_controller or not vehicle_controller.camera_available:
            return jsonify({
                'success': False,
                'error': 'Camera not available'
            }), 503
        
        # Get frame from camera
        ret, frame = vehicle_controller.camera.read()
        if not ret:
            return jsonify({
                'success': False,
                'error': 'Failed to capture frame'
            }), 500
        
        # Resize for mobile
        import cv2
        frame = cv2.resize(frame, MOBILE_IMAGE_SIZE)
        
        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        
        # Convert to base64
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'data': {
                'frame': frame_b64,
                'timestamp': time.time(),
                'resolution': MOBILE_IMAGE_SIZE,
                'format': 'jpeg'
            }
        })
        
    except Exception as e:
        logger.error(f"Mobile camera stream error: {e}")
        return jsonify({
            'success': False,
            'error': 'Camera stream failed'
        }), 500

@app.route('/mobile/waypoints', methods=['GET'])
@token_required
def get_mobile_waypoints(current_user):
    """Get waypoints optimized for mobile"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, x, y, type, status, priority, created_at
            FROM waypoints ORDER BY priority DESC, created_at ASC
        ''')
        
        waypoints = []
        for row in cursor.fetchall():
            waypoint = {
                'id': row[0],
                'name': row[1],
                'position': [round(row[2], 1), round(row[3], 1)],
                'type': row[4],
                'status': row[5],
                'priority': row[6],
                'created_at': row[7]
            }
            
            # Calculate distance if vehicle position is available
            if vehicle_controller:
                current_pos = vehicle_controller.slam_mapper.robot_position
                if current_pos:
                    distance = ((row[2] - current_pos[0])**2 + (row[3] - current_pos[1])**2)**0.5
                    waypoint['distance'] = round(distance, 1)
            
            waypoints.append(waypoint)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': waypoints
        })
        
    except Exception as e:
        logger.error(f"Mobile waypoints error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get waypoints'
        }), 500

@app.route('/mobile/waypoints', methods=['POST'])
@token_required
def add_mobile_waypoint(current_user):
    """Add waypoint from mobile"""
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
                'error': 'Missing required fields'
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
        
        # Notify vehicle controller
        if vehicle_controller:
            vehicle_controller.reload_waypoints()
        
        # Log waypoint addition
        log_mobile_event('waypoint_added', current_user, data.get('device_id', ''), 
                        f'Added waypoint: {name} at ({x}, {y})')
        
        return jsonify({
            'success': True,
            'data': {
                'id': waypoint_id,
                'message': 'Waypoint added successfully'
            }
        })
        
    except Exception as e:
        logger.error(f"Mobile add waypoint error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to add waypoint'
        }), 500

@app.route('/mobile/map/data', methods=['GET'])
@token_required
def get_mobile_map_data(current_user):
    """Get map data optimized for mobile"""
    try:
        if not vehicle_controller:
            return jsonify({
                'success': False,
                'error': 'Vehicle controller not available'
            }), 503
        
        # Get map data from SLAM mapper
        map_data = vehicle_controller.slam_mapper.export_map_data()
        
        # Optimize for mobile (reduce data size)
        mobile_map_data = {
            'robot_position': map_data.get('robot_position', [0, 0]),
            'robot_heading': round(map_data.get('robot_heading', 0), 2),
            'path_history': map_data.get('path_history', [])[-50:],  # Last 50 points
            'obstacles': map_data.get('obstacles', [])[-20:],  # Last 20 obstacles
            'total_distance': round(map_data.get('total_distance', 0), 1),
            'timestamp': map_data.get('timestamp', time.time())
        }
        
        return jsonify({
            'success': True,
            'data': mobile_map_data
        })
        
    except Exception as e:
        logger.error(f"Mobile map data error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get map data'
        }), 500

@app.route('/mobile/mining/sessions', methods=['GET'])
@token_required
def get_mobile_mining_sessions(current_user):
    """Get mining sessions for mobile"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 sessions
        
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, start_time, end_time, waypoints_completed, 
                   total_distance, minerals_collected, status
            FROM mining_sessions ORDER BY start_time DESC LIMIT ?
        ''', (limit,))
        
        sessions = []
        for row in cursor.fetchall():
            session = {
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'waypoints_completed': row[3],
                'total_distance': round(row[4], 1) if row[4] else 0,
                'minerals_collected': row[5],
                'status': row[6]
            }
            
            # Calculate duration
            if row[1] and row[2]:
                start = datetime.fromisoformat(row[1])
                end = datetime.fromisoformat(row[2])
                duration = (end - start).total_seconds()
                session['duration_seconds'] = int(duration)
            
            sessions.append(session)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': sessions
        })
        
    except Exception as e:
        logger.error(f"Mobile mining sessions error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get mining sessions'
        }), 500

@app.route('/mobile/system/info', methods=['GET'])
@token_required
def get_mobile_system_info(current_user):
    """Get system info optimized for mobile"""
    try:
        import psutil
        import platform
        
        # Get basic system info
        system_info = {
            'hostname': platform.node(),
            'uptime_seconds': int(time.time() - psutil.boot_time()),
            'cpu_percent': round(psutil.cpu_percent(), 1),
            'memory_percent': round(psutil.virtual_memory().percent, 1),
            'disk_percent': round(psutil.disk_usage('/').percent, 1),
            'temperature': get_cpu_temperature(),
            'vehicle_status': {
                'running': vehicle_controller.running if vehicle_controller else False,
                'mining_active': vehicle_controller.mining_active if vehicle_controller else False
            },
            'connectivity': {
                'wifi_connected': True,  # Assume connected if API is responding
                'signal_strength': 'good'
            },
            'timestamp': time.time()
        }
        
        return jsonify({
            'success': True,
            'data': system_info
        })
        
    except Exception as e:
        logger.error(f"Mobile system info error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get system info'
        }), 500

@app.route('/mobile/qr/connect', methods=['GET'])
def generate_connection_qr():
    """Generate QR code for easy mobile connection"""
    try:
        # Get server info
        import socket
        hostname = socket.gethostname()
        
        # Try to get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "192.168.1.100"
        
        # Create connection info
        connection_info = {
            'type': 'smartrover_connection',
            'hostname': hostname,
            'ip': local_ip,
            'api_port': 5000,
            'websocket_port': 8765,
            'version': '2.0.0',
            'timestamp': int(time.time())
        }
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(connection_info))
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=False,
            download_name='smartrover_connection.png'
        )
        
    except Exception as e:
        logger.error(f"QR code generation error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate QR code'
        }), 500

@app.route('/mobile/logs', methods=['GET'])
@token_required
def get_mobile_logs(current_user):
    """Get system logs for mobile"""
    try:
        limit = min(int(request.args.get('limit', 20)), 100)  # Max 100 logs
        level = request.args.get('level', 'INFO')
        
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        if level == 'ALL':
            cursor.execute('''
                SELECT timestamp, level, message, component
                FROM system_logs ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT timestamp, level, message, component
                FROM system_logs WHERE level = ? ORDER BY timestamp DESC LIMIT ?
            ''', (level, limit))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'timestamp': row[0],
                'level': row[1],
                'message': row[2],
                'component': row[3]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': logs
        })
        
    except Exception as e:
        logger.error(f"Mobile logs error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get logs'
        }), 500

# Helper functions
def execute_mobile_command(command, user):
    """Execute vehicle command from mobile"""
    try:
        if not vehicle_controller:
            return {
                'success': False,
                'error': 'Vehicle controller not available'
            }
        
        if command == 'start_mining':
            vehicle_controller.start_mining_operation()
            return {
                'success': True,
                'message': 'Mining operation started',
                'action': 'start_mining'
            }
        elif command == 'stop_mining':
            vehicle_controller.stop_mining_operation()
            return {
                'success': True,
                'message': 'Mining operation stopped',
                'action': 'stop_mining'
            }
        elif command == 'return_to_dock':
            vehicle_controller.return_to_dock()
            return {
                'success': True,
                'message': 'Returning to docking station',
                'action': 'return_to_dock'
            }
        elif command == 'emergency_stop':
            vehicle_controller.emergency_stop()
            return {
                'success': True,
                'message': 'Emergency stop activated',
                'action': 'emergency_stop'
            }
        elif command == 'start_vehicle':
            vehicle_controller.running = True
            return {
                'success': True,
                'message': 'Vehicle started',
                'action': 'start_vehicle'
            }
        elif command == 'stop_vehicle':
            vehicle_controller.running = False
            return {
                'success': True,
                'message': 'Vehicle stopped',
                'action': 'stop_vehicle'
            }
        else:
            return {
                'success': False,
                'error': f'Unknown command: {command}'
            }
            
    except Exception as e:
        logger.error(f"Error executing mobile command {command}: {e}")
        return {
            'success': False,
            'error': f'Command execution failed: {str(e)}'
        }

def get_cpu_temperature():
    """Get CPU temperature"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
            return round(temp, 1)
    except:
        return None

def log_mobile_event(event_type, user, device_id, details):
    """Log mobile API events"""
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO system_logs (level, message, component)
            VALUES (?, ?, ?)
        ''', ('INFO', f'Mobile {event_type}: {user} ({device_id}) - {details}', 'mobile_api'))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging mobile event: {e}")

def init_mobile_api(vc=None, sm=None):
    """Initialize mobile API with vehicle controller and stream manager"""
    global vehicle_controller, stream_manager
    vehicle_controller = vc
    stream_manager = sm
    logger.info("📱 Mobile API initialized")

if __name__ == '__main__':
    logger.info("📱 Starting SmartRover Mobile API server...")
    app.run(host='0.0.0.0', port=5001, debug=False)
