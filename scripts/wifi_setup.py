#!/usr/bin/env python3
"""
WiFi Setup and Configuration Script for SmartRover
Configures WiFi discovery, mDNS, and network services
"""

import os
import sys
import subprocess
import logging
import json
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WiFiSetup:
    def __init__(self):
        self.config_dir = Path('/etc/smartrover')
        self.log_dir = Path('/var/log/smartrover')
        self.service_dir = Path('/etc/systemd/system')
        
    def setup_directories(self):
        """Create necessary directories"""
        logger.info("📁 Creating directories...")
        
        directories = [
            self.config_dir,
            self.log_dir,
            Path('/var/lib/smartrover')
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Created directory: {directory}")
    
    def install_dependencies(self):
        """Install required system packages"""
        logger.info("📦 Installing system dependencies...")
        
        packages = [
            'avahi-daemon',
            'avahi-utils',
            'wireless-tools',
            'net-tools',
            'iw',
            'hostapd',
            'dnsmasq'
        ]
        
        try:
            # Update package list
            subprocess.run(['apt', 'update'], check=True)
            
            # Install packages
            cmd = ['apt', 'install', '-y'] + packages
            subprocess.run(cmd, check=True)
            
            logger.info("📦 System dependencies installed successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install dependencies: {e}")
            return False
        
        return True
    
    def configure_avahi(self):
        """Configure Avahi mDNS service"""
        logger.info("🔧 Configuring Avahi mDNS service...")
        
        avahi_config = """<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
    <name replace-wildcards="yes">SmartRover Mining Vehicle on %h</name>
    <service>
        <type>_smartrover._tcp</type>
        <port>8889</port>
        <txt-record>version=2.0.0</txt-record>
        <txt-record>device_type=mining_vehicle</txt-record>
        <txt-record>features=autonomous_mining,real_time_control,sensor_monitoring</txt-record>
        <txt-record>http_port=5000</txt-record>
        <txt-record>manufacturer=SmartRover Systems</txt-record>
    </service>
    <service>
        <type>_http._tcp</type>
        <port>5000</port>
        <txt-record>path=/</txt-record>
        <txt-record>description=SmartRover Web Interface</txt-record>
    </service>
</service-group>"""
        
        try:
            avahi_service_file = Path('/etc/avahi/services/smartrover.service')
            avahi_service_file.write_text(avahi_config)
            
            # Enable and start Avahi
            subprocess.run(['systemctl', 'enable', 'avahi-daemon'], check=True)
            subprocess.run(['systemctl', 'restart', 'avahi-daemon'], check=True)
            
            logger.info("🔧 Avahi mDNS service configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure Avahi: {e}")
            return False
    
    def create_wifi_discovery_service(self):
        """Create systemd service for WiFi discovery"""
        logger.info("🔧 Creating WiFi discovery systemd service...")
        
        service_content = f"""[Unit]
Description=SmartRover WiFi Discovery Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/smartrover
ExecStart=/usr/bin/python3 /opt/smartrover/scripts/wifi_discovery_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        try:
            service_file = self.service_dir / 'smartrover-wifi-discovery.service'
            service_file.write_text(service_content)
            
            # Reload systemd and enable service
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', 'enable', 'smartrover-wifi-discovery'], check=True)
            
            logger.info("🔧 WiFi discovery service created successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create WiFi discovery service: {e}")
            return False
    
    def configure_network_interfaces(self):
        """Configure network interfaces for optimal discovery"""
        logger.info("🔧 Configuring network interfaces...")
        
        try:
            # Enable IP forwarding
            with open('/etc/sysctl.conf', 'a') as f:
                f.write('\n# SmartRover network configuration\n')
                f.write('net.ipv4.ip_forward=1\n')
                f.write('net.ipv6.conf.all.forwarding=1\n')
            
            # Apply sysctl changes
            subprocess.run(['sysctl', '-p'], check=True)
            
            logger.info("🔧 Network interfaces configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure network interfaces: {e}")
            return False
    
    def create_wifi_config(self):
        """Create WiFi configuration file"""
        logger.info("🔧 Creating WiFi configuration...")
        
        wifi_config = {
            "discovery": {
                "enabled": True,
                "udp_port": 8888,
                "tcp_port": 8889,
                "broadcast_interval": 30,
                "mdns_enabled": True
            },
            "network": {
                "scan_interval": 300,
                "auto_connect": False,
                "preferred_networks": []
            },
            "security": {
                "allow_control": True,
                "require_auth": False,
                "max_clients": 10
            }
        }
        
        try:
            config_file = self.config_dir / 'wifi_config.json'
            config_file.write_text(json.dumps(wifi_config, indent=2))
            
            logger.info("🔧 WiFi configuration created successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create WiFi configuration: {e}")
            return False
    
    def setup_firewall_rules(self):
        """Setup firewall rules for WiFi discovery"""
        logger.info("🔧 Setting up firewall rules...")
        
        try:
            # Allow mDNS
            subprocess.run(['ufw', 'allow', '5353/udp'], check=True)
            
            # Allow WiFi discovery ports
            subprocess.run(['ufw', 'allow', '8888/udp'], check=True)
            subprocess.run(['ufw', 'allow', '8889/tcp'], check=True)
            
            # Allow HTTP
            subprocess.run(['ufw', 'allow', '5000/tcp'], check=True)
            
            logger.info("🔧 Firewall rules configured successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ Firewall configuration failed (may not be installed): {e}")
            return True  # Continue even if ufw is not available
    
    def test_wifi_discovery(self):
        """Test WiFi discovery functionality"""
        logger.info("🧪 Testing WiFi discovery...")
        
        try:
            # Test mDNS resolution
            result = subprocess.run(
                ['avahi-resolve', '-n', f'{os.uname().nodename}.local'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("🧪 mDNS resolution test passed")
            else:
                logger.warning("⚠️ mDNS resolution test failed")
            
            # Test network interfaces
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            if 'wlan0' in result.stdout or 'eth0' in result.stdout:
                logger.info("🧪 Network interfaces detected")
            else:
                logger.warning("⚠️ No network interfaces detected")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ WiFi discovery test failed: {e}")
            return False
    
    def create_discovery_client_example(self):
        """Create example client for testing discovery"""
        logger.info("📝 Creating discovery client example...")
        
        client_code = '''#!/usr/bin/env python3
"""
SmartRover WiFi Discovery Client Example
Use this to test discovery and connection to SmartRover vehicles
"""

import socket
import json
import time
import threading
from zeroconf import ServiceBrowser, Zeroconf

class SmartRoverDiscoveryClient:
    def __init__(self):
        self.discovered_vehicles = {}
        self.zeroconf = None
        
    def discover_via_udp(self, timeout=5):
        """Discover SmartRover vehicles via UDP broadcast"""
        print("🔍 Discovering SmartRover vehicles via UDP...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        
        # Send discovery message
        message = "SMARTROVER_DISCOVERY"
        sock.sendto(message.encode('utf-8'), ('<broadcast>', 8888))
        
        vehicles = []
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                response = json.loads(data.decode('utf-8'))
                
                if response.get('type') == 'smartrover_response':
                    vehicles.append({
                        'ip': addr[0],
                        'data': response
                    })
                    print(f"📡 Found vehicle: {response.get('hostname')} at {addr[0]}")
                    
            except socket.timeout:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        sock.close()
        return vehicles
    
    def discover_via_mdns(self, timeout=10):
        """Discover SmartRover vehicles via mDNS"""
        print("🔍 Discovering SmartRover vehicles via mDNS...")
        
        self.zeroconf = Zeroconf()
        
        class SmartRoverListener:
            def __init__(self, client):
                self.client = client
                
            def remove_service(self, zeroconf, type, name):
                print(f"📡 Service removed: {name}")
                
            def add_service(self, zeroconf, type, name):
                info = zeroconf.get_service_info(type, name)
                if info:
                    print(f"📡 Found mDNS service: {name}")
                    print(f"   Address: {socket.inet_ntoa(info.addresses[0])}")
                    print(f"   Port: {info.port}")
                    print(f"   Properties: {info.properties}")
        
        listener = SmartRoverListener(self)
        browser = ServiceBrowser(self.zeroconf, "_smartrover._tcp.local.", listener)
        
        time.sleep(timeout)
        
        self.zeroconf.close()
        return []
    
    def connect_to_vehicle(self, ip, port=8889):
        """Connect to a discovered vehicle"""
        print(f"🔗 Connecting to vehicle at {ip}:{port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            
            # Receive welcome message
            data = sock.recv(4096)
            welcome = json.loads(data.decode('utf-8'))
            print(f"📨 Welcome: {welcome.get('message')}")
            
            # Send ping
            ping_msg = {"type": "ping"}
            sock.send(json.dumps(ping_msg).encode('utf-8'))
            
            # Receive pong
            data = sock.recv(4096)
            response = json.loads(data.decode('utf-8'))
            print(f"📨 Response: {response}")
            
            sock.close()
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

def main():
    client = SmartRoverDiscoveryClient()
    
    # Discover via UDP
    vehicles = client.discover_via_udp()
    
    if vehicles:
        print(f"\\n✅ Found {len(vehicles)} vehicle(s)")
        
        # Try to connect to the first vehicle
        vehicle = vehicles[0]
        client.connect_to_vehicle(vehicle['ip'])
    else:
        print("❌ No vehicles discovered")
    
    # Discover via mDNS
    client.discover_via_mdns()

if __name__ == "__main__":
    main()
'''
        
        try:
            client_file = Path('/opt/smartrover/scripts/discovery_client_example.py')
            client_file.parent.mkdir(parents=True, exist_ok=True)
            client_file.write_text(client_code)
            client_file.chmod(0o755)
            
            logger.info("📝 Discovery client example created successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create discovery client example: {e}")
            return False
    
    def run_setup(self):
        """Run complete WiFi setup"""
        logger.info("🚀 Starting SmartRover WiFi Setup...")
        
        steps = [
            ("Creating directories", self.setup_directories),
            ("Installing dependencies", self.install_dependencies),
            ("Configuring Avahi mDNS", self.configure_avahi),
            ("Creating WiFi discovery service", self.create_wifi_discovery_service),
            ("Configuring network interfaces", self.configure_network_interfaces),
            ("Creating WiFi configuration", self.create_wifi_config),
            ("Setting up firewall rules", self.setup_firewall_rules),
            ("Creating discovery client example", self.create_discovery_client_example),
            ("Testing WiFi discovery", self.test_wifi_discovery)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"🔄 {step_name}...")
            if not step_func():
                logger.error(f"❌ Failed: {step_name}")
                return False
            logger.info(f"✅ Completed: {step_name}")
        
        logger.info("🎉 SmartRover WiFi Setup completed successfully!")
        logger.info("📋 Next steps:")
        logger.info("   1. Start the WiFi discovery service: sudo systemctl start smartrover-wifi-discovery")
        logger.info("   2. Check service status: sudo systemctl status smartrover-wifi-discovery")
        logger.info("   3. Test discovery: python3 /opt/smartrover/scripts/discovery_client_example.py")
        logger.info("   4. View logs: sudo journalctl -u smartrover-wifi-discovery -f")
        
        return True

def main():
    if os.geteuid() != 0:
        logger.error("❌ This script must be run as root (use sudo)")
        sys.exit(1)
    
    setup = WiFiSetup()
    success = setup.run_setup()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
