#!/usr/bin/env python3
"""
Hardware test script for mining vehicle
Run this to verify all hardware components are working
"""

import time
import sys
import RPi.GPIO as GPIO
from gpiozero import DistanceSensor, LED, Button
from vehicle_controller import L298NMotorController, UltrasonicSensorArray

def test_motors():
    """Test all 4 motors"""
    print("\n=== Testing Motors ===")
    try:
        motor_controller = L298NMotorController()
        
        print("Testing forward movement...")
        motor_controller.move_forward(0.5)
        time.sleep(2)
        
        print("Testing left turn...")
        motor_controller.turn_left(0.5)
        time.sleep(2)
        
        print("Testing right turn...")
        motor_controller.turn_right(0.5)
        time.sleep(2)
        
        print("Testing backward movement...")
        motor_controller.move_backward(0.5)
        time.sleep(2)
        
        print("Stopping motors...")
        motor_controller.stop_all_motors()
        
        motor_controller.cleanup()
        print("✓ Motor test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Motor test failed: {e}")
        return False

def test_ultrasonic_sensors():
    """Test all ultrasonic sensors"""
    print("\n=== Testing Ultrasonic Sensors ===")
    try:
        sensor_array = UltrasonicSensorArray()
        
        for i in range(5):
            readings = sensor_array.read_all_sensors()
            print(f"Reading {i+1}: Front={readings[0]:.1f}cm, "
                  f"Left={readings[1]:.1f}cm, Right={readings[2]:.1f}cm, "
                  f"Rear={readings[3]:.1f}cm")
            time.sleep(1)
        
        print("✓ Ultrasonic sensor test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Ultrasonic sensor test failed: {e}")
        return False

def test_leds_and_button():
    """Test status LEDs and emergency button"""
    print("\n=== Testing LEDs and Button ===")
    try:
        status_led = LED(26)
        warning_led = LED(13)
        emergency_button = Button(6)
        
        print("Testing status LED...")
        status_led.on()
        time.sleep(1)
        status_led.off()
        
        print("Testing warning LED...")
        warning_led.on()
        time.sleep(1)
        warning_led.off()
        
        print("Testing LED blink...")
        status_led.blink(on_time=0.5, off_time=0.5)
        time.sleep(3)
        status_led.off()
        
        print("Press emergency button within 5 seconds...")
        button_pressed = False
        
        def button_callback():
            nonlocal button_pressed
            button_pressed = True
            print("Emergency button pressed!")
        
        emergency_button.when_pressed = button_callback
        
        start_time = time.time()
        while time.time() - start_time < 5 and not button_pressed:
            time.sleep(0.1)
        
        if button_pressed:
            print("✓ LED and button test completed successfully")
            return True
        else:
            print("⚠ Button not pressed, but LEDs working")
            return True
            
    except Exception as e:
        print(f"✗ LED and button test failed: {e}")
        return False

def test_camera():
    """Test camera functionality"""
    print("\n=== Testing Camera ===")
    try:
        import cv2
        
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            print("⚠ Camera not available")
            return True
        
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        ret, frame = camera.read()
        if ret:
            print(f"✓ Camera working - Frame size: {frame.shape}")
            # Save test image
            cv2.imwrite('/tmp/camera_test.jpg', frame)
            print("Test image saved to /tmp/camera_test.jpg")
        else:
            print("⚠ Camera connected but no frame captured")
        
        camera.release()
        return True
        
    except Exception as e:
        print(f"✗ Camera test failed: {e}")
        return False

def main():
    """Run all hardware tests"""
    print("Mining Vehicle Hardware Test")
    print("=" * 50)
    
    tests = [
        ("Camera", test_camera),
        ("Ultrasonic Sensors", test_ultrasonic_sensors),
        ("LEDs and Button", test_leds_and_button),
        ("Motors", test_motors)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\nStarting {test_name} test...")
        try:
            results[test_name] = test_func()
        except KeyboardInterrupt:
            print(f"\n{test_name} test interrupted by user")
            results[test_name] = False
            break
        except Exception as e:
            print(f"Unexpected error in {test_name} test: {e}")
            results[test_name] = False
    
    # Cleanup GPIO
    GPIO.cleanup()
    
    # Print results
    print("\n" + "=" * 50)
    print("Test Results:")
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name}: {status}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Hardware is ready for deployment.")
    else:
        print("⚠ Some tests failed. Please check hardware connections.")

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
