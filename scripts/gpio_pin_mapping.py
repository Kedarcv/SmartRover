"""
GPIO Pin Mapping for Mining Vehicle
This file documents all GPIO pin assignments for easy reference
"""

# L298N Motor Driver Connections
MOTOR_PINS = {
    # Motor A (Front Left)
    'MOTOR_A_IN1': 18,    # Direction control 1
    'MOTOR_A_IN2': 19,    # Direction control 2
    'MOTOR_A_ENA': 12,    # Speed control (PWM)
    
    # Motor B (Front Right)
    'MOTOR_B_IN3': 20,    # Direction control 1
    'MOTOR_B_IN4': 21,    # Direction control 2
    'MOTOR_B_ENB': 13,    # Speed control (PWM)
    
    # Motor C (Rear Left)
    'MOTOR_C_IN1': 22,    # Direction control 1
    'MOTOR_C_IN2': 23,    # Direction control 2
    'MOTOR_C_ENA': 16,    # Speed control (PWM)
    
    # Motor D (Rear Right)
    'MOTOR_D_IN3': 24,    # Direction control 1
    'MOTOR_D_IN4': 25,    # Direction control 2
    'MOTOR_D_ENB': 26,    # Speed control (PWM)
}

# Ultrasonic Sensor Connections (HC-SR04)
ULTRASONIC_PINS = {
    'front': {'trigger': 23, 'echo': 24},
    'left': {'trigger': 25, 'echo': 8},
    'right': {'trigger': 7, 'echo': 1},
    'rear': {'trigger': 12, 'echo': 16}
}

# Status LEDs and Controls
STATUS_PINS = {
    'STATUS_LED': 26,      # Green LED - System running
    'WARNING_LED': 13,     # Red LED - Obstacle detected
    'EMERGENCY_BUTTON': 6  # Emergency stop button
}

# Power Supply Requirements
POWER_REQUIREMENTS = {
    'raspberry_pi': '5V 3A',
    'motors': '12V 2A per motor (8A total)',
    'sensors': '5V 0.5A total',
    'recommended_battery': '12V 10Ah LiPo or Lead Acid'
}

# Wiring Instructions
WIRING_INSTRUCTIONS = """
L298N Motor Driver Wiring:
- Connect VCC to 12V battery positive
- Connect GND to battery negative and Pi GND
- Connect 5V to Pi 5V (if using L298N 5V regulator)
- Connect IN1, IN2, ENA to Pi GPIO pins as specified above
- Connect OUT1, OUT2 to Motor A
- Repeat for all 4 motors

Ultrasonic Sensor Wiring (HC-SR04):
- VCC to Pi 5V
- GND to Pi GND  
- Trigger to specified GPIO pin
- Echo to specified GPIO pin (through voltage divider if needed)

LED Wiring:
- Anode to GPIO pin through 220Ω resistor
- Cathode to GND

Emergency Button:
- One terminal to GPIO pin
- Other terminal to GND
- Enable internal pull-up resistor in code
"""

def print_pin_mapping():
    """Print complete pin mapping for reference"""
    print("Mining Vehicle GPIO Pin Mapping")
    print("=" * 50)
    
    print("\nMotor Driver Pins:")
    for motor, pin in MOTOR_PINS.items():
        print(f"  {motor}: GPIO {pin}")
    
    print("\nUltrasonic Sensor Pins:")
    for sensor, pins in ULTRASONIC_PINS.items():
        print(f"  {sensor.upper()}:")
        print(f"    Trigger: GPIO {pins['trigger']}")
        print(f"    Echo: GPIO {pins['echo']}")
    
    print("\nStatus & Control Pins:")
    for component, pin in STATUS_PINS.items():
        print(f"  {component}: GPIO {pin}")
    
    print("\nPower Requirements:")
    for component, requirement in POWER_REQUIREMENTS.items():
        print(f"  {component}: {requirement}")
    
    print(f"\nWiring Instructions:\n{WIRING_INSTRUCTIONS}")

if __name__ == "__main__":
    print_pin_mapping()
