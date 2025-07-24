import numpy as np
import cv2
import tensorflow as tf
from tensorflow import keras
import json
import time
import threading
import requests
import logging
from collections import deque
import RPi.GPIO as GPIO
from gpiozero import DistanceSensor, LED, Button
import socket
import os
import sqlite3
import math
from datetime import datetime
import random
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockHardware:
    """Mock hardware for testing without actual GPIO"""
    def __init__(self):
        self.position = [1000, 1000]  # Start at docking station
        self.heading = 0
        self.speed = 0
        self.sensors = {'front': 100, 'left': 100, 'right': 100, 'rear': 100}
        
    def read_sensors(self):
        """Simulate sensor readings"""
        # Add some random variation
        for direction in self.sensors:
            self.sensors[direction] = max(20, min(200, self.sensors[direction] + random.randint(-10, 10)))
        return [self.sensors['front'], self.sensors['left'], self.sensors['right'], self.sensors['rear']]
    
    def move_forward(self, speed=0.5):
        """Simulate forward movement"""
        self.speed = speed
        # Update position based on heading
        self.position[0] += math.cos(math.radians(self.heading)) * speed * 10
        self.position[1] += math.sin(math.radians(self.heading)) * speed * 10
    
    def turn_left(self, angle=15):
        """Simulate left turn"""
        self.heading = (self.heading - angle) % 360
    
    def turn_right(self, angle=15):
        """Simulate right turn"""
        self.heading = (self.heading + angle) % 360
    
    def stop(self):
        """Stop the vehicle"""
        self.speed = 0

class MiningVehicleNN:
    def __init__(self, model_path=None):
        self.input_shape = (224, 224, 3)
        self.model = self._load_or_create_model(model_path)
        
    def _load_or_create_model(self, model_path):
        """Load existing model or create new one"""
        if model_path and os.path.exists(model_path):
            logger.info(f"Loading model from {model_path}")
            return keras.models.load_model(model_path)
        else:
            logger.info("Creating new model")
            return self._build_model()
    
    def _build_model(self):
        """Build the neural network for path planning and obstacle detection"""
        # Input for ultrasonic sensors (always available)
        sensor_input = keras.Input(shape=(4,), name='sensors')
        
        # Optional camera input
        camera_input = keras.Input(shape=self.input_shape, name='camera')
        
        # Process sensor data (primary input)
        sensor_features = keras.layers.Dense(64, activation='relu')(sensor_input)
        sensor_features = keras.layers.Dense(128, activation='relu')(sensor_features)
        sensor_features = keras.layers.Dense(64, activation='relu')(sensor_features)
        
        # Process camera data if available
        x = keras.layers.Conv2D(32, 3, activation='relu')(camera_input)
        x = keras.layers.MaxPooling2D()(x)
        x = keras.layers.Conv2D(64, 3, activation='relu')(x)
        x = keras.layers.GlobalAveragePooling2D()(x)
        camera_features = keras.layers.Dense(64, activation='relu')(x)
        
        # Combine features (sensor-weighted)
        combined = keras.layers.concatenate([sensor_features, camera_features])
        combined = keras.layers.Dense(128, activation='relu')(combined)
        combined = keras.layers.Dropout(0.2)(combined)
        
        # Output layers
        path_output = keras.layers.Dense(4, activation='softmax', name='path')(combined)
        speed_output = keras.layers.Dense(1, activation='sigmoid', name='speed')(combined)
        obstacle_output = keras.layers.Dense(1, activation='sigmoid', name='obstacle')(combined)
        
        model = keras.Model(
            inputs=[sensor_input, camera_input],
            outputs=[path_output, speed_output, obstacle_output]
        )
        
        model.compile(
            optimizer='adam',
            loss={
                'path': 'categorical_crossentropy',
                'speed': 'mse',
                'obstacle': 'binary_crossentropy'
            }
        )
        
        return model
    
    def predict_action_sensors_only(self, sensor_data):
        """Make prediction using only ultrasonic sensors"""
        sensor_processed = np.array(sensor_data).reshape(1, -1) / 400.0
        
        # Simple rule-based system when no camera
        front, left, right, rear = sensor_data
        
        # Determine action based on sensor readings
        if front < 30 or min(sensor_data) < 20:  # Emergency stop
            return {
                'action': 'stop',
                'action_confidence': 1.0,
                'speed': 0.0,
                'obstacle_detected': True,
                'obstacle_confidence': 1.0
            }
        elif front < 80:  # Obstacle ahead, turn
            if left > right:
                action = 'left'
            else:
                action = 'right'
            return {
                'action': action,
                'action_confidence': 0.8,
                'speed': 0.3,
                'obstacle_detected': True,
                'obstacle_confidence': 0.8
            }
        else:  # Clear path
            return {
                'action': 'straight',
                'action_confidence': 0.9,
                'speed': 0.6,
                'obstacle_detected': False,
                'obstacle_confidence': 0.1
            }

class L298NMotorController:
    def __init__(self):
        """Initialize L298N motor controller with user's pin configuration"""
        # User's motor pin configuration
        self.MOTOR_PINS = {
            'IN1': 18,  # Motor 1 Direction
            'IN2': 16,  # Motor 1 Direction  
            'IN3': 21,  # Motor 2 Direction
            'IN4': 23   # Motor 2 Direction
        }
        
        # Enable pins (PWM) - using available GPIO pins
        self.ENA = 12  # Motor 1 Speed (PWM)
        self.ENB = 13  # Motor 2 Speed (PWM)
        
        self.setup_motors()
        
    def setup_motors(self):
        """Setup GPIO pins for motor control"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup all motor pins
        for pin in self.MOTOR_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
        
        # Setup enable pins
        GPIO.setup(self.ENA, GPIO.OUT)
        GPIO.setup(self.ENB, GPIO.OUT)
        
        # Setup PWM for speed control
        self.pwm_a = GPIO.PWM(self.ENA, 1000)  # 1kHz frequency
        self.pwm_b = GPIO.PWM(self.ENB, 1000)
        
        # Start PWM with 0% duty cycle
        self.pwm_a.start(0)
        self.pwm_b.start(0)
        
        logger.info("L298N motor controller initialized with custom pin configuration")
    
    def set_motor_direction(self, motor, direction):
        """Set motor direction"""
        if motor == 'A':  # Motor 1
            if direction == 'forward':
                GPIO.output(self.MOTOR_PINS['IN1'], GPIO.HIGH)
                GPIO.output(self.MOTOR_PINS['IN2'], GPIO.LOW)
            elif direction == 'backward':
                GPIO.output(self.MOTOR_PINS['IN1'], GPIO.LOW)
                GPIO.output(self.MOTOR_PINS['IN2'], GPIO.HIGH)
            else:  # stop
                GPIO.output(self.MOTOR_PINS['IN1'], GPIO.LOW)
                GPIO.output(self.MOTOR_PINS['IN2'], GPIO.LOW)
                
        elif motor == 'B':  # Motor 2
            if direction == 'forward':
                GPIO.output(self.MOTOR_PINS['IN3'], GPIO.HIGH)
                GPIO.output(self.MOTOR_PINS['IN4'], GPIO.LOW)
            elif direction == 'backward':
                GPIO.output(self.MOTOR_PINS['IN3'], GPIO.LOW)
                GPIO.output(self.MOTOR_PINS['IN4'], GPIO.HIGH)
            else:  # stop
                GPIO.output(self.MOTOR_PINS['IN3'], GPIO.LOW)
                GPIO.output(self.MOTOR_PINS['IN4'], GPIO.LOW)
    
    def set_motor_speed(self, motor, speed):
        """Set motor speed (0-100%)"""
        speed_percent = max(0, min(100, speed * 100))
        
        if motor == 'A':
            self.pwm_a.ChangeDutyCycle(speed_percent)
        elif motor == 'B':
            self.pwm_b.ChangeDutyCycle(speed_percent)
    
    def move_vehicle(self, action, speed):
        """Control vehicle movement based on action"""
        if action == 'stop':
            self.stop_all_motors()
        elif action == 'straight':
            self.move_forward(speed)
        elif action == 'left':
            self.turn_left(speed)
        elif action == 'right':
            self.turn_right(speed)
        elif action == 'reverse':
            self.move_backward(speed)
    
    def move_forward(self, speed):
        """Move vehicle forward"""
        self.set_motor_direction('A', 'forward')
        self.set_motor_direction('B', 'forward')
        self.set_motor_speed('A', speed)
        self.set_motor_speed('B', speed)
    
    def move_backward(self, speed):
        """Move vehicle backward"""
        self.set_motor_direction('A', 'backward')
        self.set_motor_direction('B', 'backward')
        self.set_motor_speed('A', speed)
        self.set_motor_speed('B', speed)
    
    def turn_left(self, speed):
        """Turn vehicle left (slow left motor, full right motor)"""
        self.set_motor_direction('A', 'forward')
        self.set_motor_direction('B', 'forward')
        self.set_motor_speed('A', speed * 0.3)  # Slow left motor
        self.set_motor_speed('B', speed)        # Full right motor
    
    def turn_right(self, speed):
        """Turn vehicle right (full left motor, slow right motor)"""
        self.set_motor_direction('A', 'forward')
        self.set_motor_direction('B', 'forward')
        self.set_motor_speed('A', speed)        # Full left motor
        self.set_motor_speed('B', speed * 0.3)  # Slow right motor
    
    def stop_all_motors(self):
        """Stop all motors"""
        self.set_motor_direction('A', 'stop')
        self.set_motor_direction('B', 'stop')
        self.set_motor_speed('A', 0)
        self.set_motor_speed('B', 0)
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        self.stop_all_motors()
        self.pwm_a.stop()
        self.pwm_b.stop()
        GPIO.cleanup()

class UltrasonicSensorArray:
    def __init__(self):
        """Initialize ultrasonic sensor with user's pin configuration"""
        # User's sensor pin configuration
        self.SENSOR_PINS = {
            'TRIG': 24,  # Ultrasonic Trigger
            'ECHO': 25   # Ultrasonic Echo
        }
        
        try:
            # Initialize single ultrasonic sensor
            self.sensor = DistanceSensor(
                echo=self.SENSOR_PINS['ECHO'], 
                trigger=self.SENSOR_PINS['TRIG'], 
                max_distance=4
            )
            logger.info("Ultrasonic sensor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize sensor: {e}")
            self.sensor = None
    
    def read_all_sensors(self):
        """Read ultrasonic sensor and simulate 4 sensors"""
        readings = []
        
        try:
            if self.sensor:
                # Read the actual sensor
                distance = self.sensor.distance * 100  # Convert to cm
                distance = min(distance, 400)  # Cap at 400cm
                
                # For now, use the same reading for all 4 directions
                # In a real setup, you'd have 4 separate sensors
                readings = [distance, distance, distance, distance]
            else:
                # Simulation mode - return safe distances
                readings = [200, 200, 200, 200]
                
        except Exception as e:
            logger.warning(f"Error reading sensor: {e}")
            readings = [400, 400, 400, 400]  # Default max range
        
        return readings

class SLAMMapper:
    def __init__(self, map_size=2000):
        self.map_size = map_size
        self.map_data = np.zeros((map_size, map_size), dtype=np.uint8)
        self.robot_position = [map_size // 2, map_size // 2]  # Start at center
        self.robot_heading = 0
        self.scale = 5  # cm per pixel
        self.path_history = deque(maxlen=1000)
        self.obstacles = []
        self.total_distance = 0
        
    def update_position(self, movement_vector, heading_change=0):
        """Update robot position and heading"""
        dx, dy = movement_vector
        
        # Update heading
        self.robot_heading += heading_change
        self.robot_heading = self.robot_heading % (2 * np.pi)
        
        # Calculate new position based on heading
        distance = np.sqrt(dx**2 + dy**2)
        new_x = self.robot_position[0] + int((distance * np.cos(self.robot_heading)) / self.scale)
        new_y = self.robot_position[1] + int((distance * np.sin(self.robot_heading)) / self.scale)
        
        # Ensure position is within map bounds
        new_x = max(10, min(self.map_size - 10, new_x))
        new_y = max(10, min(self.map_size - 10, new_y))
        
        # Add to path history
        self.path_history.append([new_x, new_y])
        
        # Update total distance
        if len(self.path_history) > 1:
            prev_pos = self.path_history[-2]
            self.total_distance += np.sqrt((new_x - prev_pos[0])**2 + (new_y - prev_pos[1])**2) * self.scale / 100  # meters
        
        # Update position
        self.robot_position = [new_x, new_y]
        
        # Mark current position as explored
        self.map_data[new_y, new_x] = 128  # Explored area
        
        # Draw path
        if len(self.path_history) > 1:
            prev_pos = self.path_history[-2]
            cv2.line(self.map_data, tuple(prev_pos), tuple(self.robot_position), 64, 2)
    
    def add_obstacle(self, distance, sensor_angle):
        """Add obstacle to map based on sensor reading"""
        if distance < 350:  # Only map close obstacles
            # Calculate obstacle position relative to robot
            absolute_angle = self.robot_heading + sensor_angle
            obstacle_x = self.robot_position[0] + int((distance * np.cos(absolute_angle)) / self.scale)
            obstacle_y = self.robot_position[1] + int((distance * np.sin(absolute_angle)) / self.scale)
            
            # Ensure obstacle is within map bounds
            if 0 <= obstacle_x < self.map_size and 0 <= obstacle_y < self.map_size:
                self.map_data[obstacle_y, obstacle_x] = 255  # Obstacle
                
                # Add to obstacles list for path planning
                obstacle_info = {
                    'position': [obstacle_x, obstacle_y],
                    'distance': distance,
                    'timestamp': time.time()
                }
                self.obstacles.append(obstacle_info)
                
                # Keep only recent obstacles
                current_time = time.time()
                self.obstacles = [obs for obs in self.obstacles 
                                if current_time - obs['timestamp'] < 300]  # 5 minutes
    
    def get_map_region(self, size=400):
        """Get map region around robot for visualization"""
        x, y = self.robot_position
        half_size = size // 2
        
        x_start = max(0, x - half_size)
        x_end = min(self.map_size, x + half_size)
        y_start = max(0, y - half_size)
        y_end = min(self.map_size, y + half_size)
        
        region = self.map_data[y_start:y_end, x_start:x_end].copy()
        
        # Adjust robot position for the region
        region_robot_x = x - x_start
        region_robot_y = y - y_start
        
        # Convert to RGB
        region_rgb = cv2.cvtColor(region, cv2.COLOR_GRAY2RGB)
        
        # Draw robot
        if 0 <= region_robot_x < region.shape[1] and 0 <= region_robot_y < region.shape[0]:
            cv2.circle(region_rgb, (region_robot_x, region_robot_y), 8, (0, 255, 0), -1)
            
            # Draw heading direction
            end_x = int(region_robot_x + 15 * np.cos(self.robot_heading))
            end_y = int(region_robot_y + 15 * np.sin(self.robot_heading))
            cv2.arrowedLine(region_rgb, (region_robot_x, region_robot_y), 
                          (end_x, end_y), (0, 0, 255), 3)
        
        # Draw path in region
        if len(self.path_history) > 1:
            for i in range(1, len(self.path_history)):
                pt1 = self.path_history[i-1]
                pt2 = self.path_history[i]
                
                # Adjust points for region
                pt1_region = (pt1[0] - x_start, pt1[1] - y_start)
                pt2_region = (pt2[0] - x_start, pt2[1] - y_start)
                
                # Check if points are in region
                if (0 <= pt1_region[0] < region.shape[1] and 0 <= pt1_region[1] < region.shape[0] and
                    0 <= pt2_region[0] < region.shape[1] and 0 <= pt2_region[1] < region.shape[0]):
                    cv2.line(region_rgb, pt1_region, pt2_region, (255, 255, 0), 2)
        
        return region_rgb
    
    def export_map_data(self):
        """Export map data for dashboard"""
        return {
            'robot_position': self.robot_position,
            'robot_heading': float(self.robot_heading),
            'path_history': list(self.path_history),
            'obstacles': self.obstacles[-50:],  # Last 50 obstacles
            'map_region': self.get_map_region().tolist(),
            'total_distance': self.total_distance,
            'timestamp': time.time()
        }

class WaypointNavigator:
    def __init__(self, database_path):
        self.database_path = database_path
        self.current_waypoint = None
        self.waypoints_queue = []
        self.navigation_tolerance = 50  # pixels (10 meters at 5cm/pixel scale)
        
    def load_waypoints(self):
        """Load pending waypoints from database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, x, y, type, priority
                FROM waypoints 
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
            ''')
            
            self.waypoints_queue = []
            for row in cursor.fetchall():
                self.waypoints_queue.append({
                    'id': row[0],
                    'name': row[1],
                    'x': row[2],
                    'y': row[3],
                    'type': row[4],
                    'priority': row[5]
                })
            
            conn.close()
            logger.info(f"Loaded {len(self.waypoints_queue)} pending waypoints")
            
        except Exception as e:
            logger.error(f"Error loading waypoints: {e}")
    
    def reload_waypoints(self):
        """Reload waypoints from database"""
        self.load_waypoints()
    
    def get_next_waypoint(self):
        """Get the next waypoint to navigate to"""
        if not self.current_waypoint and self.waypoints_queue:
            self.current_waypoint = self.waypoints_queue.pop(0)
            logger.info(f"Next waypoint: {self.current_waypoint['name']} at ({self.current_waypoint['x']}, {self.current_waypoint['y']})")
        
        return self.current_waypoint
    
    def calculate_navigation_action(self, current_position, current_heading):
        """Calculate navigation action to reach current waypoint"""
        if not self.current_waypoint:
            return None
        
        target_x = self.current_waypoint['x']
        target_y = self.current_waypoint['y']
        current_x, current_y = current_position
        
        # Calculate distance to target
        distance = math.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
        
        # Check if we've reached the waypoint
        if distance < self.navigation_tolerance:
            self.mark_waypoint_completed()
            return {'action': 'waypoint_reached', 'distance': distance}
        
        # Calculate desired heading to target
        desired_heading = math.atan2(target_y - current_y, target_x - current_x)
        
        # Calculate heading difference
        heading_diff = desired_heading - current_heading
        
        # Normalize heading difference to [-pi, pi]
        while heading_diff > math.pi:
            heading_diff -= 2 * math.pi
        while heading_diff < -math.pi:
            heading_diff += 2 * math.pi
        
        # Determine navigation action
        if abs(heading_diff) > 0.3:  # Need to turn
            if heading_diff > 0:
                return {'action': 'turn_left', 'heading_diff': heading_diff, 'distance': distance}
            else:
                return {'action': 'turn_right', 'heading_diff': heading_diff, 'distance': distance}
        else:
            return {'action': 'move_forward', 'heading_diff': heading_diff, 'distance': distance}
    
    def mark_waypoint_completed(self):
        """Mark current waypoint as completed"""
        if not self.current_waypoint:
            return
        
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE waypoints 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (self.current_waypoint['id'],))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Waypoint completed: {self.current_waypoint['name']}")
            
            # Simulate mineral collection for mining waypoints
            if self.current_waypoint['type'] == 'mining':
                self.simulate_mineral_collection()
            
            self.current_waypoint = None
            
        except Exception as e:
            logger.error(f"Error marking waypoint completed: {e}")
    
    def simulate_mineral_collection(self):
        """Simulate mineral collection process"""
        logger.info("Simulating mineral collection...")
        time.sleep(2)  # Simulate collection time
        logger.info("Mineral collection completed")
    
    def get_docking_station_waypoint(self):
        """Get docking station coordinates"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT x, y FROM waypoints WHERE type = "dock" LIMIT 1')
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {'x': result[0], 'y': result[1], 'name': 'Docking Station', 'type': 'dock'}
            else:
                return {'x': 1000, 'y': 1000, 'name': 'Docking Station', 'type': 'dock'}  # Default
                
        except Exception as e:
            logger.error(f"Error getting docking station: {e}")
            return {'x': 1000, 'y': 1000, 'name': 'Docking Station', 'type': 'dock'}

class VehicleController:
    def __init__(self, database_path='/var/lib/smartrover/mining_data.db', server_port=5000):
        self.database_path = database_path
        self.nn_model = MiningVehicleNN()
        self.motor_controller = L298NMotorController()
        self.sensor_array = UltrasonicSensorArray()
        self.slam_mapper = SLAMMapper()
        self.waypoint_navigator = WaypointNavigator(database_path)
        self.server_port = server_port
        self.running = False
        self.mining_active = False
        self.returning_to_dock = False
        self.camera = None
        self.camera_available = False
        self.current_session_id = None
        self.waypoints_completed = 0
        self.minerals_collected = 0
        self.total_distance = 0
        
        # Status LEDs
        try:
            self.status_led = LED(26)
            self.warning_led = LED(13)
            self.emergency_button = Button(6)
            self.emergency_button.when_pressed = self.emergency_stop
        except Exception as e:
            logger.warning(f"LED/Button setup failed: {e}")
            self.status_led = None
            self.warning_led = None
        
        # Try to import real hardware, fall back to mock
        try:
            import RPi.GPIO as GPIO
            from gpiozero import DistanceSensor, Motor
            self.use_real_hardware = True
            logger.info("Real hardware detected")
        except ImportError:
            self.use_real_hardware = False
            logger.info("Using mock hardware for testing")
            self.hardware = MockHardware()
    
    def initialize_camera(self):
        """Try to initialize camera"""
        try:
            self.camera = cv2.VideoCapture(0)
            if self.camera.isOpened():
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera_available = True
                logger.info("Camera initialized successfully")
            else:
                self.camera_available = False
                logger.warning("Camera not available, using sensor-only mode")
        except Exception as e:
            logger.warning(f"Camera initialization failed: {e}")
            self.camera_available = False
    
    def start_mining_session(self):
        """Start a new mining session"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO mining_sessions (start_time, status)
                VALUES (CURRENT_TIMESTAMP, 'active')
            ''')
            
            self.current_session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Started mining session {self.current_session_id}")
            
        except Exception as e:
            logger.error(f"Error starting mining session: {e}")
    
    def end_mining_session(self):
        """End current mining session"""
        if not self.current_session_id:
            return
        
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE mining_sessions 
                SET end_time = CURRENT_TIMESTAMP,
                    waypoints_completed = ?,
                    total_distance = ?,
                    minerals_collected = ?,
                    status = 'completed'
                WHERE id = ?
            ''', (self.waypoints_completed, self.slam_mapper.total_distance, 
                  self.minerals_collected, self.current_session_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Ended mining session {self.current_session_id}")
            self.current_session_id = None
            
        except Exception as e:
            logger.error(f"Error ending mining session: {e}")
    
    def start_mining_operation(self):
        """Start autonomous mining operation"""
        self.mining_active = True
        self.returning_to_dock = False
        self.waypoint_navigator.load_waypoints()
        self.start_mining_session()
        logger.info("Mining operation started")
    
    def stop_mining_operation(self):
        """Stop mining operation"""
        self.mining_active = False
        self.returning_to_dock = False
        self.end_mining_session()
        self.motor_controller.stop_all_motors()
        logger.info("Mining operation stopped")
    
    def return_to_dock(self):
        """Return to docking station"""
        self.mining_active = False
        self.returning_to_dock = True
        dock_waypoint = self.waypoint_navigator.get_docking_station_waypoint()
        self.waypoint_navigator.current_waypoint = dock_waypoint
        logger.info("Returning to docking station")
    
    def reload_waypoints(self):
        """Reload waypoints from database"""
        self.waypoint_navigator.load_waypoints()
    
    def process_sensor_data(self, ultrasonic_readings):
        """Process sensor data and update map"""
        sensor_angles = [0, np.pi/2, -np.pi/2, np.pi]  # front, left, right, rear
        
        for i, distance in enumerate(ultrasonic_readings):
            if distance < 350:  # Only process close readings
                self.slam_mapper.add_obstacle(distance, sensor_angles[i])
    
    def calculate_movement(self, action_data):
        """Calculate movement vector and heading change"""
        speed = action_data['speed']
        action = action_data['action']
        
        movement = [0, 0]
        heading_change = 0
        
        if action == 'straight':
            movement = [speed * 20, 0]  # Move forward
        elif action == 'left':
            movement = [speed * 15, 0]
            heading_change = -0.1  # Turn left
        elif action == 'right':
            movement = [speed * 15, 0]
            heading_change = 0.1   # Turn right
        
        return movement, heading_change
    
    def emergency_stop(self):
        """Emergency stop function"""
        logger.critical("EMERGENCY STOP ACTIVATED!")
        self.motor_controller.stop_all_motors()
        self.mining_active = False
        self.returning_to_dock = False
        if self.warning_led:
            self.warning_led.on()
        self.running = False
    
    def navigate_to_waypoint(self, waypoint):
        """Navigate to a specific waypoint"""
        target_x, target_y = waypoint['x'], waypoint['y']
        current_x, current_y = self.hardware.position
        
        # Calculate distance and direction
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.sqrt(dx*dx + dy*dy)
        target_heading = math.degrees(math.atan2(dy, dx))
        
        logger.info(f"Navigating to {waypoint['name']} at ({target_x}, {target_y}), distance: {distance:.1f}")
        
        # Simple navigation logic
        tolerance = 50  # Distance tolerance
        
        while distance > tolerance and self.running and self.mining_active:
            # Read sensors for obstacle avoidance
            sensors = self.hardware.read_sensors()
            
            # Check for obstacles
            if sensors[0] < 30:  # Front sensor
                logger.info("Obstacle detected, turning right")
                self.hardware.turn_right(30)
                time.sleep(0.5)
                continue
            
            # Adjust heading towards target
            heading_diff = target_heading - self.hardware.heading
            if heading_diff > 180:
                heading_diff -= 360
            elif heading_diff < -180:
                heading_diff += 360
            
            if abs(heading_diff) > 10:
                if heading_diff > 0:
                    self.hardware.turn_left(min(15, abs(heading_diff)))
                else:
                    self.hardware.turn_right(min(15, abs(heading_diff)))
                time.sleep(0.2)
            else:
                # Move forward
                self.hardware.move_forward(0.5)
                time.sleep(0.5)
            
            # Recalculate distance
            current_x, current_y = self.hardware.position
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Update total distance
            self.total_distance += 5  # Approximate distance per step
        
        if distance <= tolerance:
            logger.info(f"Reached waypoint: {waypoint['name']}")
            return True
        else:
            logger.info(f"Navigation to {waypoint['name']} interrupted")
            return False
    
    def perform_mining(self, waypoint):
        """Perform mining operation at waypoint"""
        logger.info(f"Starting mining at {waypoint['name']}")
        
        # Simulate mining operation
        mining_time = 3  # seconds
        for i in range(mining_time):
            if not self.mining_active:
                break
            logger.info(f"Mining... {i+1}/{mining_time}")
            time.sleep(1)
        
        if self.mining_active:
            # Simulate collecting minerals
            minerals_found = random.randint(1, 5)
            self.minerals_collected += minerals_found
            logger.info(f"Mining complete! Collected {minerals_found} minerals")
            
            # Mark waypoint as completed
            self.mark_waypoint_completed(waypoint['id'])
            self.waypoints_completed += 1
            return True
        else:
            logger.info("Mining interrupted")
            return False
    
    def mark_waypoint_completed(self, waypoint_id):
        """Mark waypoint as completed in database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE waypoints SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (waypoint_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"Waypoint {waypoint_id} marked as completed")
        except Exception as e:
            logger.error(f"Error marking waypoint completed: {e}")
    
    def main_loop(self):
        """Main control loop"""
        self.initialize_camera()
        self.running = True
        
        if self.status_led:
            self.status_led.on()
        
        logger.info("Starting autonomous mining vehicle...")
        logger.info(f"Camera available: {self.camera_available}")
        
        while self.running:
            try:
                # Read sensor data (always available)
                ultrasonic_readings = self.sensor_array.read_all_sensors()
                
                # Default action from neural network
                action_data = self.nn_model.predict_action_sensors_only(ultrasonic_readings)
                
                # Override with navigation if mining is active
                if self.mining_active or self.returning_to_dock:
                    current_waypoint = self.waypoint_navigator.get_next_waypoint()
                    
                    if current_waypoint:
                        nav_action = self.waypoint_navigator.calculate_navigation_action(
                            self.slam_mapper.robot_position, 
                            self.slam_mapper.robot_heading
                        )
                        
                        if nav_action:
                            if nav_action['action'] == 'waypoint_reached':
                                if current_waypoint['type'] == 'mining':
                                    self.waypoints_completed += 1
                                    self.minerals_collected += 1
                                elif current_waypoint['type'] == 'dock':
                                    logger.info("Reached docking station")
                                    self.stop_mining_operation()
                                
                                # Stop briefly at waypoint
                                action_data = {
                                    'action': 'stop',
                                    'speed': 0.0,
                                    'obstacle_detected': False,
                                    'action_confidence': 1.0,
                                    'obstacle_confidence': 0.0
                                }
                                time.sleep(3)  # Pause at waypoint
                                
                            elif nav_action['action'] in ['turn_left', 'turn_right', 'move_forward']:
                                # Only override if no immediate obstacles
                                if not action_data['obstacle_detected']:
                                    if nav_action['action'] == 'turn_left':
                                        action_data['action'] = 'left'
                                    elif nav_action['action'] == 'turn_right':
                                        action_data['action'] = 'right'
                                    elif nav_action['action'] == 'move_forward':
                                        action_data['action'] = 'straight'
                                    
                                    action_data['speed'] = min(0.4, action_data['speed'])  # Slower for navigation
                    
                    else:
                        # No more waypoints, return to dock if mining was active
                        if self.mining_active and not self.returning_to_dock:
                            logger.info("All waypoints completed, returning to dock")
                            self.return_to_dock()
                
                # Control motors
                self.motor_controller.move_vehicle(action_data['action'], action_data['speed'])
                
                # Update LEDs
                if self.warning_led:
                    if action_data['obstacle_detected']:
                        self.warning_led.on()
                    else:
                        self.warning_led.off()
                
                # Calculate movement and update SLAM
                movement, heading_change = self.calculate_movement(action_data)
                self.slam_mapper.update_position(movement, heading_change)
                
                # Process sensor data for mapping
                self.process_sensor_data(ultrasonic_readings)
                
                # Log status
                status_msg = f"Action: {action_data['action']}, Speed: {action_data['speed']:.2f}, "
                status_msg += f"Obstacles: {action_data['obstacle_detected']}, "
                status_msg += f"Position: {self.slam_mapper.robot_position}"
                
                if self.mining_active:
                    status_msg += f", Mining: Active, Waypoints: {self.waypoints_completed}"
                elif self.returning_to_dock:
                    status_msg += ", Status: Returning to dock"
                
                logger.info(status_msg)
                
                time.sleep(0.2)  # 5 FPS for stability
                
            except KeyboardInterrupt:
                logger.info("Stopping vehicle...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.motor_controller.stop_all_motors()
                time.sleep(1)
        
        self.cleanup()
    
    def get_status_data(self):
        """Get current vehicle status for server"""
        ultrasonic_readings = self.sensor_array.read_all_sensors()
        action_data = self.nn_model.predict_action_sensors_only(ultrasonic_readings)
        
        return {
            'timestamp': time.time(),
            'position': self.slam_mapper.robot_position,
            'heading': float(self.slam_mapper.robot_heading),
            'sensor_data': {
                'ultrasonic': ultrasonic_readings,
                'camera_available': self.camera_available
            },
            'action_data': action_data,
            'map_data': self.slam_mapper.export_map_data(),
            'system_status': {
                'running': self.running,
                'camera_available': self.camera_available,
                'emergency_stop': not self.running,
                'mining_active': self.mining_active,
                'returning_to_dock': self.returning_to_dock,
                'current_waypoint': self.waypoint_navigator.current_waypoint,
                'waypoints_completed': self.waypoints_completed,
                'minerals_collected': self.minerals_collected,
                'total_distance': self.slam_mapper.total_distance
            },
            'connection_info': {
                'wifi_connected': True,  # Assume connected if responding
                'bluetooth_connected': False,  # Placeholder
                'last_update': time.time()
            }
        }
    
    def cleanup(self):
        """Cleanup all resources"""
        self.running = False
        self.end_mining_session()
        self.motor_controller.cleanup()
        
        if self.camera:
            self.camera.release()
        
        if self.status_led:
            self.status_led.off()
        if self.warning_led:
            self.warning_led.off()
            
        logger.info("Vehicle controller cleanup completed")

if __name__ == "__main__":
    controller = VehicleController()
    controller.running = True
    
    try:
        controller.main_loop()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        controller.cleanup()
</merged_code>
