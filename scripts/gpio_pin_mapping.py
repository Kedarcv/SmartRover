#!/usr/bin/env python3
"""
GPIO Pin Mapping Configuration for SmartRover Mining Vehicle
This module defines the hardware pin configuration for the Raspberry Pi
"""

import logging

logger = logging.getLogger(__name__)

class GPIOPinMapping:
    """GPIO pin mapping configuration for SmartRover hardware"""
    
    def __init__(self):
        # Motor controller pins (L298N)
        self.MOTOR_PINS = {
            'IN1': 18,  # Motor 1 Direction Pin 1
            'IN2': 16,  # Motor 1 Direction Pin 2
            'IN3': 21,  # Motor 2 Direction Pin 1
            'IN4': 23,  # Motor 2 Direction Pin 2
            'ENA': 12,  # Motor 1 Enable (PWM)
            'ENB': 13   # Motor 2 Enable (PWM)
        }
        
        # Ultrasonic sensor pins (HC-SR04)
        self.SENSOR_PINS = {
            'TRIG': 24,  # Ultrasonic Trigger Pin
            'ECHO': 25   # Ultrasonic Echo Pin
        }
        
        # Status LED pins
        self.LED_PINS = {
            'STATUS': 26,   # Green status LED
            'WARNING': 13,  # Red warning LED
            'MINING': 19    # Blue mining operation LED
        }
        
        # Button pins
        self.BUTTON_PINS = {
            'EMERGENCY': 6,  # Emergency stop button
            'START': 5,      # Start operation button
            'STOP': 22       # Stop operation button
        }
        
        # Camera module
        self.CAMERA_CONFIG = {
            'DEVICE': '/dev/video0',
            'WIDTH': 640,
            'HEIGHT': 480,
            'FPS': 30
        }
        
        # I2C devices (if used)
        self.I2C_DEVICES = {
            'IMU': 0x68,        # MPU6050 IMU
            'COMPASS': 0x1E,    # HMC5883L Compass
            'DISPLAY': 0x3C     # OLED Display
        }
        
        # SPI devices (if used)
        self.SPI_DEVICES = {
            'GPS': 0,           # GPS module on SPI0
            'RADIO': 1          # Radio module on SPI1
        }
        
        # PWM configuration
        self.PWM_CONFIG = {
            'FREQUENCY': 1000,  # 1kHz PWM frequency
            'DUTY_CYCLE_MIN': 0,
            'DUTY_CYCLE_MAX': 100
        }
        
        # Safety limits
        self.SAFETY_LIMITS = {
            'MAX_SPEED': 0.8,           # Maximum motor speed (0-1)
            'OBSTACLE_THRESHOLD': 30,    # Minimum distance in cm
            'EMERGENCY_STOP_TIME': 0.1,  # Emergency stop response time
            'SENSOR_TIMEOUT': 1.0        # Sensor read timeout
        }
        
        logger.info("GPIO pin mapping initialized")
        self.log_pin_configuration()
    
    def log_pin_configuration(self):
        """Log the current pin configuration"""
        logger.info("=== SmartRover GPIO Pin Configuration ===")
        logger.info(f"Motor Pins: {self.MOTOR_PINS}")
        logger.info(f"Sensor Pins: {self.SENSOR_PINS}")
        logger.info(f"LED Pins: {self.LED_PINS}")
        logger.info(f"Button Pins: {self.BUTTON_PINS}")
        logger.info("==========================================")
    
    def validate_pins(self):
        """Validate pin configuration for conflicts"""
        all_pins = []
        
        # Collect all pins
        all_pins.extend(self.MOTOR_PINS.values())
        all_pins.extend(self.SENSOR_PINS.values())
        all_pins.extend(self.LED_PINS.values())
        all_pins.extend(self.BUTTON_PINS.values())
        
        # Check for duplicates
        if len(all_pins) != len(set(all_pins)):
            duplicates = [pin for pin in set(all_pins) if all_pins.count(pin) > 1]
            logger.error(f"Pin conflict detected! Duplicate pins: {duplicates}")
            return False
        
        # Check for reserved pins
        reserved_pins = [2, 3, 4, 14, 15, 17, 27]  # I2C, UART, etc.
        conflicts = [pin for pin in all_pins if pin in reserved_pins]
        
        if conflicts:
            logger.warning(f"Using reserved pins (may cause issues): {conflicts}")
        
        logger.info("Pin configuration validation passed")
        return True
    
    def get_motor_config(self):
        """Get motor configuration"""
        return {
            'pins': self.MOTOR_PINS,
            'pwm_frequency': self.PWM_CONFIG['FREQUENCY'],
            'max_speed': self.SAFETY_LIMITS['MAX_SPEED']
        }
    
    def get_sensor_config(self):
        """Get sensor configuration"""
        return {
            'pins': self.SENSOR_PINS,
            'obstacle_threshold': self.SAFETY_LIMITS['OBSTACLE_THRESHOLD'],
            'timeout': self.SAFETY_LIMITS['SENSOR_TIMEOUT']
        }
    
    def get_led_config(self):
        """Get LED configuration"""
        return self.LED_PINS
    
    def get_button_config(self):
        """Get button configuration"""
        return self.BUTTON_PINS
    
    def export_config(self, filename='gpio_config.json'):
        """Export configuration to JSON file"""
        import json
        
        config = {
            'motor_pins': self.MOTOR_PINS,
            'sensor_pins': self.SENSOR_PINS,
            'led_pins': self.LED_PINS,
            'button_pins': self.BUTTON_PINS,
            'camera_config': self.CAMERA_CONFIG,
            'i2c_devices': self.I2C_DEVICES,
            'spi_devices': self.SPI_DEVICES,
            'pwm_config': self.PWM_CONFIG,
            'safety_limits': self.SAFETY_LIMITS
        }
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"GPIO configuration exported to {filename}")

# Create global instance
gpio_config = GPIOPinMapping()

# Validate configuration on import
if not gpio_config.validate_pins():
    logger.error("GPIO pin configuration validation failed!")
else:
    logger.info("GPIO pin configuration loaded successfully")

# Export functions for easy access
def get_motor_pins():
    return gpio_config.MOTOR_PINS

def get_sensor_pins():
    return gpio_config.SENSOR_PINS

def get_led_pins():
    return gpio_config.LED_PINS

def get_button_pins():
    return gpio_config.BUTTON_PINS

def get_safety_limits():
    return gpio_config.SAFETY_LIMITS

if __name__ == "__main__":
    # Test the configuration
    print("SmartRover GPIO Pin Configuration Test")
    print("=====================================")
    
    config = GPIOPinMapping()
    config.validate_pins()
    config.export_config('test_gpio_config.json')
    
    print("\nMotor Configuration:")
    print(config.get_motor_config())
    
    print("\nSensor Configuration:")
    print(config.get_sensor_config())
    
    print("\nConfiguration test completed successfully!")
