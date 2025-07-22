#!/bin/bash

# SmartRover Mining Vehicle - Installation Script
# This script installs all dependencies and sets up the system

set -e  # Exit on any error

echo "🚀 Starting SmartRover Installation..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo "🔧 Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    cmake \
    pkg-config \
    libjpeg-dev \
    libtiff5-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libfontconfig1-dev \
    libcairo2-dev \
    libgdk-pixbuf2.0-dev \
    libpango1.0-dev \
    libgtk2.0-dev \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran \
    libhdf5-dev \
    libhdf5-serial-dev \
    libhdf5-103 \
    libqt5gui5 \
    libqt5webkit5 \
    libqt5test5 \
    python3-pyqt5 \
    bluetooth \
    bluez \
    libbluetooth-dev \
    nginx \
    git \
    curl \
    wget \
    unzip

# Install Node.js and npm
echo "📦 Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Create smartrover user if it doesn't exist
if ! id "smartrover" &>/dev/null; then
    echo "👤 Creating smartrover user..."
    sudo useradd -m -s /bin/bash smartrover
    sudo usermod -a -G gpio,i2c,spi,video,audio,bluetooth smartrover
fi

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/smartrover
sudo chown smartrover:smartrover /opt/smartrover

# Copy files to application directory
echo "📋 Copying application files..."
sudo cp -r . /opt/smartrover/
sudo chown -R smartrover:smartrover /opt/smartrover

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
sudo -u smartrover python3 -m venv /opt/smartrover/venv
sudo -u smartrover /opt/smartrover/venv/bin/pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies..."
sudo -u smartrover /opt/smartrover/venv/bin/pip install -r /opt/smartrover/requirements.txt

# Install Bluetooth dependencies separately (with fallback)
echo "🔵 Installing Bluetooth support..."
if ! sudo -u smartrover /opt/smartrover/venv/bin/pip install pybluez; then
    echo "⚠️  pybluez failed to install, using bleak as alternative..."
    sudo -u smartrover /opt/smartrover/venv/bin/pip install bleak
fi

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
cd /opt/smartrover
sudo -u smartrover npm install

# Build the dashboard
echo "🏗️  Building dashboard..."
sudo -u smartrover npm run build

# Set up systemd services
echo "⚙️  Setting up system services..."

# Vehicle service
sudo tee /etc/systemd/system/smartrover-vehicle.service > /dev/null <<EOF
[Unit]
Description=SmartRover Vehicle Controller
After=network.target
Wants=network.target

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory=/opt/smartrover
Environment=PATH=/opt/smartrover/venv/bin
ExecStart=/opt/smartrover/venv/bin/python scripts/standalone_vehicle_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Bluetooth service
sudo tee /etc/systemd/system/smartrover-bluetooth.service > /dev/null <<EOF
[Unit]
Description=SmartRover Bluetooth Server
After=network.target bluetooth.target
Wants=network.target bluetooth.target

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory=/opt/smartrover
Environment=PATH=/opt/smartrover/venv/bin
ExecStart=/opt/smartrover/venv/bin/python scripts/bluetooth_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Dashboard service
sudo tee /etc/systemd/system/smartrover-dashboard.service > /dev/null <<EOF
[Unit]
Description=SmartRover Dashboard
After=network.target
Wants=network.target

[Service]
Type=simple
User=smartrover
Group=smartrover
WorkingDirectory=/opt/smartrover
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "🌐 Configuring web server..."
sudo tee /etc/nginx/sites-available/smartrover > /dev/null <<EOF
server {
    listen 80;
    server_name _;
    
    # Dashboard
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/smartrover /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Enable and start services
echo "🚀 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable smartrover-vehicle
sudo systemctl enable smartrover-bluetooth
sudo systemctl enable smartrover-dashboard
sudo systemctl enable nginx

sudo systemctl start smartrover-vehicle
sudo systemctl start smartrover-bluetooth
sudo systemctl start smartrover-dashboard
sudo systemctl restart nginx

# Configure GPIO permissions
echo "🔧 Configuring GPIO permissions..."
sudo usermod -a -G gpio smartrover

# Enable hardware interfaces
echo "⚙️  Enabling hardware interfaces..."
if command -v raspi-config &> /dev/null; then
    sudo raspi-config nonint do_i2c 0
    sudo raspi-config nonint do_spi 0
    sudo raspi-config nonint do_camera 0
    sudo raspi-config nonint do_ssh 0
fi

# Create log directories
sudo mkdir -p /var/log/smartrover
sudo chown smartrover:smartrover /var/log/smartrover

# Set up log rotation
sudo tee /etc/logrotate.d/smartrover > /dev/null <<EOF
/var/log/smartrover/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
    su smartrover smartrover
}
EOF

# Create startup script
sudo tee /opt/smartrover/start_all.sh > /dev/null <<'EOF'
#!/bin/bash
echo "🚀 Starting SmartRover services..."
sudo systemctl start smartrover-vehicle
sudo systemctl start smartrover-bluetooth
sudo systemctl start smartrover-dashboard
sudo systemctl start nginx
echo "✅ All services started!"
EOF

sudo chmod +x /opt/smartrover/start_all.sh

# Get system IP
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo ""
echo "🎉 SmartRover installation completed successfully!"
echo ""
echo "📊 Dashboard URL: http://$IP_ADDRESS"
echo "🔐 Default login: cvlised360@gmail.com / Cvlised@360"
echo ""
echo "🔧 Service Management:"
echo "  Start all:    sudo /opt/smartrover/start_all.sh"
echo "  Stop all:     sudo systemctl stop smartrover-*"
echo "  View logs:    sudo journalctl -u smartrover-vehicle -f"
echo ""
echo "🔍 Service Status:"
sudo systemctl status smartrover-vehicle --no-pager -l
sudo systemctl status smartrover-bluetooth --no-pager -l
sudo systemctl status smartrover-dashboard --no-pager -l
sudo systemctl status nginx --no-pager -l
echo ""
echo "✅ Installation complete! Access your dashboard at http://$IP_ADDRESS"
