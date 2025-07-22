"""
Training script for the mining vehicle neural network
This script generates synthetic training data and trains the model
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
import cv2
import os
from neural_network import MiningVehicleNN

class TrainingDataGenerator:
    def __init__(self):
        self.image_size = (224, 224, 3)
        self.num_samples = 10000
        
    def generate_synthetic_data(self):
        """Generate synthetic training data"""
        print("Generating synthetic training data...")
        
        # Generate camera images (synthetic tunnel/mine environments)
        camera_data = []
        sensor_data = []
        path_labels = []
        speed_labels = []
        obstacle_labels = []
        
        for i in range(self.num_samples):
            # Generate synthetic camera image
            img = self.create_synthetic_mine_image()
            camera_data.append(img)
            
            # Generate sensor readings
            sensors = np.random.uniform(10, 400, 4)  # 4 ultrasonic sensors
            sensor_data.append(sensors)
            
            # Generate labels based on sensor readings
            min_distance = np.min(sensors)
            front_distance = sensors[0]
            left_distance = sensors[1]
            right_distance = sensors[2]
            
            # Path decision logic
            if min_distance < 30:  # Very close obstacle
                path = [0, 0, 0, 1]  # Stop
                speed = 0.0
                obstacle = 1.0
            elif front_distance < 50:  # Obstacle ahead
                if left_distance > right_distance:
                    path = [1, 0, 0, 0]  # Turn left
                else:
                    path = [0, 0, 1, 0]  # Turn right
                speed = 0.3
                obstacle = 1.0
            else:  # Clear path
                path = [0, 1, 0, 0]  # Go straight
                speed = 0.8
                obstacle = 0.0
            
            path_labels.append(path)
            speed_labels.append(speed)
            obstacle_labels.append(obstacle)
            
            if i % 1000 == 0:
                print(f"Generated {i}/{self.num_samples} samples")
        
        return (np.array(camera_data), np.array(sensor_data), 
                np.array(path_labels), np.array(speed_labels), 
                np.array(obstacle_labels))
    
    def create_synthetic_mine_image(self):
        """Create a synthetic mine tunnel image"""
        img = np.zeros((224, 224, 3), dtype=np.uint8)
        
        # Create tunnel walls
        img[:, :50] = [139, 69, 19]  # Brown walls
        img[:, -50:] = [139, 69, 19]
        
        # Add some texture and obstacles
        if np.random.random() > 0.7:
            # Add obstacle
            obstacle_x = np.random.randint(50, 174)
            obstacle_y = np.random.randint(100, 200)
            cv2.rectangle(img, (obstacle_x, obstacle_y), 
                         (obstacle_x + 30, obstacle_y + 40), 
                         (100, 100, 100), -1)
        
        # Add lighting effects
        center_brightness = np.random.randint(50, 150)
        for y in range(224):
            for x in range(50, 174):
                distance_from_center = abs(x - 112)
                brightness = max(0, center_brightness - distance_from_center * 2)
                img[y, x] = [brightness, brightness, brightness]
        
        # Add noise
        noise = np.random.randint(0, 30, (224, 224, 3))
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        return img.astype(np.float32) / 255.0

def train_model():
    """Train the neural network model"""
    print("Starting model training...")
    
    # Initialize model and data generator
    model = MiningVehicleNN()
    data_generator = TrainingDataGenerator()
    
    # Generate training data
    camera_data, sensor_data, path_labels, speed_labels, obstacle_labels = \
        data_generator.generate_synthetic_data()
    
    # Split data into train/validation
    split_idx = int(0.8 * len(camera_data))
    
    train_camera = camera_data[:split_idx]
    train_sensors = sensor_data[:split_idx]
    train_path = path_labels[:split_idx]
    train_speed = speed_labels[:split_idx]
    train_obstacle = obstacle_labels[:split_idx]
    
    val_camera = camera_data[split_idx:]
    val_sensors = sensor_data[split_idx:]
    val_path = path_labels[split_idx:]
    val_speed = speed_labels[split_idx:]
    val_obstacle = obstacle_labels[split_idx:]
    
    print(f"Training samples: {len(train_camera)}")
    print(f"Validation samples: {len(val_camera)}")
    
    # Train the model
    history = model.model.fit(
        [train_camera, train_sensors],
        [train_path, train_speed, train_obstacle],
        validation_data=(
            [val_camera, val_sensors],
            [val_path, val_speed, val_obstacle]
        ),
        epochs=50,
        batch_size=32,
        verbose=1
    )
    
    # Save the trained model
    model.model.save('mining_vehicle_model.h5')
    print("Model saved as 'mining_vehicle_model.h5'")
    
    # Evaluate model
    test_loss = model.model.evaluate(
        [val_camera, val_sensors],
        [val_path, val_speed, val_obstacle],
        verbose=0
    )
    
    print(f"Test Loss: {test_loss}")
    
    return model, history

if __name__ == "__main__":
    trained_model, training_history = train_model()
    print("Training completed successfully!")
