#!/usr/bin/env python3
"""
SmartRover Mining Vehicle Production Setup Script
This script configures the system for production deployment
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path

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
            'bluetooth',
            'bluez',
            'libbluetooth-dev',
            'nginx',
            'supervisor',
            'logrotate'
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
        
        venv_path = self.project_root / 'venv'
        
        try:
            # Create virtual environment
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            
            # Install Python dependencies
            pip_path = venv_path / 'bin' / 'pip'
            requirements_path = self.project_root / 'requirements.txt'
            
            subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], check=True)
            subprocess.run([str(pip_path), 'install', '-r', str(requirements_path)], check=True)
            
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
                '--home', '/var/lib/smartrover', '--create-home',
                self.user
            ], check=True)
            
            # Add user to required groups
            subprocess.run(['usermod', '-a', '-G', 'gpio,bluetooth', self.user], check=True)
            
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
            self.base_dir / 'models',
            self.base_dir / 'data',
            self.base_dir / 'backups'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
    
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
            "sensors": {
                "ultrasonic": {
                    "enabled": True,
                    "pins": [18, 24, 23, 25],
                    "max_distance": 400
                },
                "camera": {
                    "enabled": True,
                    "device": "/dev/video0",
                    "resolution": [640, 480],
                    "fps": 30
                },
                "imu": {
                    "enabled": False,
                    "device": "/dev/i2c-1"
                }
            },
            "motors": {
                "left": {
                    "pin1": 16,
                    "pin2": 20,
                    "enable": 21
                },
                "right": {
                    "pin1": 19,
                    "pin2": 26,
                    "enable": 13
                }
            },
            "neural_network": {
                "model_path": "/opt/smartrover/models/mining_vehicle_model.h5",
                "input_shape": [64, 64, 3],
                "confidence_threshold": 0.7
            },
            "slam": {
                "enabled": True,
                "map_size": [200, 200],
                "resolution": 0.1,
                "update_rate": 10
            },
            "safety": {
                "emergency_stop_pin": 3,
                "max_speed": 0.8,
                "obstacle_threshold": 30,
                "timeout": 5.0
            }
        }
        
        config_file = self.config_dir / 'vehicle_config.json'
        with open(config_file, 'w') as f:
            json.dump(vehicle_config, f, indent=2)
        logger.info(f"Created vehicle config: {config_file}")
        
        # Server configuration
        server_config = {
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False,
                "threaded": True
            },
            "bluetooth": {
                "enabled": True,
                "service_name": "SmartRover Mining Control",
                "service_uuid": "1e0ca4ea-299d-4335-93eb-27fcfe7fa848"
            },
            "logging": {
                "level": "INFO",
                "file": "/var/log/smartrover/vehicle.log",
                "max_size": "10MB",
                "backup_count": 5
            },
            "security": {
                "session_timeout": 3600,
                "max_login_attempts": 5,
                "lockout_duration": 300
            }
        }
        
        server_config_file = self.config_dir / 'server_config.json'
        with open(server_config_file, 'w') as f:
            json.dump(server_config, f, indent=2)
        logger.info(f"Created server config: {server_config_file}")
    
    def setup_gpio_permissions(self):
        """Setup GPIO permissions for smartrover user"""
        logger.info("Setting up GPIO permissions...")
        
        # Add smartrover user to gpio group
        try:
            subprocess.run(['usermod', '-a', '-G', 'gpio', self.user], check=True)
            logger.info(f"Added {self.user} to gpio group")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add user to gpio group: {e}")
    
    def setup_bluetooth_permissions(self):
        """Setup Bluetooth permissions"""
        logger.info("Setting up Bluetooth permissions...")
        
        try:
            # Add user to bluetooth group
            subprocess.run(['usermod', '-a', '-G', 'bluetooth', self.user], check=True)
            
            # Configure Bluetooth service
            bluetooth_override = Path('/etc/systemd/system/bluetooth.service.d')
            bluetooth_override.mkdir(parents=True, exist_ok=True)
            
            override_content = """[Service]
ExecStart=
ExecStart=/usr/lib/bluetooth/bluetoothd --experimental
"""
            
            with open(bluetooth_override / 'override.conf', 'w') as f:
                f.write(override_content)
            
            logger.info("Configured Bluetooth service")
            
        except Exception as e:
            logger.error(f"Failed to setup Bluetooth permissions: {e}")
    
    def create_backup_script(self):
        """Create backup script for system data"""
        logger.info("Creating backup script...")
        
        backup_script = """#!/bin/bash
# SmartRover Backup Script

BACKUP_DIR="/opt/smartrover/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="smartrover_backup_$DATE.tar.gz"

echo "Creating backup: $BACKUP_FILE"

# Create backup
tar -czf "$BACKUP_DIR/$BACKUP_FILE" \
    /opt/smartrover/models/ \
    /opt/smartrover/data/ \
    /etc/smartrover/ \
    /var/log/smartrover/ \
    --exclude="*.pyc" \
    --exclude="__pycache__"

# Keep only last 10 backups
cd "$BACKUP_DIR"
ls -t smartrover_backup_*.tar.gz | tail -n +11 | xargs -r rm

echo "Backup completed: $BACKUP_FILE"
"""
        
        backup_script_path = Path('/usr/local/bin/smartrover-backup')
        with open(backup_script_path, 'w') as f:
            f.write(backup_script)
        
        backup_script_path.chmod(0o755)
        logger.info(f"Created backup script: {backup_script_path}")
    
    def setup_cron_jobs(self):
        """Setup cron jobs for maintenance"""
        logger.info("Setting up cron jobs...")
        
        cron_content = """# SmartRover Maintenance Cron Jobs
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/smartrover-backup

# Weekly log cleanup at 3 AM on Sunday
0 3 * * 0 find /var/log/smartrover -name "*.log.*" -mtime +30 -delete

# Daily system health check at 6 AM
0 6 * * * /usr/local/bin/smartrover-status > /var/log/smartrover/health_check.log 2>&1
"""
        
        cron_file = Path('/etc/cron.d/smartrover')
        with open(cron_file, 'w') as f:
            f.write(cron_content)
        
        cron_file.chmod(0o644)
        logger.info(f"Created cron jobs: {cron_file}")
    
    def optimize_system(self):
        """Optimize system for production"""
        logger.info("Optimizing system for production...")
        
        # GPU memory split for Raspberry Pi
        try:
            subprocess.run(['raspi-config', 'nonint', 'do_memory_split', '128'], check=True)
            logger.info("Set GPU memory split to 128MB")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Could not set GPU memory split (not on Raspberry Pi?)")
        
        # Enable I2C and SPI
        try:
            subprocess.run(['raspi-config', 'nonint', 'do_i2c', '0'], check=True)
            subprocess.run(['raspi-config', 'nonint', 'do_spi', '0'], check=True)
            logger.info("Enabled I2C and SPI interfaces")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Could not enable I2C/SPI (not on Raspberry Pi?)")
    
    def setup_directories(self):
        """Setup required directories"""
        logger.info("Setting up directories...")
        
        directories = [
            self.config_dir,
            self.log_dir,
            Path('/var/lib/smartrover'),
            Path('/var/run/smartrover')
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            subprocess.run(['chown', 'smartrover:smartrover', str(directory)], check=True)
            subprocess.run(['chmod', '755', str(directory)], check=True)
        
        logger.info("Directories setup completed")
    
    def create_systemd_services(self):
        """Create systemd service files"""
        logger.info("Creating systemd services...")
        
        # Main server service
        server_service = f"""[Unit]
Description=SmartRover Mining Vehicle Server
After=network.target bluetooth.target
Wants=network.target bluetooth.target

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory={self.project_root}
Environment=PATH={self.project_root}/venv/bin
ExecStart={self.project_root}/venv/bin/python scripts/enhanced_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartrover-server

[Install]
WantedBy=multi-user.target
"""
        
        # Vehicle controller service
        vehicle_service = f"""[Unit]
Description=SmartRover Vehicle Controller
After=network.target
Wants=network.target

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory={self.project_root}
Environment=PATH={self.project_root}/venv/bin
ExecStart={self.project_root}/venv/bin/python scripts/vehicle_controller.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartrover-vehicle

[Install]
WantedBy=multi-user.target
"""
        
        # Write service files
        with open(self.services_dir / 'smartrover-server.service', 'w') as f:
            f.write(server_service)
        
        with open(self.services_dir / 'smartrover-vehicle.service', 'w') as f:
            f.write(vehicle_service)
        
        # Reload systemd and enable services
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', 'smartrover-server.service'], check=True)
        subprocess.run(['systemctl', 'enable', 'smartrover-vehicle.service'], check=True)
        
        logger.info("Systemd services created and enabled")
    
    def setup_nginx(self):
        """Setup Nginx reverse proxy"""
        logger.info("Setting up Nginx...")
        
        nginx_config = """server {
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
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
    }
    
    # Health check
    location /health {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Static files (if serving dashboard from Pi)
    location / {
        root /var/www/smartrover;
        try_files $uri $uri/ /index.html;
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
    
    def setup_bluetooth(self):
        """Setup Bluetooth configuration"""
        logger.info("Setting up Bluetooth...")
        
        # Enable Bluetooth service
        subprocess.run(['systemctl', 'enable', 'bluetooth'], check=True)
        subprocess.run(['systemctl', 'start', 'bluetooth'], check=True)
        
        # Make device discoverable
        bluetooth_config = """[General]
Name = SmartRover-Mining-Vehicle
Class = 0x000100
DiscoverableTimeout = 0
PairableTimeout = 0
Discoverable = true
Pairable = true

[Policy]
AutoEnable = true
"""
        
        with open('/etc/bluetooth/main.conf', 'w') as f:
            f.write(bluetooth_config)
        
        subprocess.run(['systemctl', 'restart', 'bluetooth'], check=True)
        
        logger.info("Bluetooth setup completed")
    
    def setup_logrotate(self):
        """Setup log rotation"""
        logger.info("Setting up log rotation...")
        
        logrotate_config = """/var/log/smartrover/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 smartrover smartrover
    postrotate
        systemctl reload smartrover-server || true
    endscript
}
"""
        
        with open('/etc/logrotate.d/smartrover', 'w') as f:
            f.write(logrotate_config)
        
        logger.info("Log rotation setup completed")
    
    def create_startup_script(self):
        """Create startup script"""
        logger.info("Creating startup script...")
        
        startup_script = f"""#!/bin/bash
# SmartRover Mining Vehicle Startup Script

set -e

echo "Starting SmartRover Mining Vehicle System..."

# Start services
systemctl start smartrover-server
systemctl start smartrover-vehicle
systemctl start nginx
systemctl start bluetooth

# Wait for services to start
sleep 5

# Check service status
echo "Service Status:"
systemctl is-active smartrover-server && echo "✓ Server: Running" || echo "✗ Server: Failed"
systemctl is-active smartrover-vehicle && echo "✓ Vehicle: Running" || echo "✗ Vehicle: Failed"
systemctl is-active nginx && echo "✓ Nginx: Running" || echo "✗ Nginx: Failed"
systemctl is-active bluetooth && echo "✓ Bluetooth: Running" || echo "✗ Bluetooth: Failed"

echo ""
echo "SmartRover Mining Vehicle System started successfully!"
echo "Access the dashboard at: http://$(hostname -I | awk '{{print $1}}')"
echo "Bluetooth device name: SmartRover-Mining-Vehicle"
echo ""
echo "Logs can be viewed with:"
echo "  journalctl -u smartrover-server -f"
echo "  journalctl -u smartrover-vehicle -f"
"""
        
        startup_script_path = Path('/usr/local/bin/smartrover-start')
        with open(startup_script_path, 'w') as f:
            f.write(startup_script)
        
        subprocess.run(['chmod', '+x', str(startup_script_path)], check=True)
        
        logger.info("Startup script created")
    
    def set_permissions(self):
        """Set proper file permissions"""
        logger.info("Setting file permissions...")
        
        # Set ownership
        subprocess.run(['chown', '-R', f'{self.user}:{self.user}', str(self.base_dir)], check=True)
        subprocess.run(['chown', '-R', f'{self.user}:{self.user}', str(self.log_dir)], check=True)
        
        # Set permissions
        subprocess.run(['chmod', '-R', '755', str(self.base_dir)], check=True)
        subprocess.run(['chmod', '-R', '644', str(self.config_dir)], check=True)
        subprocess.run(['chmod', '-R', '755', str(self.log_dir)], check=True)
        
        logger.info("Set file permissions")
    
    def run_setup(self):
        """Run complete production setup"""
        logger.info("Starting SmartRover production setup...")
        
        self.check_root()
        self.install_system_dependencies()
        self.setup_python_environment()
        self.create_system_user()
        self.create_directories()
        self.create_config_files()
        self.setup_gpio_permissions()
        self.setup_bluetooth_permissions()
        self.create_backup_script()
        self.setup_cron_jobs()
        self.optimize_system()
        self.setup_directories()
        self.create_systemd_services()
        self.setup_nginx()
        self.setup_bluetooth()
        self.setup_logrotate()
        self.create_startup_script()
        self.set_permissions()
        
        logger.info("Production setup completed successfully!")
        logger.info("System is ready for deployment.")

if __name__ == "__main__":
    setup = ProductionSetup()
    setup.run_setup()
