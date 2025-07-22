#!/bin/bash
# SmartRover Mining Vehicle Installation Script

set -e

echo "🚀 Installing SmartRover Mining Vehicle System..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 Project root: $PROJECT_ROOT"

# Update system
echo "📦 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install system dependencies
echo "🔧 Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    bluetooth \
    bluez \
    libbluetooth-dev \
    build-essential \
    cmake \
    pkg-config \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran \
    python3-dev \
    supervisor

# Create system user
echo "👤 Creating smartrover user..."
if ! id "smartrover" &>/dev/null; then
    useradd -r -s /bin/bash -d /opt/smartrover -m smartrover
    usermod -a -G dialout,gpio,i2c,spi,bluetooth smartrover
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p /opt/smartrover
mkdir -p /var/log/smartrover
mkdir -p /etc/smartrover
mkdir -p /opt/smartrover/venv

# Set permissions
chown -R smartrover:smartrover /opt/smartrover
chown -R smartrover:smartrover /var/log/smartrover

# Copy application files
echo "📋 Installing application files..."
cp -r scripts/* /opt/smartrover/
cp requirements.txt /opt/smartrover/

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
sudo -u smartrover python3 -m venv /opt/smartrover/venv
sudo -u smartrover /opt/smartrover/venv/bin/pip install --upgrade pip
sudo -u smartrover /opt/smartrover/venv/bin/pip install -r /opt/smartrover/requirements.txt

# Install additional Python packages
sudo -u smartrover /opt/smartrover/venv/bin/pip install \
    flask \
    flask-cors \
    flask-session \
    psutil \
    pybluez \
    opencv-python \
    numpy \
    tensorflow \
    scikit-learn

# Configure Bluetooth
echo "📡 Configuring Bluetooth..."
systemctl enable bluetooth
systemctl start bluetooth

# Add smartrover user to bluetooth group
usermod -a -G bluetooth smartrover

# Configure Bluetooth for serial port profile
cat > /etc/systemd/system/bluetooth.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=/usr/lib/bluetooth/bluetoothd --experimental
EOF

# Create systemd service for vehicle server
echo "⚙️ Creating systemd services..."
cat > /etc/systemd/system/smartrover-vehicle.service << EOF
[Unit]
Description=SmartRover Mining Vehicle Server
After=network.target bluetooth.service
Wants=bluetooth.service

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory=/opt/smartrover
Environment=PATH=/opt/smartrover/venv/bin
ExecStart=/opt/smartrover/venv/bin/python standalone_vehicle_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Bluetooth server
cat > /etc/systemd/system/smartrover-bluetooth.service << EOF
[Unit]
Description=SmartRover Bluetooth Server
After=network.target bluetooth.service smartrover-vehicle.service
Wants=bluetooth.service
Requires=smartrover-vehicle.service

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory=/opt/smartrover
Environment=PATH=/opt/smartrover/venv/bin
ExecStart=/opt/smartrover/venv/bin/python bluetooth_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "🌐 Configuring Nginx..."
cat > /etc/nginx/sites-available/smartrover << EOF
server {
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    
    # Proxy to Flask application
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check
    location /health {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Serve static files (if any)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable Nginx site
ln -sf /etc/nginx/sites-available/smartrover /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Create startup script
echo "🚀 Creating startup scripts..."
cat > /usr/local/bin/smartrover-start << EOF
#!/bin/bash
echo "Starting SmartRover Mining Vehicle System..."
systemctl start smartrover-vehicle
systemctl start smartrover-bluetooth
systemctl start nginx
echo "SmartRover system started successfully!"
echo "Access dashboard at: http://\$(hostname -I | awk '{print \$1}')"
EOF

cat > /usr/local/bin/smartrover-stop << EOF
#!/bin/bash
echo "Stopping SmartRover Mining Vehicle System..."
systemctl stop smartrover-vehicle
systemctl stop smartrover-bluetooth
systemctl stop nginx
echo "SmartRover system stopped."
EOF

cat > /usr/local/bin/smartrover-status << EOF
#!/bin/bash
echo "SmartRover System Status:"
echo "========================"
systemctl status smartrover-vehicle --no-pager -l
echo ""
systemctl status smartrover-bluetooth --no-pager -l
echo ""
systemctl status nginx --no-pager -l
EOF

# Make scripts executable
chmod +x /usr/local/bin/smartrover-start
chmod +x /usr/local/bin/smartrover-stop
chmod +x /usr/local/bin/smartrover-status

# Configure log rotation
echo "📝 Configuring log rotation..."
cat > /etc/logrotate.d/smartrover << EOF
/var/log/smartrover/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 smartrover smartrover
    postrotate
        systemctl reload smartrover-vehicle
        systemctl reload smartrover-bluetooth
    endscript
}
EOF

# Enable and start services
echo "🔄 Enabling and starting services..."
systemctl daemon-reload
systemctl enable smartrover-vehicle
systemctl enable smartrover-bluetooth
systemctl enable nginx

# Start services
systemctl start smartrover-vehicle
systemctl start smartrover-bluetooth
systemctl restart nginx

# Configure firewall (if ufw is installed)
if command -v ufw &> /dev/null; then
    echo "🔥 Configuring firewall..."
    ufw allow 80/tcp
    ufw allow 5000/tcp
    ufw allow ssh
fi

# Create desktop shortcut (if desktop environment is available)
if [ -d "/home/pi/Desktop" ]; then
    echo "🖥️ Creating desktop shortcut..."
    cat > /home/pi/Desktop/SmartRover.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SmartRover Dashboard
Comment=Open SmartRover Mining Vehicle Dashboard
Exec=chromium-browser http://localhost
Icon=applications-internet
Terminal=false
Categories=Network;
EOF
    chmod +x /home/pi/Desktop/SmartRover.desktop
    chown pi:pi /home/pi/Desktop/SmartRover.desktop
fi

# Final system check
echo "🔍 Running system check..."
sleep 5

if systemctl is-active --quiet smartrover-vehicle; then
    echo "✅ Vehicle server is running"
else
    echo "❌ Vehicle server failed to start"
fi

if systemctl is-active --quiet smartrover-bluetooth; then
    echo "✅ Bluetooth server is running"
else
    echo "❌ Bluetooth server failed to start"
fi

if systemctl is-active --quiet nginx; then
    echo "✅ Nginx is running"
else
    echo "❌ Nginx failed to start"
fi

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo ""
echo "🎉 SmartRover Mining Vehicle System Installation Complete!"
echo "=========================================================="
echo ""
echo "📱 Dashboard Access:"
echo "   Local: http://localhost"
echo "   Network: http://$IP_ADDRESS"
echo ""
echo "🔐 Default Login Credentials:"
echo "   Email: cvlised360@gmail.com"
echo "   Password: Cvlised@360"
echo ""
echo "⚙️ System Management:"
echo "   Start:  sudo smartrover-start"
echo "   Stop:   sudo smartrover-stop"
echo "   Status: sudo smartrover-status"
echo ""
echo "📋 Log Files:"
echo "   Vehicle: /var/log/smartrover/vehicle.log"
echo "   System:  journalctl -u smartrover-vehicle -f"
echo ""
echo "🔧 Configuration:"
echo "   Vehicle Config: /opt/smartrover/"
echo "   Nginx Config:   /etc/nginx/sites-available/smartrover"
echo ""
echo "The system is now ready for use!"
