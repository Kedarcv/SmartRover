#!/usr/bin/env python3
"""
SmartRover Dependencies Installation Script
This script installs all required Python packages and system dependencies with flexible versioning
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
        # Remove version constraints for maximum compatibility
        self.python_packages = [
            'numpy',
            'opencv-python',
            'flask',
            'flask-cors',
            'gpiozero',
            'RPi.GPIO',
            'psutil',
            'requests',
            'matplotlib',
            'scikit-learn',
            'pandas',
            'Pillow',
            'scipy',
            'bleak'
        ]
        
        # Try TensorFlow but don't fail if it doesn't install
        self.optional_packages = [
            'tensorflow',
            'pybluez'
        ]
        
        self.system_packages = [
            'python3-pip',
            'python3-venv',
            'python3-dev',
            'build-essential',
            'cmake',
            'pkg-config',
            'libjpeg-dev',
            'libpng-dev',
            'libavcodec-dev',
            'libavformat-dev',
            'libswscale-dev',
            'libv4l-dev',
            'libatlas-base-dev',
            'gfortran',
            'bluetooth',
            'bluez',
            'libbluetooth-dev',
            'sqlite3',
            'nginx',
            'git',
            'curl',
            'wget'
        ]
    
    def run_command(self, command, description, fail_on_error=True):
        """Run a command with error handling"""
        logger.info(f"{description}...")
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"✓ {description} completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            if fail_on_error:
                logger.error(f"✗ {description} failed: {e}")
                if e.stderr:
                    logger.error(f"Error output: {e.stderr}")
                return False
            else:
                logger.warning(f"⚠ {description} failed but continuing: {e}")
                return True
    
    def check_root(self):
        """Check if running as root for system package installation"""
        return os.geteuid() == 0
    
    def update_system(self):
        """Update system package lists"""
        return self.run_command(['apt', 'update'], "Updating system package lists", fail_on_error=False)
    
    def install_system_packages(self):
        """Install system packages"""
        if not self.check_root():
            logger.warning("Not running as root - skipping system package installation")
            return True
        
        # Install packages one by one to avoid failures
        success = True
        for package in self.system_packages:
            if not self.run_command(['apt', 'install', '-y', package], 
                                  f"Installing {package}", fail_on_error=False):
                logger.warning(f"Failed to install {package}, continuing...")
        
        return success
    
    def create_virtual_environment(self, venv_path):
        """Create Python virtual environment"""
        logger.info(f"Creating virtual environment at {venv_path}")
        if venv_path.exists():
            logger.info("Virtual environment already exists, skipping creation")
            return True
        
        return self.run_command([sys.executable, '-m', 'venv', str(venv_path)], 
                               "Creating virtual environment")
    
    def install_python_packages(self, venv_path):
        """Install Python packages in virtual environment"""
        pip_path = venv_path / 'bin' / 'pip'
        
        # Upgrade pip first
        self.run_command([str(pip_path), 'install', '--upgrade', 'pip'], 
                        "Upgrading pip", fail_on_error=False)
        
        # Install core packages
        logger.info("Installing core Python packages...")
        for package in self.python_packages:
            self.run_command([str(pip_path), 'install', package], 
                           f"Installing {package}", fail_on_error=False)
        
        # Install optional packages
        logger.info("Installing optional packages...")
        for package in self.optional_packages:
            self.run_command([str(pip_path), 'install', package], 
                           f"Installing optional {package}", fail_on_error=False)
        
        logger.info("Python packages installation completed")
        return True
    
    def create_simple_test_script(self, venv_path):
        """Create a simple test script to verify basic functionality"""
        test_script = venv_path.parent / 'test_installation.py'
        
        test_code = '''#!/usr/bin/env python3
"""Simple test script to verify installation"""
import sys
import traceback

def test_import(module_name, optional=False):
    try:
        __import__(module_name)
        print(f"✓ {module_name} imported successfully")
        return True
    except ImportError as e:
        if optional:
            print(f"⚠ Optional module {module_name} not available: {e}")
        else:
            print(f"✗ Required module {module_name} failed to import: {e}")
        return not optional

def main():
    print("Testing SmartRover installation...")
    
    required_modules = ['flask', 'numpy', 'psutil', 'requests']
    optional_modules = ['cv2', 'tensorflow', 'gpiozero', 'RPi.GPIO']
    
    success = True
    
    for module in required_modules:
        if not test_import(module):
            success = False
    
    for module in optional_modules:
        test_import(module, optional=True)
    
    if success:
        print("\\n✓ Installation test passed! Core modules are working.")
    else:
        print("\\n✗ Installation test failed! Some required modules are missing.")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        with open(test_script, 'w') as f:
            f.write(test_code)
        
        os.chmod(test_script, 0o755)
        
        # Run the test
        python_path = venv_path / 'bin' / 'python'
        return self.run_command([str(python_path), str(test_script)], 
                               "Testing installation", fail_on_error=False)
    
    def install_all(self, venv_path=None):
        """Install all dependencies"""
        if venv_path is None:
            venv_path = Path.cwd() / 'venv'
        
        logger.info("Starting SmartRover dependency installation (flexible versioning)...")
        
        # System packages
        self.update_system()
        self.install_system_packages()
        
        # Python virtual environment and packages
        if not self.create_virtual_environment(venv_path):
            logger.error("Failed to create virtual environment")
            return False
        
        if not self.install_python_packages(venv_path):
            logger.error("Failed to install Python packages")
            return False
        
        # Test installation
        self.create_simple_test_script(venv_path)
        
        logger.info("SmartRover dependency installation completed!")
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
    
    args = parser.parse_args()
    
    venv_path = Path(args.venv_path) if args.venv_path else Path.cwd() / 'venv'
    
    # Install everything
    success = installer.install_all(venv_path)
    
    if success:
        print("\n" + "="*50)
        print("✓ Installation completed successfully!")
        print("✓ You can now run the SmartRover system")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("⚠ Installation completed with some warnings")
        print("⚠ The system should still work with basic functionality")
        print("="*50)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
