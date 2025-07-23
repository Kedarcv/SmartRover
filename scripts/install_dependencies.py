#!/usr/bin/env python3
"""
SmartRover Dependencies Installation Script
This script installs all required Python packages and system dependencies
"""

import subprocess
import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DependencyInstaller:
    def __init__(self):
        self.python_packages = [
            'numpy==1.21.6',
            'opencv-python==4.5.5.64',
            'tensorflow==2.8.0',
            'flask==2.2.2',
            'flask-cors==3.0.10',
            'gpiozero==1.6.2',
            'RPi.GPIO==0.7.1',
            'psutil==5.9.0',
            'requests==2.28.1',
            'matplotlib==3.5.3',
            'scikit-learn==1.1.3',
            'pandas==1.4.4',
            'Pillow==9.3.0',
            'scipy==1.9.3'
        ]
        
        self.system_packages = [
            'python3-pip',
            'python3-venv',
            'python3-dev',
            'build-essential',
            'cmake',
            'pkg-config',
            'libjpeg-dev',
            'libtiff5-dev',
            'libpng-dev',
            'libavcodec-dev',
            'libavformat-dev',
            'libswscale-dev',
            'libv4l-dev',
            'libxvidcore-dev',
            'libx264-dev',
            'libfontconfig1-dev',
            'libcairo2-dev',
            'libgdk-pixbuf2.0-dev',
            'libpango1.0-dev',
            'libgtk2.0-dev',
            'libgtk-3-dev',
            'libatlas-base-dev',
            'gfortran',
            'libhdf5-dev',
            'libhdf5-serial-dev',
            'libhdf5-103',
            'libqt5gui5',
            'libqt5webkit5',
            'libqt5test5',
            'python3-pyqt5',
            'bluetooth',
            'bluez',
            'libbluetooth-dev',
            'sqlite3',
            'nginx',
            'git',
            'curl',
            'wget'
        ]
        
        self.optional_packages = [
            'bleak==0.19.5',  # Bluetooth alternative
        ]
    
    def check_root(self):
        """Check if running as root for system package installation"""
        return os.geteuid() == 0
    
    def update_system(self):
        """Update system package lists"""
        logger.info("Updating system package lists...")
        try:
            subprocess.run(['apt', 'update'], check=True, capture_output=True)
            logger.info("System package lists updated successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update system packages: {e}")
            return False
        return True
    
    def install_system_packages(self):
        """Install system packages"""
        if not self.check_root():
            logger.error("Root privileges required for system package installation")
            return False
        
        logger.info("Installing system packages...")
        try:
            subprocess.run(['apt', 'install', '-y'] + self.system_packages, 
                         check=True, capture_output=True)
            logger.info("System packages installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install system packages: {e}")
            return False
        return True
    
    def create_virtual_environment(self, venv_path):
        """Create Python virtual environment"""
        logger.info(f"Creating virtual environment at {venv_path}")
        try:
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            logger.info("Virtual environment created successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False
        return True
    
    def install_python_packages(self, venv_path):
        """Install Python packages in virtual environment"""
        pip_path = venv_path / 'bin' / 'pip'
        
        logger.info("Upgrading pip...")
        try:
            subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to upgrade pip: {e}")
            return False
        
        logger.info("Installing Python packages...")
        for package in self.python_packages:
            try:
                logger.info(f"Installing {package}...")
                subprocess.run([str(pip_path), 'install', package], 
                             check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {package}: {e}")
                # Continue with other packages
        
        # Install optional packages (don't fail if they don't install)
        logger.info("Installing optional packages...")
        for package in self.optional_packages:
            try:
                logger.info(f"Installing optional package {package}...")
                subprocess.run([str(pip_path), 'install', package], 
                             check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                logger.warning(f"Optional package {package} failed to install: {e}")
        
        logger.info("Python packages installation completed")
        return True
    
    def install_bluetooth_support(self, venv_path):
        """Install Bluetooth support with fallback"""
        pip_path = venv_path / 'bin' / 'pip'
        
        logger.info("Installing Bluetooth support...")
        
        # Try pybluez first
        try:
            subprocess.run([str(pip_path), 'install', 'pybluez==0.23'], 
                         check=True, capture_output=True)
            logger.info("pybluez installed successfully")
            return True
        except subprocess.CalledProcessError:
            logger.warning("pybluez installation failed, trying bleak as alternative...")
        
        # Fallback to bleak
        try:
            subprocess.run([str(pip_path), 'install', 'bleak==0.19.5'], 
                         check=True, capture_output=True)
            logger.info("bleak installed successfully as Bluetooth alternative")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Bluetooth support: {e}")
            return False
    
    def verify_installation(self, venv_path):
        """Verify that key packages are installed correctly"""
        python_path = venv_path / 'bin' / 'python'
        
        test_imports = [
            'numpy',
            'cv2',
            'tensorflow',
            'flask',
            'gpiozero',
            'RPi.GPIO',
            'psutil'
        ]
        
        logger.info("Verifying installation...")
        for module in test_imports:
            try:
                subprocess.run([str(python_path), '-c', f'import {module}'], 
                             check=True, capture_output=True)
                logger.info(f"✓ {module} imported successfully")
            except subprocess.CalledProcessError:
                logger.error(f"✗ Failed to import {module}")
                return False
        
        logger.info("Installation verification completed successfully")
        return True
    
    def install_all(self, venv_path=None):
        """Install all dependencies"""
        if venv_path is None:
            venv_path = Path.cwd() / 'venv'
        
        logger.info("Starting SmartRover dependency installation...")
        
        # System packages (requires root)
        if self.check_root():
            if not self.update_system():
                return False
            if not self.install_system_packages():
                return False
        else:
            logger.warning("Not running as root - skipping system package installation")
            logger.warning("Please run 'sudo apt update && sudo apt install -y python3-pip python3-venv python3-dev build-essential' manually")
        
        # Python virtual environment and packages
        if not self.create_virtual_environment(venv_path):
            return False
        
        if not self.install_python_packages(venv_path):
            return False
        
        if not self.install_bluetooth_support(venv_path):
            logger.warning("Bluetooth support installation failed - some features may not work")
        
        if not self.verify_installation(venv_path):
            logger.error("Installation verification failed")
            return False
        
        logger.info("SmartRover dependency installation completed successfully!")
        logger.info(f"Virtual environment created at: {venv_path}")
        logger.info(f"To activate: source {venv_path}/bin/activate")
        
        return True

def main():
    """Main installation function"""
    installer = DependencyInstaller()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Install SmartRover dependencies')
    parser.add_argument('--venv-path', type=str, help='Path for virtual environment')
    parser.add_argument('--system-only', action='store_true', help='Install only system packages')
    parser.add_argument('--python-only', action='store_true', help='Install only Python packages')
    
    args = parser.parse_args()
    
    venv_path = Path(args.venv_path) if args.venv_path else Path.cwd() / 'venv'
    
    if args.system_only:
        if installer.check_root():
            installer.update_system()
            installer.install_system_packages()
        else:
            logger.error("Root privileges required for system package installation")
            sys.exit(1)
    elif args.python_only:
        if not venv_path.exists():
            installer.create_virtual_environment(venv_path)
        installer.install_python_packages(venv_path)
        installer.install_bluetooth_support(venv_path)
        installer.verify_installation(venv_path)
    else:
        # Install everything
        success = installer.install_all(venv_path)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
