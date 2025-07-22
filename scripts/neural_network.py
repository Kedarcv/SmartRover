import numpy as np
import cv2
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import json
import time
from collections import deque
import threading
import requests

class MiningVehicleNN:
    def __init__(self, input_shape=(224, 224, 3)):
        self.input_shape = input_shape
        self.model = self._build_model()
        self.path_history = deque(maxlen=1000)
        self.obstacle_map = {}
        self.current_position = [0, 0]
        self.heading = 0
        
    def _build_model(self):
        """Build the neural network for path planning and obstacle detection"""
        # Input layers for camera and sensor data
        camera_input = keras.Input(shape=self.input_shape, name='camera')
        sensor_input = keras.Input(shape=(4,), name='sensors')  # ultrasonic sensors
        
        # CNN for camera processing
        x = layers.Conv2D(32, 3, activation='relu')(camera_input)
        x = layers.MaxPooling2D()(x)
        x = layers.Conv2D(64, 3, activation='relu')(x)
        x = layers.MaxPooling2D()(x)
        x = layers.Conv2D(128, 3, activation='relu')(x)
        x = layers.GlobalAveragePooling2D()(x)
        
        # Dense layers for camera features
        camera_features = layers.Dense(128, activation='relu')(x)
        camera_features = layers.Dropout(0.3)(camera_features)
        
        # Process sensor data
        sensor_features = layers.Dense(64, activation='relu')(sensor_input)
        sensor_features = layers.Dense(32, activation='relu')(sensor_features)
        
        # Combine features
        combined = layers.concatenate([camera_features, sensor_features])
        combined = layers.Dense(256, activation='relu')(combined)
        combined = layers.Dropout(0.3)(combined)
        
        # Output layers
        # Path direction (left, straight, right, stop)
        path_output = layers.Dense(4, activation='softmax', name='path')(combined)
        
        # Speed control (0-1)
        speed_output = layers.Dense(1, activation='sigmoid', name='speed')(combined)
        
        # Obstacle detection confidence
        obstacle_output = layers.Dense(1, activation='sigmoid', name='obstacle')(combined)
        
        model = keras.Model(
            inputs=[camera_input, sensor_input],
            outputs=[path_output, speed_output, obstacle_output]
        )
        
        model.compile(
            optimizer='adam',
            loss={
                'path': 'categorical_crossentropy',
                'speed': 'mse',
                'obstacle': 'binary_crossentropy'
            },
            metrics=['accuracy']
        )
        
        return model
    
    def preprocess_camera_data(self, frame):
        """Preprocess camera frame for neural network"""
        # Resize and normalize
        frame = cv2.resize(frame, (224, 224))
        frame = frame.astype(np.float32) / 255.0
        return np.expand_dims(frame, axis=0)
    
    def preprocess_sensor_data(self, ultrasonic_readings):
        """Preprocess ultrasonic sensor data"""
        # Normalize sensor readings (assuming max range of 400cm)
        normalized = np.array(ultrasonic_readings) / 400.0
        return np.expand_dims(normalized, axis=0)
    
    def predict_action(self, camera_frame, sensor_data):
        """Make prediction for vehicle action"""
        camera_processed = self.preprocess_camera_data(camera_frame)
        sensor_processed = self.preprocess_sensor_data(sensor_data)
        
        predictions = self.model.predict([camera_processed, sensor_processed])
        
        path_probs = predictions[0][0]
        speed = predictions[1][0][0]
        obstacle_confidence = predictions[2][0][0]
        
        # Determine action
        action = np.argmax(path_probs)
        action_names = ['left', 'straight', 'right', 'stop']
        
        return {
            'action': action_names[action],
            'action_confidence': float(path_probs[action]),
            'speed': float(speed),
            'obstacle_detected': obstacle_confidence > 0.5,
            'obstacle_confidence': float(obstacle_confidence)
        }

class SLAMMapper:
    def __init__(self):
        self.map_data = np.zeros((1000, 1000), dtype=np.uint8)  # 1000x1000 grid
        self.robot_position = [500, 500]  # Start at center
        self.robot_heading = 0
        self.scale = 10  # cm per pixel
        self.landmarks = []
        
    def update_position(self, movement_vector):
        """Update robot position based on movement"""
        dx, dy = movement_vector
        self.robot_position[0] += int(dx / self.scale)
        self.robot_position[1] += int(dy / self.scale)
        
        # Mark current position as explored
        x, y = self.robot_position
        if 0 <= x < 1000 and 0 <= y < 1000:
            self.map_data[y, x] = 128  # Explored area
    
    def add_obstacle(self, distance, angle):
        """Add obstacle to map based on sensor reading"""
        # Calculate obstacle position
        obstacle_x = self.robot_position[0] + int((distance * np.cos(angle)) / self.scale)
        obstacle_y = self.robot_position[1] + int((distance * np.sin(angle)) / self.scale)
        
        if 0 <= obstacle_x < 1000 and 0 <= obstacle_y < 1000:
            self.map_data[obstacle_y, obstacle_x] = 255  # Obstacle
    
    def get_map_image(self):
        """Get current map as image"""
        map_img = cv2.cvtColor(self.map_data, cv2.COLOR_GRAY2RGB)
        
        # Draw robot position
        cv2.circle(map_img, tuple(self.robot_position), 5, (0, 255, 0), -1)
        
        # Draw heading direction
        end_x = int(self.robot_position[0] + 20 * np.cos(self.robot_heading))
        end_y = int(self.robot_position[1] + 20 * np.sin(self.robot_heading))
        cv2.arrowedLine(map_img, tuple(self.robot_position), (end_x, end_y), (0, 0, 255), 2)
        
        return map_img
    
    def export_map_data(self):
        """Export map data for dashboard"""
        return {
            'map_array': self.map_data.tolist(),
            'robot_position': self.robot_position,
            'robot_heading': float(self.robot_heading),
            'landmarks': self.landmarks,
            'timestamp': time.time()
        }

class VehicleController:
    def __init__(self, server_url="http://localhost:3000"):
        self.nn_model = MiningVehicleNN()
        self.slam_mapper = SLAMMapper()
        self.server_url = server_url
        self.running = False
        self.sensor_data = {'ultrasonic': [0, 0, 0, 0]}
        
    def initialize_camera(self):
        """Initialize camera"""
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
    def read_ultrasonic_sensors(self):
        """Simulate reading from ultrasonic sensors"""
        # In real implementation, this would interface with GPIO pins
        # For simulation, return random values
        import random
        return [
            random.uniform(10, 400),  # Front sensor
            random.uniform(10, 400),  # Left sensor  
            random.uniform(10, 400),  # Right sensor
            random.uniform(10, 400)   # Rear sensor
        ]
    
    def send_data_to_server(self, data):
        """Send sensor and map data to server dashboard"""
        try:
            response = requests.post(f"{self.server_url}/api/vehicle-data", 
                                   json=data, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send data to server: {e}")
            return False
    
    def execute_action(self, action_data):
        """Execute the predicted action"""
        action = action_data['action']
        speed = action_data['speed']
        
        print(f"Executing: {action} at speed {speed:.2f}")
        
        # In real implementation, this would control motors via GPIO
        # For simulation, we'll just update position
        movement = [0, 0]
        
        if action == 'straight':
            movement = [speed * 10, 0]  # Move forward
        elif action == 'left':
            movement = [speed * 7, speed * 7]  # Move diagonally
            self.slam_mapper.robot_heading -= 0.1
        elif action == 'right':
            movement = [speed * 7, -speed * 7]  # Move diagonally
            self.slam_mapper.robot_heading += 0.1
        elif action == 'stop':
            movement = [0, 0]
        
        self.slam_mapper.update_position(movement)
        
        return movement
    
    def process_sensor_data(self, ultrasonic_readings):
        """Process sensor data and update map"""
        for i, distance in enumerate(ultrasonic_readings):
            if distance < 50:  # Obstacle detected within 50cm
                angle = i * (np.pi / 2)  # 0, 90, 180, 270 degrees
                self.slam_mapper.add_obstacle(distance, angle)
    
    def main_loop(self):
        """Main control loop"""
        self.initialize_camera()
        self.running = True
        
        print("Starting autonomous mining vehicle...")
        
        while self.running:
            try:
                # Read camera frame
                ret, frame = self.camera.read()
                if not ret:
                    continue
                
                # Read sensor data
                ultrasonic_readings = self.read_ultrasonic_sensors()
                self.sensor_data['ultrasonic'] = ultrasonic_readings
                
                # Process sensors and update map
                self.process_sensor_data(ultrasonic_readings)
                
                # Get neural network prediction
                action_data = self.nn_model.predict_action(frame, ultrasonic_readings)
                
                # Execute action
                movement = self.execute_action(action_data)
                
                # Prepare data for server
                server_data = {
                    'timestamp': time.time(),
                    'position': self.slam_mapper.robot_position,
                    'heading': float(self.slam_mapper.robot_heading),
                    'sensor_data': self.sensor_data,
                    'action_data': action_data,
                    'map_data': self.slam_mapper.export_map_data(),
                    'movement': movement
                }
                
                # Send data to server
                self.send_data_to_server(server_data)
                
                # Display current map (for debugging)
                map_img = self.slam_mapper.get_map_image()
                cv2.imshow('SLAM Map', map_img)
                cv2.imshow('Camera Feed', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                time.sleep(0.1)  # 10 FPS
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(1)
        
        self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        self.running = False
        if hasattr(self, 'camera'):
            self.camera.release()
        cv2.destroyAllWindows()
        print("Vehicle controller stopped.")

if __name__ == "__main__":
    controller = VehicleController()
    controller.main_loop()
