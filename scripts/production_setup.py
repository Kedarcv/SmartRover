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
        
    def check_root(self):
        """Check if running as root"""
        if os.geteuid() != 0:
            logger.error("This script must be run as root (use sudo)")
            sys.exit(1)
    
    def install_system_dependencies(self):
        """Install system-level dependencies"""
        logger.info("Installing system dependencies...")
        
        packages = [
            'python3-pip',
            'python3-venv',
            'python3-dev',
            'build-essential',
            'cmake',
            'bluetooth',
            'bluez',
            'libbluetooth-dev',
            'nginx',
            'supervisor',
            'logrotate',
            'sqlite3',
            'curl',
            'wget',
            'git'
        ]
        
        try:
            subprocess.run(['apt', 'update'], check=True)
            subprocess.run(['apt', 'install', '-y'] + packages, check=True)
            logger.info("System dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install system dependencies: {e}")
            sys.exit(1)
    
    def setup_python_environment(self):
        """Setup Python virtual environment"""
        logger.info("Setting up Python environment...")
        
        venv_path = self.base_dir / 'venv'
        
        try:
            # Create virtual environment
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            
            # Install Python dependencies
            pip_path = venv_path / 'bin' / 'pip'
            
            subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], check=True)
            
            # Install core packages
            packages = [
                'numpy==1.21.6',
                'opencv-python==4.5.5.64',
                'tensorflow==2.8.0',
                'flask==2.2.2',
                'flask-cors==3.0.10',
                'gpiozero==1.6.2',
                'RPi.GPIO==0.7.1',
                'psutil==5.9.0',
                'requests==2.28.1'
            ]
            
            for package in packages:
                subprocess.run([str(pip_path), 'install', package], check=True)
            
            logger.info("Python environment setup completed")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup Python environment: {e}")
            sys.exit(1)
    
    def create_system_user(self):
        """Create system user for the service"""
        logger.info("Creating system user...")
        
        try:
            subprocess.run([
                'useradd', '--system', '--shell', '/bin/false',
                '--home', str(self.data_dir), '--create-home',
                self.user
            ], check=True)
            
            # Add user to required groups
            subprocess.run(['usermod', '-a', '-G', 'gpio,bluetooth,video,i2c,spi', self.user], check=True)
            
            logger.info("System user created successfully")
        except subprocess.CalledProcessError:
            logger.info("System user already exists or creation failed")
    
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
            subprocess.run(['chown', f'{self.user}:{self.user}', str(directory)], check=True)
            subprocess.run(['chmod', '755', str(directory)], check=True)
            logger.info(f"Created directory: {directory}")
    
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
            ('Mining Point Delta', 600, 1000, 'mining', 'pending', 1),
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
        subprocess.run(['chown', f'{self.user}:{self.user}', str(db_path)], check=True)
        subprocess.run(['chmod', '644', str(db_path)], check=True)
        
        logger.info("Mining database initialized with sample waypoints")
    
    def create_config_files(self):
        """Create production configuration files"""
        logger.info("Creating configuration files...")
        
        # Vehicle configuration
        vehicle_config = {
            "vehicle": {
                "id": "smartrover_001",
                "name": "SmartRover Mining Vehicle #1",
                "type": "autonomous_mining_rover",
                "version": "2.0.0"
            },
            "hardware": {
                "motor_pins": {
                    "IN1": 18,
                    "IN2": 16,
                    "IN3": 21,
                    "IN4": 23,
                    "ENA": 12,
                    "ENB": 13
                },
                "sensor_pins": {
                    "TRIG": 24,
                    "ECHO": 25
                },
                "led_pins": {
                    "status": 26,
                    "warning": 13
                },
                "button_pins": {
                    "emergency": 6
                }
            },
            "navigation": {
                "max_speed": 0.8,
                "obstacle_threshold": 30,
                "waypoint_tolerance": 50,
                "map_size": 2000,
                "scale": 5
            },
            "mining": {
                "collection_time": 3,
                "auto_return_dock": True,
                "max_session_time": 7200,
                "auto_start_on_boot": True
            },
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False,
                "threaded": True
            },
            "logging": {
                "level": "INFO",
                "file": str(self.log_dir / "vehicle.log"),
                "max_size": "10MB",
                "backup_count": 5
            },
            "safety": {
                "emergency_stop_pin": 6,
                "max_speed": 0.8,
                "obstacle_threshold": 30,
                "timeout": 5.0
            }
        }
        
        config_file = self.config_dir / 'vehicle_config.json'
        with open(config_file, 'w') as f:
            json.dump(vehicle_config, f, indent=2)
        
        subprocess.run(['chown', f'{self.user}:{self.user}', str(config_file)], check=True)
        subprocess.run(['chmod', '644', str(config_file)], check=True)
        
        logger.info(f"Created vehicle config: {config_file}")
    
    def create_systemd_services(self):
        """Create systemd service files for auto-start"""
        logger.info("Creating systemd services...")
        
        # Main server service
        server_service = f"""[Unit]
Description=SmartRover Mining Vehicle Server
Documentation=https://github.com/smartrover/mining-vehicle
After=network.target bluetooth.target
Wants=network.target

[Service]
Type=simple
User={self.user}
Group={self.user}
WorkingDirectory={self.base_dir}
Environment=PATH={self.base_dir}/venv/bin
Environment=PYTHONPATH={self.base_dir}
ExecStart={self.base_dir}/venv/bin/python {self.base_dir}/enhanced_server.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartrover-server

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={self.data_dir} {self.log_dir} /var/run/smartrover

[Install]
WantedBy=multi-user.target
"""
        
        # Vehicle controller service
        vehicle_service = f"""[Unit]
Description=SmartRover Vehicle Controller
Documentation=https://github.com/smartrover/mining-vehicle
After=network.target smartrover-server.service
Wants=network.target
Requires=smartrover-server.service

[Service]
Type=simple
User={self.user}
Group={self.user}
WorkingDirectory={self.base_dir}
Environment=PATH={self.base_dir}/venv/bin
Environment=PYTHONPATH={self.base_dir}
ExecStart={self.base_dir}/venv/bin/python {self.base_dir}/vehicle_controller.py {self.data_dir}/mining_data.db
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartrover-vehicle

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={self.data_dir} {self.log_dir} /var/run/smartrover

[Install]
WantedBy=multi-user.target
"""
        
        # Auto-start mining service (waits for system to be ready, then starts mining)
        autostart_service = f"""[Unit]
Description=SmartRover Auto-Start Mining Operations
After=smartrover-server.service smartrover-vehicle.service
Requires=smartrover-server.service smartrover-vehicle.service

[Service]
Type=oneshot
User={self.user}
Group={self.user}
ExecStartPre=/bin/sleep 60
ExecStart=/bin/bash -c 'curl -X POST http://localhost:5000/api/vehicle-control -H "Content-Type: application/json" -d "{{\\"command\\":\\"start_mining\\"}}" || true'
RemainAfterExit=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartrover-autostart

[Install]
WantedBy=multi-user.target
"""
        
        # Write service files
        with open(self.services_dir / 'smartrover-server.service', 'w') as f:
            f.write(server_service)
        
        with open(self.services_dir / 'smartrover-vehicle.service', 'w') as f:
            f.write(vehicle_service)
        
        with open(self.services_dir / 'smartrover-autostart.service', 'w') as f:
            f.write(autostart_service)
        
        # Reload systemd and enable services
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', 'smartrover-server.service'], check=True)
        subprocess.run(['systemctl', 'enable', 'smartrover-vehicle.service'], check=True)
        subprocess.run(['systemctl', 'enable', 'smartrover-autostart.service'], check=True)
        
        logger.info("Systemd services created and enabled for auto-start")
    
    def setup_nginx(self):
        """Setup Nginx reverse proxy"""
        logger.info("Setting up Nginx...")
        
        nginx_config = """server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check
    location /health {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        access_log off;
    }
    
    # Main application
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Deny access to sensitive files
    location ~ /\\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
"""
        
        # Write Nginx config
        with open('/etc/nginx/sites-available/smartrover', 'w') as f:
            f.write(nginx_config)
        
        # Enable site
        nginx_enabled = Path('/etc/nginx/sites-enabled/smartrover')
        if nginx_enabled.exists():
            nginx_enabled.unlink()
        nginx_enabled.symlink_to('/etc/nginx/sites-available/smartrover')
        
        # Remove default site
        default_site = Path('/etc/nginx/sites-enabled/default')
        if default_site.exists():
            default_site.unlink()
        
        # Test and reload Nginx
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'enable', 'nginx'], check=True)
        subprocess.run(['systemctl', 'restart', 'nginx'], check=True)
        
        logger.info("Nginx setup completed")
    
    def create_management_scripts(self):
        """Create management scripts"""
        logger.info("Creating management scripts...")
        
        # Status script
        status_script = """#!/bin/bash
echo "SmartRover Mining Vehicle Status"
echo "================================"
echo
echo "Services:"
systemctl is-active smartrover-server && echo "✓ Server: Running" || echo "✗ Server: Stopped"
systemctl is-active smartrover-vehicle && echo "✓ Vehicle: Running" || echo "✗ Vehicle: Stopped"
systemctl is-active nginx && echo "✓ Nginx: Running" || echo "✗ Nginx: Stopped"
echo
echo "System Info:"
echo "IP Address: $(hostname -I | awk '{print $1}')"
echo "Uptime: $(uptime -p)"
if command -v vcgencmd >/dev/null 2>&1; then
    echo "Temperature: $(vcgencmd measure_temp)"
fi
echo
echo "Mining Status:"
curl -s http://localhost:5000/api/vehicle-status | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        status = data['data']['system_status']
        print(f\"Mining Active: {status.get('mining_active', False)}\")
        print(f\"Waypoints Completed: {status.get('waypoints_completed', 0)}\")
        print(f\"Minerals Collected: {status.get('minerals_collected', 0)}\")
        print(f\"Total Distance: {data['data']['map_data'].get('total_distance', 0):.1f}m\")
    else:
        print('Vehicle not responding')
except:
    print('Unable to get mining status')
"
"""
        
        # Start mining script
        start_mining_script = """#!/bin/bash
echo "Starting SmartRover Mining Operation..."
curl -X POST http://localhost:5000/api/vehicle-control \\
     -H "Content-Type: application/json" \\
     -d '{"command":"start_mining"}' \\
     && echo "Mining operation started successfully" \\
     || echo "Failed to start mining operation"
"""
        
        # Stop mining script
        stop_mining_script = """#!/bin/bash
echo "Stopping SmartRover Mining Operation..."
curl -X POST http://localhost:5000/api/vehicle-control \\
     -H "Content-Type: application/json" \\
     -d '{"command":"stop_mining"}' \\
     && echo "Mining operation stopped successfully" \\
     || echo "Failed to stop mining operation"
"""
        
        # Return to dock script
        return_dock_script = """#!/bin/bash
echo "Returning SmartRover to Docking Station..."
curl -X POST http://localhost:5000/api/vehicle-control \\
     -H "Content-Type: application/json" \\
     -d '{"command":"return_to_dock"}' \\
     && echo "Return to dock initiated successfully" \\
     || echo "Failed to initiate return to dock"
"""
        
        scripts = {
            '/usr/local/bin/smartrover-status': status_script,
            '/usr/local/bin/smartrover-start-mining': start_mining_script,
            '/usr/local/bin/smartrover-stop-mining': stop_mining_script,
            '/usr/local/bin/smartrover-return-dock': return_dock_script
        }
        
        for script_path, content in scripts.items():
            with open(script_path, 'w') as f:
                f.write(content)
            subprocess.run(['chmod', '+x', script_path], check=True)
        
        logger.info("Management scripts created")
    
    def setup_boot_optimization(self):
        """Optimize system for faster boot and auto-start"""
        logger.info("Optimizing system for auto-start...")
        
        # Raspberry Pi specific optimizations
        try:
            # Set GPU memory split
            subprocess.run(['raspi-config', 'nonint', 'do_memory_split', '128'], check=True)
            
            # Enable required interfaces
            subprocess.run(['raspi-config', 'nonint', 'do_i2c', '0'], check=True)
            subprocess.run(['raspi-config', 'nonint', 'do_spi', '0'], check=True)
            subprocess.run(['raspi-config', 'nonint', 'do_camera', '0'], check=True)
            
            logger.info("Raspberry Pi optimizations applied")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Could not apply Raspberry Pi optimizations (not on Raspberry Pi?)")
        
        # Create boot script for immediate startup
        boot_script = f"""#!/bin/bash
# SmartRover Boot Script
# This script runs early in the boot process

# Wait for network
while ! ping -c 1 8.8.8.8 >/dev/null 2>&1; do
    sleep 1
done

# Ensure services are running
systemctl start smartrover-server
systemctl start smartrover-vehicle

# Log boot completion
echo "$(date): SmartRover boot sequence completed" >> {self.log_dir}/boot.log
"""
        
        boot_script_path = Path('/usr/local/bin/smartrover-boot')
        with open(boot_script_path, 'w') as f:
            f.write(boot_script)
        subprocess.run(['chmod', '+x', str(boot_script_path)], check=True)
        
        # Add to rc.local for early startup
        rc_local_content = """#!/bin/bash
# SmartRover early startup
/usr/local/bin/smartrover-boot &

exit 0
"""
        
        with open('/etc/rc.local', 'w') as f:
            f.write(rc_local_content)
        subprocess.run(['chmod', '+x', '/etc/rc.local'], check=True)
        
        logger.info("Boot optimization completed")
    
    def run_setup(self):
        """Run complete production setup"""
        logger.info("Starting SmartRover production setup for autonomous mining...")
        
        self.check_root()
        self.install_system_dependencies()
        self.setup_python_environment()
        self.create_system_user()
        self.create_directories()
        self.initialize_database()
        self.create_config_files()
        self.create_systemd_services()
        self.setup_nginx()
        self.create_management_scripts()
        self.setup_boot_optimization()
        
        logger.info("Production setup completed successfully!")
        logger.info("System configured for automatic startup and autonomous mining operations.")
        logger.info("The vehicle will automatically start mapping and await mining commands on boot.")
        logger.info(f"Access the dashboard at: http://$(hostname -I | awk '{{print $1}}')")

if __name__ == "__main__":
    setup = ProductionSetup()
    setup.run_setup()
