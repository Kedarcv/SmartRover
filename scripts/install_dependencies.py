#!/usr/bin/env python3
"""
Installation script for mining vehicle dependencies
Run this script on your Raspberry Pi to install all required packages
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("Mining Vehicle Dependencies Installation")
    print("=" * 50)
    
    # Update system
    if not run_command("sudo apt update && sudo apt upgrade -y", 
                      "Updating system packages"):
        return False
    
    # Install system dependencies
    system_packages = [
        "python3-pip",
        "python3-venv",
        "python3-dev",
        "libopencv-dev",
        "python3-opencv",
        "libatlas-base-dev",
        "libjasper-dev",
        "libqtgui4",
        "libqt4-test",
        "libhdf5-dev",
        "libhdf5-serial-dev",
        "libatlas-base-dev",
        "libjasper-dev",
        "libqtgui4",
        "libqt4-test"
    ]
    
    package_list = " ".join(system_packages)
    if not run_command(f"sudo apt install -y {package_list}", 
                      "Installing system packages"):
        return False
    
    # Create virtual environment
    if not run_command("python3 -m venv mining_vehicle_env", 
                      "Creating virtual environment"):
        return False
    
    # Activate virtual environment and install Python packages
    pip_packages = [
        "tensorflow==2.13.0",
        "opencv-python==4.8.0.74",
        "numpy==1.24.3",
        "flask==2.3.2",
        "flask-cors==4.0.0",
        "RPi.GPIO==0.7.1",
        "gpiozero==1.6.2",
        "psutil==5.9.5",
        "requests==2.31.0"
    ]
    
    for package in pip_packages:
        if not run_command(f"./mining_vehicle_env/bin/pip install {package}", 
                          f"Installing {package}"):
            print(f"Warning: Failed to install {package}")
    
    # Create systemd service file
    service_content = """[Unit]
Description=Mining Vehicle Controller
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mining_vehicle
Environment=PATH=/home/pi/mining_vehicle/mining_vehicle_env/bin
ExecStart=/home/pi/mining_vehicle/mining_vehicle_env/bin/python raspberry_pi_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    try:
        with open("/tmp/mining_vehicle.service", "w") as f:
            f.write(service_content)
        
        run_command("sudo mv /tmp/mining_vehicle.service /etc/systemd/system/", 
                   "Creating systemd service")
        run_command("sudo systemctl daemon-reload", "Reloading systemd")
        
        print("\n" + "=" * 50)
        print("Installation completed!")
        print("\nTo start the mining vehicle service:")
        print("sudo systemctl enable mining_vehicle")
        print("sudo systemctl start mining_vehicle")
        print("\nTo check service status:")
        print("sudo systemctl status mining_vehicle")
        print("\nTo view logs:")
        print("sudo journalctl -u mining_vehicle -f")
        
    except Exception as e:
        print(f"Warning: Could not create systemd service: {e}")
    
    print("\n" + "=" * 50)
    print("Setup Instructions:")
    print("1. Connect your L298N motor driver to the specified GPIO pins")
    print("2. Connect 4 ultrasonic sensors to the specified pins")
    print("3. Connect status LEDs and emergency button")
    print("4. Run the server: python3 raspberry_pi_server.py")
    print("5. Access dashboard at: http://[PI_IP]:5000")

if __name__ == "__main__":
    main()
