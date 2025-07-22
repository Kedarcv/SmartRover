"""
Raspberry Pi setup script for the mining vehicle
This script configures GPIO pins and initializes hardware components
"""

import RPi.GPIO as GPIO
import time
import threading
from gpiozero import DistanceSensor, Motor, LED, Button
import cv2
import numpy as np

class RaspberryPiHardware:
    def __init__(self):
        # GPIO pin assignments
        self.MOTOR_LEFT_FORWARD = 18
        self.MOTOR_LEFT_BACKWARD = 19
        self.MOTOR_RIGHT_FORWARD = 20
        self.MOTOR_RIGHT_BACKWARD = 21
        
        # Ultrasonic sensor pins
        self.ULTRASONIC_PINS = {
            'front': {'trigger': 23, 'echo': 24},
            'left': {'trigger': 25, 'echo': 8},
            'right': {'trigger': 7, 'echo': 1},
            'rear': {'trigger': 12, 'echo': 16}
        }
        
        # LED indicators
        self.STATUS_LED = 26
        self.WARNING_LED = 13
        
        # Emergency stop button
        self.EMERGENCY_STOP = 6
        
        self.setup_hardware()
    
    def setup_hardware(self):
        """Initialize all hardware components"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup motors
        self.left_motor = Motor(forward=self.MOTOR_LEFT_FORWARD, 
                               backward=self.MOTOR_LEFT_BACKWARD)
        self.right_motor = Motor(forward=self.MOTOR_RIGHT_FORWARD, 
                                backward=self.MOTOR_RIGHT_BACKWARD)
        
        # Setup ultrasonic sensors
        self.sensors = {}
        for direction, pins in self.ULTRASONIC_PINS.items():
            self.sensors[direction] = DistanceSensor(echo=pins['echo'], 
                                                   trigger=pins['trigger'])
        
        # Setup LEDs
        self.status_led = LED(self.STATUS_LED)
        self.warning_led = LED(self.WARNING_LED)
        
        # Setup emergency stop
        self.emergency_button = Button(self.EMERGENCY_STOP)
        self.emergency_button.when_pressed = self.emergency_stop
        
        # Initialize camera
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print("Hardware initialized successfully")
    
    def read_ultrasonic_sensors(self):
        """Read all ultrasonic sensors"""
        readings = {}
        for direction, sensor in self.sensors.items():
            try:
                distance = sensor.distance * 100  # Convert to cm
                readings[direction] = min(distance, 400)  # Cap at 400cm
            except Exception as e:
                print(f"Error reading {direction} sensor: {e}")
                readings[direction] = 400  # Default to max range
        
        return [readings['front'], readings['left'], 
                readings['right'], readings['rear']]
    
    def control_motors(self, action, speed):
        """Control vehicle movement based on action and speed"""
        if action == 'stop':
            self.left_motor.stop()
            self.right_motor.stop()
        elif action == 'straight':
            self.left_motor.forward(speed)
            self.right_motor.forward(speed)
        elif action == 'left':
            self.left_motor.forward(speed * 0.5)
            self.right_motor.forward(speed)
        elif action == 'right':
            self.left_motor.forward(speed)
            self.right_motor.forward(speed * 0.5)
        elif action == 'reverse':
            self.left_motor.backward(speed)
            self.right_motor.backward(speed)
    
    def capture_frame(self):
        """Capture frame from camera"""
        ret, frame = self.camera.read()
        if ret:
            return frame
        return None
    
    def update_status_leds(self, obstacle_detected):
        """Update status LEDs based on system state"""
        self.status_led.on()  # Always on when system is running
        
        if obstacle_detected:
            self.warning_led.blink(on_time=0.5, off_time=0.5)
        else:
            self.warning_led.off()
    
    def emergency_stop(self):
        """Emergency stop function"""
        print("EMERGENCY STOP ACTIVATED!")
        self.left_motor.stop()
        self.right_motor.stop()
        self.warning_led.on()
        # Could also send emergency signal to server
    
    def cleanup(self):
        """Cleanup GPIO and camera resources"""
        self.left_motor.stop()
        self.right_motor.stop()
        self.camera.release()
        GPIO.cleanup()
        print("Hardware cleanup completed")

# Integration with main vehicle controller
class RaspberryPiVehicleController:
    def __init__(self, server_url="http://your-server.com"):
        from neural_network import VehicleController
        
        self.hardware = RaspberryPiHardware()
        self.controller = VehicleController(server_url)
        self.running = False
    
    def run(self):
        """Main execution loop for Raspberry Pi"""
        self.running = True
        
        try:
            while self.running:
                # Capture camera frame
                frame = self.hardware.capture_frame()
                if frame is None:
                    continue
                
                # Read sensor data
                ultrasonic_readings = self.hardware.read_ultrasonic_sensors()
                
                # Get neural network prediction
                action_data = self.controller.nn_model.predict_action(
                    frame, ultrasonic_readings)
                
                # Control motors based on prediction
                self.hardware.control_motors(
                    action_data['action'], 
                    action_data['speed']
                )
                
                # Update status LEDs
                self.hardware.update_status_leds(
                    action_data['obstacle_detected']
                )
                
                # Update SLAM mapping
                self.controller.slam_mapper.update_position(
                    self.calculate_movement(action_data)
                )
                
                # Process sensor data for mapping
                self.controller.process_sensor_data(ultrasonic_readings)
                
                # Send data to server
                server_data = {
                    'timestamp': time.time(),
                    'position': self.controller.slam_mapper.robot_position,
                    'heading': float(self.controller.slam_mapper.robot_heading),
                    'sensor_data': {'ultrasonic': ultrasonic_readings},
                    'action_data': action_data,
                    'map_data': self.controller.slam_mapper.export_map_data()
                }
                
                self.controller.send_data_to_server(server_data)
                
                time.sleep(0.1)  # 10 FPS
                
        except KeyboardInterrupt:
            print("Stopping vehicle...")
        finally:
            self.cleanup()
    
    def calculate_movement(self, action_data):
        """Calculate movement vector based on action"""
        speed = action_data['speed']
        action = action_data['action']
        
        if action == 'straight':
            return [speed * 10, 0]
        elif action == 'left':
            return [speed * 7, speed * 7]
        elif action == 'right':
            return [speed * 7, -speed * 7]
        else:
            return [0, 0]
    
    def cleanup(self):
        """Cleanup all resources"""
        self.running = False
        self.hardware.cleanup()
        self.controller.cleanup()

if __name__ == "__main__":
    # Run the Raspberry Pi vehicle controller
    pi_controller = RaspberryPiVehicleController("http://your-dashboard-server.com")
    pi_controller.run()
