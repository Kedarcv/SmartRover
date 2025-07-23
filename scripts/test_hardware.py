#!/usr/bin/env python3
"""
SmartRover Hardware Test Script
This script tests all hardware components to ensure proper functionality
"""

import time
import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

try:
    import RPi.GPIO as GPIO
    from gpiozero import DistanceSensor, LED, Button, PWMOutputDevice
    import cv2
    import numpy as np
    from vehicle_controller import L298NMotorController, UltrasonicSensorArray
    from gpio_pin_mapping import gpio_config
    GPIO_AVAILABLE = True
except ImportError as e:
    print(f"GPIO libraries not available: {e}")
    print("Running in simulation mode...")
    GPIO_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HardwareTest:
    def __init__(self):
        self.gpio_available = GPIO_AVAILABLE
        self.test_results = {}
        
        if self.gpio_available:
            self.setup_hardware()
        else:
            logger.warning("GPIO not available - running in simulation mode")
    
    def setup_hardware(self):
        """Setup hardware components for testing"""
        try:
            # Motor pins
            self.motor_pins = gpio_config.get_motor_pins()
            
            # Sensor pins
            self.sensor_pins = gpio_config.get_sensor_pins()
            
            # LED pins
            self.led_pins = gpio_config.get_led_pins()
            
            # Button pins
            self.button_pins = gpio_config.get_button_pins()
            
            logger.info("Hardware configuration loaded")
            
        except Exception as e:
            logger.error(f"Failed to setup hardware: {e}")
            self.gpio_available = False
    
    def test_gpio_basic(self):
        """Test basic GPIO functionality"""
        logger.info("Testing basic GPIO functionality...")
        
        if not self.gpio_available:
            self.test_results['gpio_basic'] = {'status': 'skipped', 'reason': 'GPIO not available'}
            return False
        
        try:
            # Test GPIO mode setting
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Test a simple output pin
            test_pin = 18  # Use motor pin for test
            GPIO.setup(test_pin, GPIO.OUT)
            
            # Toggle pin
            GPIO.output(test_pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(test_pin, GPIO.LOW)
            
            self.test_results['gpio_basic'] = {'status': 'passed', 'pin_tested': test_pin}
            logger.info("✓ Basic GPIO test passed")
            return True
            
        except Exception as e:
            self.test_results['gpio_basic'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ Basic GPIO test failed: {e}")
            return False
    
    def test_motors(self):
        """Test motor controller"""
        logger.info("Testing motor controller...")
        
        if not self.gpio_available:
            self.test_results['motors'] = {'status': 'skipped', 'reason': 'GPIO not available'}
            return False
        
        try:
            # Setup motor pins
            motor_pins = self.motor_pins
            
            # Setup all motor control pins
            for pin_name, pin_num in motor_pins.items():
                if pin_name in ['ENA', 'ENB']:
                    # PWM pins
                    GPIO.setup(pin_num, GPIO.OUT)
                else:
                    # Direction pins
                    GPIO.setup(pin_num, GPIO.OUT)
            
            # Test motor A
            GPIO.output(motor_pins['IN1'], GPIO.HIGH)
            GPIO.output(motor_pins['IN2'], GPIO.LOW)
            
            # Test motor B
            GPIO.output(motor_pins['IN3'], GPIO.HIGH)
            GPIO.output(motor_pins['IN4'], GPIO.LOW)
            
            # Test PWM
            pwm_a = GPIO.PWM(motor_pins['ENA'], 1000)
            pwm_b = GPIO.PWM(motor_pins['ENB'], 1000)
            
            pwm_a.start(50)  # 50% duty cycle
            pwm_b.start(50)
            
            time.sleep(1)  # Run for 1 second
            
            pwm_a.stop()
            pwm_b.stop()
            
            # Stop motors
            GPIO.output(motor_pins['IN1'], GPIO.LOW)
            GPIO.output(motor_pins['IN2'], GPIO.LOW)
            GPIO.output(motor_pins['IN3'], GPIO.LOW)
            GPIO.output(motor_pins['IN4'], GPIO.LOW)
            
            self.test_results['motors'] = {'status': 'passed', 'pins_tested': motor_pins}
            logger.info("✓ Motor controller test passed")
            return True
            
        except Exception as e:
            self.test_results['motors'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ Motor controller test failed: {e}")
            return False
    
    def test_ultrasonic_sensor(self):
        """Test ultrasonic sensor"""
        logger.info("Testing ultrasonic sensor...")
        
        if not self.gpio_available:
            self.test_results['ultrasonic'] = {'status': 'skipped', 'reason': 'GPIO not available'}
            return False
        
        try:
            sensor_pins = self.sensor_pins
            
            # Create sensor object
            sensor = DistanceSensor(
                echo=sensor_pins['ECHO'],
                trigger=sensor_pins['TRIG'],
                max_distance=4
            )
            
            # Take multiple readings
            readings = []
            for i in range(5):
                distance = sensor.distance * 100  # Convert to cm
                readings.append(distance)
                time.sleep(0.2)
            
            avg_distance = sum(readings) / len(readings)
            
            # Validate readings
            if 2 <= avg_distance <= 400:  # Reasonable range
                self.test_results['ultrasonic'] = {
                    'status': 'passed',
                    'average_distance': avg_distance,
                    'readings': readings,
                    'pins': sensor_pins
                }
                logger.info(f"✓ Ultrasonic sensor test passed - Average distance: {avg_distance:.1f}cm")
                return True
            else:
                self.test_results['ultrasonic'] = {
                    'status': 'warning',
                    'reason': 'Distance readings out of expected range',
                    'average_distance': avg_distance,
                    'readings': readings
                }
                logger.warning(f"⚠ Ultrasonic sensor readings unusual: {avg_distance:.1f}cm")
                return False
                
        except Exception as e:
            self.test_results['ultrasonic'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ Ultrasonic sensor test failed: {e}")
            return False
    
    def test_leds(self):
        """Test status LEDs"""
        logger.info("Testing status LEDs...")
        
        if not self.gpio_available:
            self.test_results['leds'] = {'status': 'skipped', 'reason': 'GPIO not available'}
            return False
        
        try:
            led_pins = self.led_pins
            leds = {}
            
            # Setup LEDs
            for led_name, pin_num in led_pins.items():
                leds[led_name] = LED(pin_num)
            
            # Test each LED
            for led_name, led in leds.items():
                logger.info(f"Testing {led_name} LED...")
                led.on()
                time.sleep(0.5)
                led.off()
                time.sleep(0.2)
            
            # Test blinking pattern
            for i in range(3):
                for led in leds.values():
                    led.on()
                time.sleep(0.2)
                for led in leds.values():
                    led.off()
                time.sleep(0.2)
            
            self.test_results['leds'] = {'status': 'passed', 'pins_tested': led_pins}
            logger.info("✓ LED test passed")
            return True
            
        except Exception as e:
            self.test_results['leds'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ LED test failed: {e}")
            return False
    
    def test_buttons(self):
        """Test input buttons"""
        logger.info("Testing input buttons...")
        
        if not self.gpio_available:
            self.test_results['buttons'] = {'status': 'skipped', 'reason': 'GPIO not available'}
            return False
        
        try:
            button_pins = self.button_pins
            buttons = {}
            
            # Setup buttons
            for button_name, pin_num in button_pins.items():
                buttons[button_name] = Button(pin_num, pull_up=True)
            
            # Test button states
            button_states = {}
            for button_name, button in buttons.items():
                button_states[button_name] = not button.is_pressed  # Inverted due to pull-up
            
            self.test_results['buttons'] = {
                'status': 'passed',
                'pins_tested': button_pins,
                'states': button_states
            }
            logger.info(f"✓ Button test passed - States: {button_states}")
            return True
            
        except Exception as e:
            self.test_results['buttons'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ Button test failed: {e}")
            return False
    
    def test_camera(self):
        """Test camera module"""
        logger.info("Testing camera module...")
        
        try:
            # Try to open camera
            camera = cv2.VideoCapture(0)
            
            if not camera.isOpened():
                self.test_results['camera'] = {'status': 'failed', 'reason': 'Camera not detected'}
                logger.error("✗ Camera not detected")
                return False
            
            # Set camera properties
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_FPS, 30)
            
            # Capture a few frames
            frames_captured = 0
            for i in range(5):
                ret, frame = camera.read()
                if ret:
                    frames_captured += 1
                time.sleep(0.1)
            
            camera.release()
            
            if frames_captured >= 3:
                self.test_results['camera'] = {
                    'status': 'passed',
                    'frames_captured': frames_captured,
                    'resolution': '640x480'
                }
                logger.info(f"✓ Camera test passed - Captured {frames_captured}/5 frames")
                return True
            else:
                self.test_results['camera'] = {
                    'status': 'failed',
                    'reason': 'Insufficient frames captured',
                    'frames_captured': frames_captured
                }
                logger.error(f"✗ Camera test failed - Only captured {frames_captured}/5 frames")
                return False
                
        except Exception as e:
            self.test_results['camera'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ Camera test failed: {e}")
            return False
    
    def test_system_resources(self):
        """Test system resources"""
        logger.info("Testing system resources...")
        
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Temperature (Raspberry Pi specific)
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read()) / 1000.0
            except:
                temp = None
            
            self.test_results['system_resources'] = {
                'status': 'passed',
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': (disk.used / disk.total) * 100,
                'temperature': temp
            }
            
            logger.info(f"✓ System resources test passed")
            logger.info(f"  CPU: {cpu_percent:.1f}%")
            logger.info(f"  Memory: {memory.percent:.1f}%")
            logger.info(f"  Disk: {(disk.used / disk.total) * 100:.1f}%")
            if temp:
                logger.info(f"  Temperature: {temp:.1f}°C")
            
            return True
            
        except Exception as e:
            self.test_results['system_resources'] = {'status': 'failed', 'error': str(e)}
            logger.error(f"✗ System resources test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all hardware tests"""
        logger.info("Starting SmartRover hardware tests...")
        logger.info("=" * 50)
        
        tests = [
            ('Basic GPIO', self.test_gpio_basic),
            ('Motor Controller', self.test_motors),
            ('Ultrasonic Sensor', self.test_ultrasonic_sensor),
            ('Status LEDs', self.test_leds),
            ('Input Buttons', self.test_buttons),
            ('Camera Module', self.test_camera),
            ('System Resources', self.test_system_resources)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n--- Testing {test_name} ---")
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                logger.error(f"Test {test_name} crashed: {e}")
        
        # Cleanup GPIO
        if self.gpio_available:
            try:
                GPIO.cleanup()
            except:
                pass
        
        # Print summary
        logger.info("\n" + "=" * 50)
        logger.info("HARDWARE TEST SUMMARY")
        logger.info("=" * 50)
        
        for test_name, result in self.test_results.items():
            status = result['status']
            if status == 'passed':
                logger.info(f"✓ {test_name.upper()}: PASSED")
            elif status == 'failed':
                logger.error(f"✗ {test_name.upper()}: FAILED - {result.get('error', result.get('reason', 'Unknown'))}")
            elif status == 'warning':
                logger.warning(f"⚠ {test_name.upper()}: WARNING - {result.get('reason', 'Unknown')}")
            elif status == 'skipped':
                logger.info(f"- {test_name.upper()}: SKIPPED - {result.get('reason', 'Unknown')}")
        
        logger.info(f"\nTests passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            logger.info("🎉 All tests passed! Hardware is ready for operation.")
            return True
        else:
            logger.warning(f"⚠ {total_tests - passed_tests} test(s) failed. Check hardware connections.")
            return False
    
    def export_test_results(self, filename='hardware_test_results.json'):
        """Export test results to JSON file"""
        import json
        
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"Test results exported to {filename}")

def main():
    """Main test function"""
    print("SmartRover Hardware Test Suite")
    print("==============================")
    
    tester = HardwareTest()
    success = tester.run_all_tests()
    tester.export_test_results()
    
    if success:
        print("\n🎉 All hardware tests completed successfully!")
        print("Your SmartRover is ready for operation.")
        sys.exit(0)
    else:
        print("\n⚠ Some hardware tests failed.")
        print("Please check connections and try again.")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Hardware test script for mining vehicle")
        print("Usage: sudo python3 test_hardware.py")
        print("\nThis script will test:")
        print("- Camera functionality")
        print("- Ultrasonic sensors")
        print("- Status LEDs and emergency button")
        print("- Motor controllers")
        sys.exit(0)
    
    main()
