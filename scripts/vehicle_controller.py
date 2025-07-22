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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        """Initialize L298N motor controller for 4 motors"""
        # Motor A (Front Left)
        self.MOTOR_A_IN1 = 18
        self.MOTOR_A_IN2 = 19
        self.MOTOR_A_ENA = 12
        
        # Motor B (Front Right)
        self.MOTOR_B_IN3 = 20
        self.MOTOR_B_IN4 = 21
        self.MOTOR_B_ENB = 13
        
        # Motor C (Rear Left)
        self.MOTOR_C_IN1 = 22
        self.MOTOR_C_IN2 = 23
        self.MOTOR_C_ENA = 16
        
        # Motor D (Rear Right)
        self.MOTOR_D_IN3 = 24
        self.MOTOR_D_IN4 = 25
        self.MOTOR_D_ENB = 26
        
        self.setup_motors()
        
    def setup_motors(self):
        """Setup GPIO pins for motor control"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup all motor pins
        motor_pins = [
            self.MOTOR_A_IN1, self.MOTOR_A_IN2, self.MOTOR_A_ENA,
            self.MOTOR_B_IN3, self.MOTOR_B_IN4, self.MOTOR_B_ENB,
            self.MOTOR_C_IN1, self.MOTOR_C_IN2, self.MOTOR_C_ENA,
            self.MOTOR_D_IN3, self.MOTOR_D_IN4, self.MOTOR_D_ENB
        ]
        
        for pin in motor_pins:
            GPIO.setup(pin, GPIO.OUT)
        
        # Setup PWM for speed control
        self.pwm_a = GPIO.PWM(self.MOTOR_A_ENA, 1000)
        self.pwm_b = GPIO.PWM(self.MOTOR_B_ENB, 1000)
        self.pwm_c = GPIO.PWM(self.MOTOR_C_ENA, 1000)
        self.pwm_d = GPIO.PWM(self.MOTOR_D_ENB, 1000)
        
        # Start PWM
        self.pwm_a.start(0)
        self.pwm_b.start(0)
        self.pwm_c.start(0)
        self.pwm_d.start(0)
        
        logger.info("L298N motor controller initialized")
    
    def set_motor_speed(self, motor, speed, direction):
        """Set individual motor speed and direction"""
        speed_percent = max(0, min(100, speed * 100))
        
        if motor == 'A':  # Front Left
            self.pwm_a.ChangeDutyCycle(speed_percent)
            if direction == 'forward':
                GPIO.output(self.MOTOR_A_IN1, GPIO.HIGH)
                GPIO.output(self.MOTOR_A_IN2, GPIO.LOW)
            elif direction == 'backward':
                GPIO.output(self.MOTOR_A_IN1, GPIO.LOW)
                GPIO.output(self.MOTOR_A_IN2, GPIO.HIGH)
            else:
                GPIO.output(self.MOTOR_A_IN1, GPIO.LOW)
                GPIO.output(self.MOTOR_A_IN2, GPIO.LOW)
                
        elif motor == 'B':  # Front Right
            self.pwm_b.ChangeDutyCycle(speed_percent)
            if direction == 'forward':
                GPIO.output(self.MOTOR_B_IN3, GPIO.HIGH)
                GPIO.output(self.MOTOR_B_IN4, GPIO.LOW)
            elif direction == 'backward':
                GPIO.output(self.MOTOR_B_IN3, GPIO.LOW)
                GPIO.output(self.MOTOR_B_IN4, GPIO.HIGH)
            else:
                GPIO.output(self.MOTOR_B_IN3, GPIO.LOW)
                GPIO.output(self.MOTOR_B_IN4, GPIO.LOW)
                
        elif motor == 'C':  # Rear Left
            self.pwm_c.ChangeDutyCycle(speed_percent)
            if direction == 'forward':
                GPIO.output(self.MOTOR_C_IN1, GPIO.HIGH)
                GPIO.output(self.MOTOR_C_IN2, GPIO.LOW)
            elif direction == 'backward':
                GPIO.output(self.MOTOR_C_IN1, GPIO.LOW)
                GPIO.output(self.MOTOR_C_IN2, GPIO.HIGH)
            else:
                GPIO.output(self.MOTOR_C_IN1, GPIO.LOW)
                GPIO.output(self.MOTOR_C_IN2, GPIO.LOW)
                
        elif motor == 'D':  # Rear Right
            self.pwm_d.ChangeDutyCycle(speed_percent)
            if direction == 'forward':
                GPIO.output(self.MOTOR_D_IN3, GPIO.HIGH)
                GPIO.output(self.MOTOR_D_IN4, GPIO.LOW)
            elif direction == 'backward':
                GPIO.output(self.MOTOR_D_IN3, GPIO.LOW)
                GPIO.output(self.MOTOR_D_IN4, GPIO.HIGH)
            else:
                GPIO.output(self.MOTOR_D_IN3, GPIO.LOW)
                GPIO.output(self.MOTOR_D_IN4, GPIO.LOW)
    
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
        self.set_motor_speed('A', speed, 'forward')  # Front Left
        self.set_motor_speed('B', speed, 'forward')  # Front Right
        self.set_motor_speed('C', speed, 'forward')  # Rear Left
        self.set_motor_speed('D', speed, 'forward')  # Rear Right
    
    def move_backward(self, speed):
        """Move vehicle backward"""
        self.set_motor_speed('A', speed, 'backward')
        self.set_motor_speed('B', speed, 'backward')
        self.set_motor_speed('C', speed, 'backward')
        self.set_motor_speed('D', speed, 'backward')
    
    def turn_left(self, speed):
        """Turn vehicle left"""
        self.set_motor_speed('A', speed * 0.3, 'forward')  # Slow left motors
        self.set_motor_speed('B', speed, 'forward')        # Full right motors
        self.set_motor_speed('C', speed * 0.3, 'forward')
        self.set_motor_speed('D', speed, 'forward')
    
    def turn_right(self, speed):
        """Turn vehicle right"""
        self.set_motor_speed('A', speed, 'forward')        # Full left motors
        self.set_motor_speed('B', speed * 0.3, 'forward')  # Slow right motors
        self.set_motor_speed('C', speed, 'forward')
        self.set_motor_speed('D', speed * 0.3, 'forward')
    
    def stop_all_motors(self):
        """Stop all motors"""
        self.set_motor_speed('A', 0, 'stop')
        self.set_motor_speed('B', 0, 'stop')
        self.set_motor_speed('C', 0, 'stop')
        self.set_motor_speed('D', 0, 'stop')
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        self.stop_all_motors()
        self.pwm_a.stop()
        self.pwm_b.stop()
        self.pwm_c.stop()
        self.pwm_d.stop()
        GPIO.cleanup()

class UltrasonicSensorArray:
    def __init__(self):
        """Initialize 4 ultrasonic sensors"""
        try:
            self.sensors = {
                'front': DistanceSensor(echo=24, trigger=23, max_distance=4),
                'left': DistanceSensor(echo=8, trigger=25, max_distance=4),
                'right': DistanceSensor(echo=1, trigger=7, max_distance=4),
                'rear': DistanceSensor(echo=16, trigger=12, max_distance=4)
            }
            logger.info("Ultrasonic sensors initialized")
        except Exception as e:
            logger.error(f"Failed to initialize sensors: {e}")
            self.sensors = {}
    
    def read_all_sensors(self):
        """Read all ultrasonic sensors"""
        readings = []
        sensor_order = ['front', 'left', 'right', 'rear']
        
        for direction in sensor_order:
            try:
                if direction in self.sensors:
                    distance = self.sensors[direction].distance * 100  # Convert to cm
                    readings.append(min(distance, 400))  # Cap at 400cm
                else:
                    readings.append(400)  # Default max range if sensor unavailable
            except Exception as e:
                logger.warning(f"Error reading {direction} sensor: {e}")
                readings.append(400)
        
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
            'timestamp': time.time()
        }

class VehicleController:
    def __init__(self, server_port=5000):
        self.nn_model = MiningVehicleNN()
        self.motor_controller = L298NMotorController()
        self.sensor_array = UltrasonicSensorArray()
        self.slam_mapper = SLAMMapper()
        self.server_port = server_port
        self.running = False
        self.camera = None
        self.camera_available = False
        
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
    
    def capture_frame(self):
        """Capture frame from camera if available"""
        if self.camera_available and self.camera:
            ret, frame = self.camera.read()
            if ret:
                return frame
        return None
    
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
        if self.warning_led:
            self.warning_led.on()
        self.running = False
    
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
                
                # Get neural network prediction (sensor-only mode)
                action_data = self.nn_model.predict_action_sensors_only(ultrasonic_readings)
                
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
                logger.info(f"Action: {action_data['action']}, Speed: {action_data['speed']:.2f}, "
                          f"Obstacles: {action_data['obstacle_detected']}, "
                          f"Position: {self.slam_mapper.robot_position}")
                
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
                'emergency_stop': not self.running
            }
        }
    
    def cleanup(self):
        """Cleanup all resources"""
        self.running = False
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
    controller.main_loop()
