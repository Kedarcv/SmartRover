#!/usr/bin/env python3
"""
SmartRover Mining Vehicle Production Setup Script
This script configures the system for production deployment with auto-start capabilities
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.base_dir = Path('/opt/smartrover')
        self.config_dir = Path('/etc/smartrover')
        self.log_dir = Path('/var/log/smartrover')
        self.data_dir = Path('/var/lib/smartrover')
        self.services_dir = Path('/etc/systemd/system')
        self.user = 'smartrover'
        
    def run_command(self, command, description, fail_on_error=True):
        """Run a command with error handling"""
        logger.info(f"{description}...")
        try:
            if isinstance(command, str):
                result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            else:
                result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"✓ {description} completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            if fail_on_error:
                logger.error(f"✗ {description} failed: {e}")
                return False
            else:
                logger.warning(f"⚠ {description} failed but continuing: {e}")
                return True
    
    def check_root(self):
        """Check if running as root"""
        if os.geteuid() != 0:
            logger.error("This script must be run as root (use sudo)")
            sys.exit(1)
    
    def install_system_dependencies(self):
        """Install minimal system dependencies"""
        logger.info("Installing system dependencies...")
        
        packages = [
            'python3-pip',
            'python3-venv',
            'python3-dev',
            'build-essential',
            'sqlite3',
            'curl',
            'wget',
            'git'
        ]
        
        self.run_command('apt update', "Updating package lists", fail_on_error=False)
        
        for package in packages:
            self.run_command(f'apt install -y {package}', f"Installing {package}", fail_on_error=False)
    
    def setup_python_environment(self):
        """Setup Python virtual environment with flexible versioning"""
        logger.info("Setting up Python environment...")
        
        venv_path = self.base_dir / 'venv'
        
        # Create virtual environment
        self.run_command([sys.executable, '-m', 'venv', str(venv_path)], 
                        "Creating virtual environment")
        
        # Install Python dependencies without version constraints
        pip_path = venv_path / 'bin' / 'pip'
        
        self.run_command([str(pip_path), 'install', '--upgrade', 'pip'], 
                        "Upgrading pip", fail_on_error=False)
        
        # Core packages that are essential
        essential_packages = [
            'flask',
            'flask-cors', 
            'numpy',
            'psutil',
            'requests'
        ]
        
        # Optional packages that enhance functionality
        optional_packages = [
            'opencv-python',
            'tensorflow',
            'gpiozero',
            'RPi.GPIO',
            'matplotlib',
            'scikit-learn',
            'pandas',
            'Pillow',
            'scipy',
            'bleak'
        ]
        
        # Install essential packages
        for package in essential_packages:
            self.run_command([str(pip_path), 'install', package], 
                           f"Installing essential {package}")
        
        # Install optional packages (don't fail if they don't work)
        for package in optional_packages:
            self.run_command([str(pip_path), 'install', package], 
                           f"Installing optional {package}", fail_on_error=False)
        
        logger.info("Python environment setup completed")
    
    def create_system_user(self):
        """Create system user for the service"""
        logger.info("Creating system user...")
        
        self.run_command([
            'useradd', '--system', '--shell', '/bin/false',
            '--home', str(self.data_dir), '--create-home',
            self.user
        ], "Creating system user", fail_on_error=False)
        
        # Add user to required groups (don't fail if groups don't exist)
        self.run_command(['usermod', '-a', '-G', 'gpio,bluetooth,video,i2c,spi', self.user], 
                        "Adding user to groups", fail_on_error=False)
    
    def create_directories(self):
        """Create necessary directories"""
        logger.info("Creating directories...")
        
        directories = [
            self.base_dir,
            self.config_dir,
            self.log_dir,
            self.data_dir,
            self.data_dir / 'models',
            self.data_dir / 'maps',
            self.data_dir / 'backups',
            Path('/var/run/smartrover')
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            self.run_command(['chown', f'{self.user}:{self.user}', str(directory)], 
                           f"Setting ownership for {directory}", fail_on_error=False)
            self.run_command(['chmod', '755', str(directory)], 
                           f"Setting permissions for {directory}", fail_on_error=False)
    
    def copy_project_files(self):
        """Copy project files to installation directory"""
        logger.info("Copying project files...")
        
        # Copy Python scripts
        scripts_source = self.project_root / 'scripts'
        if scripts_source.exists():
            self.run_command(f'cp -r {scripts_source}/* {self.base_dir}/', 
                           "Copying scripts", fail_on_error=False)
        
        # Make scripts executable
        for script in self.base_dir.glob('*.py'):
            self.run_command(['chmod', '+x', str(script)], 
                           f"Making {script.name} executable", fail_on_error=False)
    
    def initialize_database(self):
        """Initialize the mining database with default data"""
        logger.info("Initializing mining database...")
        
        db_path = self.data_dir / 'mining_data.db'
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waypoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                type TEXT DEFAULT 'mining',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mining_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP NULL,
                waypoints_completed INTEGER DEFAULT 0,
                total_distance REAL DEFAULT 0,
                minerals_collected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT DEFAULT 'system'
            )
        ''')
        
        # Insert default docking station
        cursor.execute('''
            INSERT OR IGNORE INTO waypoints (id, name, x, y, type, status, priority)
            VALUES (1, 'Docking Station', 1000, 1000, 'dock', 'completed', 0)
        ''')
        
        # Insert sample mining waypoints
        sample_waypoints = [
            ('Mining Point Alpha', 800, 800, 'mining', 'pending', 3),
            ('Mining Point Beta', 1200, 800, 'mining', 'pending', 2),
            ('Mining Point Gamma', 1000, 600, 'mining', 'pending', 1),
        ]
        
        for waypoint in sample_waypoints:
            cursor.execute('''
                INSERT OR IGNORE INTO waypoints (name, x, y, type, status, priority)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', waypoint)
        
        # Log initial setup
        cursor.execute('''
            INSERT INTO system_logs (level, message, component)
            VALUES ('INFO', 'Database initialized with default waypoints', 'setup')
        ''')
        
        conn.commit()
        conn.close()
        
        # Set ownership
        self.run_command(['chown', f'{self.user}:{self.user}', str(db_path)], 
                        "Setting database ownership", fail_on_error=False)
    
    def create_config_files(self):
        """Create production configuration files"""
        logger.info("Creating configuration files...")
        
        # Simple vehicle configuration
        vehicle_config = {
            "vehicle": {
                "id": "smartrover_001",
                "name": "SmartRover Mining Vehicle #1",
                "version": "2.0.0"
            },
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False
            },
            "logging": {
                "level": "INFO",
                "file": str(self.log_dir / "vehicle.log")
            }
        }
        
        config_file = self.config_dir / 'vehicle_config.json'
        with open(config_file, 'w') as f:
            json.dump(vehicle_config, f, indent=2)
        
        self.run_command(['chown', f'{self.user}:{self.user}', str(config_file)], 
                        "Setting config ownership", fail_on_error=False)
    
    def create_systemd_services(self):
        """Create systemd service files for auto-start"""
        logger.info("Creating systemd services...")
        
        # Main server service
        server_service = f"""[Unit]
Description=SmartRover Mining Vehicle Server
After=network.target
Wants=network.target

[Service]
Type=simple
User={self.user}
Group={self.user}
WorkingDirectory={self.base_dir}
Environment=PATH={self.base_dir}/venv/bin
Environment=PYTHONPATH={self.base_dir}
ExecStart={self.base_dir}/venv/bin/python {self.base_dir}/standalone_vehicle_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        # Write service file
        with open(self.services_dir / 'smartrover.service', 'w') as f:
            f.write(server_service)
        
        # Reload systemd and enable service
        self.run_command(['systemctl', 'daemon-reload'], "Reloading systemd")
        self.run_command(['systemctl', 'enable', 'smartrover.service'], "Enabling SmartRover service")
        
        logger.info("Systemd service created and enabled for auto-start")
    
    def create_management_scripts(self):
        """Create simple management scripts"""
        logger.info("Creating management scripts...")
        
        # Status script
        status_script = """#!/bin/bash
echo "SmartRover Mining Vehicle Status"
echo "================================"
echo
echo "Service Status:"
systemctl is-active smartrover && echo "✓ SmartRover: Running" || echo "✗ SmartRover: Stopped"
echo
echo "System Info:"
echo "IP Address: $(hostname -I | awk '{print $1}')"
echo "Uptime: $(uptime -p)"
echo
echo "Access dashboard at: http://$(hostname -I | awk '{print $1}'):5000"
"""
        
        # Start service script
        start_script = """#!/bin/bash
echo "Starting SmartRover service..."
sudo systemctl start smartrover
sudo systemctl status smartrover
"""
        
        # Stop service script
        stop_script = """#!/bin/bash
echo "Stopping SmartRover service..."
sudo systemctl stop smartrover
sudo systemctl status smartrover
"""
        
        scripts = {
            '/usr/local/bin/smartrover-status': status_script,
            '/usr/local/bin/smartrover-start': start_script,
            '/usr/local/bin/smartrover-stop': stop_script
        }
        
        for script_path, content in scripts.items():
            with open(script_path, 'w') as f:
                f.write(content)
            self.run_command(['chmod', '+x', script_path], 
                           f"Making {script_path} executable", fail_on_error=False)
    
    def start_services(self):
        """Start the SmartRover service"""
        logger.info("Starting SmartRover service...")
        
        self.run_command(['systemctl', 'start', 'smartrover'], 
                        "Starting SmartRover service", fail_on_error=False)
        
        # Wait a moment and check status
        import time
        time.sleep(3)
        
        self.run_command(['systemctl', 'status', 'smartrover', '--no-pager'], 
                        "Checking service status", fail_on_error=False)
    
    def run_setup(self):
        """Run complete production setup"""
        logger.info("Starting SmartRover production setup...")
        
        self.check_root()
        self.install_system_dependencies()
        self.create_system_user()
        self.create_directories()
        self.setup_python_environment()
        self.copy_project_files()
        self.initialize_database()
        self.create_config_files()
        self.create_systemd_services()
        self.create_management_scripts()
        self.start_services()
        
        # Get IP address for final message
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            ip_address = result.stdout.strip().split()[0]
        except:
            ip_address = "your-pi-ip"
        
        print("\n" + "="*60)
        print("✓ SmartRover Production Setup Completed Successfully!")
        print("="*60)
        print(f"🌐 Dashboard URL: http://{ip_address}:5000")
        print("🚀 Service Status: smartrover-status")
        print("▶️  Start Service: smartrover-start")
        print("⏹️  Stop Service: smartrover-stop")
        print("📊 View Logs: journalctl -u smartrover -f")
        print("="*60)
        print("The system will automatically start on boot!")
        print("Add mining waypoints through the web dashboard.")
        print("="*60)

if __name__ == "__main__":
    setup = ProductionSetup()
    setup.run_setup()

</merged_code>
