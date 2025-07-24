#!/bin/bash

# SmartRover Mining Vehicle Installation Script
# This script sets up the complete autonomous mining system

set -e

echo "🚀 Starting SmartRover Mining Vehicle Installation..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="smartrover"
INSTALL_DIR="/opt/smartrover"
SERVICE_USER="smartrover"
LOG_DIR="/var/log/smartrover"
DATA_DIR="/var/lib/smartrover"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Detect system architecture
detect_system() {
    print_status "Detecting system architecture..."
    
    if [[ -f /proc/device-tree/model ]] && grep -q "Raspberry Pi" /proc/device-tree/model; then
        SYSTEM_TYPE="raspberry_pi"
        print_success "Detected Raspberry Pi"
    else
        SYSTEM_TYPE="generic_linux"
        print_warning "Generic Linux system detected - some features may not work"
    fi
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    
    apt update
    apt upgrade -y
    
    print_success "System packages updated"
}

# Install system dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    # Essential packages
    PACKAGES=(
        "python3"
        "python3-pip"
        "python3-venv"
        "python3-dev"
        "build-essential"
        "sqlite3"
        "curl"
        "wget"
        "git"
        "nginx"
    )
    
    # Raspberry Pi specific packages
    if [[ "$SYSTEM_TYPE" == "raspberry_pi" ]]; then
        PACKAGES+=(
            "bluetooth"
            "bluez"
            "libbluetooth-dev"
            "python3-bluez"
            "raspi-config"
            "rpi.gpio-common"
            "python3-rpi.gpio"
        )
    fi
    
    apt install -y "${PACKAGES[@]}"
    
    print_success "System dependencies installed"
}

# Create system user
create_user() {
    print_status "Creating system user: $SERVICE_USER"
    
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd --system --shell /bin/false --home "$DATA_DIR" --create-home "$SERVICE_USER"
        print_success "Created user: $SERVICE_USER"
    else
        print_warning "User $SERVICE_USER already exists"
    fi
    
    # Add user to required groups
    if [[ "$SYSTEM_TYPE" == "raspberry_pi" ]]; then
        usermod -a -G gpio,i2c,spi,bluetooth,video "$SERVICE_USER"
        print_success "Added $SERVICE_USER to hardware groups"
    fi
}

# Create directories
create_directories() {
    print_status "Creating directories..."
    
    DIRECTORIES=(
        "$INSTALL_DIR"
        "$LOG_DIR"
        "$DATA_DIR"
        "$DATA_DIR/models"
        "$DATA_DIR/maps"
        "$DATA_DIR/backups"
        "/etc/smartrover"
        "/var/run/smartrover"
    )
    
    for dir in "${DIRECTORIES[@]}"; do
        mkdir -p "$dir"
        chown "$SERVICE_USER:$SERVICE_USER" "$dir"
        chmod 755 "$dir"
    done
    
    print_success "Directories created"
}

# Install Python dependencies
install_python_deps() {
    print_status "Setting up Python environment..."
    
    # Create virtual environment
    python3 -m venv "$INSTALL_DIR/venv"
    
    # Activate virtual environment
    source "$INSTALL_DIR/venv/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    # Install core dependencies
    pip install numpy
    pip install opencv-python
    pip install tensorflow
    pip install flask
    pip install flask-cors
    pip install gpiozero
    pip install RPi.GPIO
    pip install psutil
    pip install requests
    pip install Pillow
    pip install scipy
    pip install bleak
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/venv"
    
    print_success "Python environment setup completed"
}

# Copy project files
copy_project_files() {
    print_status "Copying project files..."
    
    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    # Copy Python scripts
    cp -r "$PROJECT_ROOT/scripts/"* "$INSTALL_DIR/"
    
    # Set ownership and permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR"/*.py
    chmod +x "$INSTALL_DIR"/*.sh
    
    print_success "Project files copied"
}

# Configure Raspberry Pi specific settings
configure_raspberry_pi() {
    if [[ "$SYSTEM_TYPE" != "raspberry_pi" ]]; then
        return
    fi
    
    print_status "Configuring Raspberry Pi settings..."
    
    # Enable required interfaces
    raspi-config nonint do_i2c 0
    raspi-config nonint do_spi 0
    raspi-config nonint do_camera 0
    raspi-config nonint do_ssh 0
    
    # Set GPU memory split
    raspi-config nonint do_memory_split 128
    
    # Enable hardware PWM
    echo "dtoverlay=pwm-2chan" >> /boot/config.txt
    
    print_success "Raspberry Pi configured"
}

# Create configuration files
create_config_files() {
    print_status "Creating configuration files..."
    
    # Main configuration
    cat > /etc/smartrover/config.json << 'EOF'
{
    "vehicle": {
        "id": "smartrover_001",
        "name": "SmartRover Mining Vehicle",
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
        "auto_return_dock": true,
        "max_session_time": 7200
    },
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": false
    },
    "logging": {
        "level": "INFO",
        "max_size": "10MB",
        "backup_count": 5
    }
}
EOF
    
    chown "$SERVICE_USER:$SERVICE_USER" /etc/smartrover/config.json
    chmod 644 /etc/smartrover/config.json
    
    print_success "Configuration files created"
}

# Create systemd services
create_systemd_services() {
    print_status "Creating systemd services..."
    
    # Main server service
    cat > /etc/systemd/system/smartrover.service << EOF
[Unit]
Description=SmartRover Mining Vehicle Server
Documentation=https://github.com/smartrover/mining-vehicle
After=network.target bluetooth.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/scripts/standalone_vehicle_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartrover

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA_DIR $LOG_DIR /var/run/smartrover

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable services
    systemctl daemon-reload
    systemctl enable smartrover.service
    
    print_success "Systemd services created and enabled"
}

# Setup Nginx reverse proxy
setup_nginx() {
    print_status "Setting up Nginx reverse proxy..."
    
    cat > /etc/nginx/sites-available/smartrover << 'EOF'
server {
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
    
    # Status page
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Deny access to sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF
    
    # Enable site and remove default
    ln -sf /etc/nginx/sites-available/smartrover /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t
    
    # Enable and start Nginx
    systemctl enable nginx
    systemctl restart nginx
    
    print_success "Nginx configured and started"
}

# Setup log rotation
setup_logrotate() {
    print_status "Setting up log rotation..."
    
    cat > /etc/logrotate.d/smartrover << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload smartrover || true
    endscript
}
EOF
    
    print_success "Log rotation configured"
}

# Create management scripts
create_management_scripts() {
    print_status "Creating management scripts..."
    
    # Status script
    cat > /usr/local/bin/smartrover-status << 'EOF'
#!/bin/bash
echo "SmartRover Status"
echo "================="
systemctl status smartrover --no-pager
echo
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
EOF

    # Start script
    cat > /usr/local/bin/smartrover-start << 'EOF'
#!/bin/bash
echo "Starting SmartRover..."
sudo systemctl start smartrover
EOF

    # Stop script
    cat > /usr/local/bin/smartrover-stop << 'EOF'
#!/bin/bash
echo "Stopping SmartRover..."
sudo systemctl stop smartrover
EOF

    chmod +x /usr/local/bin/smartrover-*

    print_success "Management scripts created"
}

# Initialize database
initialize_database() {
    print_status "Initializing database..."
    
    python3 "$INSTALL_DIR/scripts/production_setup.py" || print_warning "Production setup had some issues"
}

# Start services
start_services() {
    print_status "Starting services..."
    
    systemctl start smartrover
    sleep 5
    systemctl status smartrover --no-pager || print_warning "Service may still be starting..."
    
    print_success "Services started"
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check services
    if systemctl is-active --quiet smartrover; then
        print_success "SmartRover server is running"
    else
        print_error "SmartRover server failed to start"
        return 1
    fi
    
    # Check API endpoint
    sleep 10
    if curl -s http://localhost:5000/health >/dev/null; then
        print_success "API endpoint is responding"
    else
        print_error "API endpoint is not responding"
        return 1
    fi
    
    print_success "Installation verification completed"
}

# Print final information
print_final_info() {
    clear
    echo
    echo "🎉 SmartRover Mining Vehicle Installation Complete!"
    echo "=================================================="
    echo
    echo "System Information:"
    echo "  • Installation Directory: $INSTALL_DIR"
    echo "  • Data Directory: $DATA_DIR"
    echo "  • Log Directory: $LOG_DIR"
    echo "  • Service User: $SERVICE_USER"
    echo
    echo "Access Information:"
    IP_ADDRESS=$(hostname -I | awk '{print $1}')
    echo "  • Dashboard URL: http://$IP_ADDRESS"
    echo "  • API Endpoint: http://$IP_ADDRESS:5000/api"
    echo "  • Health Check: http://$IP_ADDRESS:5000/health"
    echo
    echo "Management Commands:"
    echo "  • Status: smartrover-status"
    echo "  • Start: smartrover-start"
    echo "  • Stop: smartrover-stop"
    echo
    echo "Service Management:"
    echo "  • View logs: journalctl -u smartrover -f"
    echo
    echo "Features:"
    echo "  ✓ Automatic startup on boot"
    echo "  ✓ Waypoint-based autonomous navigation"
    echo "  ✓ Real-time SLAM mapping"
    echo "  ✓ Web-based dashboard control"
    echo "  ✓ Mining operation management"
    echo "  ✓ Automatic return to docking station"
    echo "  ✓ System monitoring and logging"
    echo "  ✓ Automatic backups"
    echo
    echo "Next Steps:"
    echo "  1. Access the dashboard at http://$IP_ADDRESS"
    echo "  2. Add mining waypoints on the map"
    echo "  3. Start mining operation from the dashboard"
    echo "  4. Monitor progress and system status"
    echo
    echo "The system will automatically start on boot and begin mapping."
    echo "Use the dashboard to add waypoints and control mining operations."
    echo
}

# Main installation function
main() {
    echo "🚀 SmartRover Mining Vehicle Installation"
    echo "========================================"
    echo
    
    check_root
    detect_system
    update_system
    install_dependencies
    create_user
    create_directories
    install_python_deps
    copy_project_files
    configure_raspberry_pi
    create_config_files
    create_systemd_services
    setup_nginx
    setup_logrotate
    create_management_scripts
    initialize_database
    start_services
    
    if verify_installation; then
        print_final_info
    else
        print_error "Installation verification failed. Check logs for details."
        exit 1
    fi
}

# Run main function
main "$@"
