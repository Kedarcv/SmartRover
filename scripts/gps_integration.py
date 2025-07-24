#!/usr/bin/env python3
"""
SmartRover GPS Integration Module
Handles GPS positioning, waypoint navigation, and coordinate transformations
"""

import serial
import time
import threading
import logging
import json
import math
import sqlite3
from datetime import datetime
import pynmea2
import utm
from geopy.distance import geodesic
from geopy import Point
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/gps.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GPSModule:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600, database_path='/var/lib/smartrover/mining_data.db'):
        self.port = port
        self.baudrate = baudrate
        self.database_path = database_path
        self.serial_connection = None
        self.running = False
        self.current_position = None
        self.current_altitude = None
        self.current_speed = None
        self.current_heading = None
        self.satellites_in_use = 0
        self.fix_quality = 0
        self.hdop = 99.9  # Horizontal dilution of precision
        self.last_update = None
        self.position_history = []
        self.max_history = 1000
        
        # Coordinate system settings
        self.utm_zone = None
        self.utm_letter = None
        self.local_origin = None  # Local coordinate system origin
        
        # GPS status
        self.gps_available = False
        self.fix_available = False
        
        # Threading
        self.gps_thread = None
        self.data_lock = threading.Lock()
        
        # Initialize database
        self.init_gps_database()
        
    def init_gps_database(self):
        """Initialize GPS database tables"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # GPS positions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gps_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    speed REAL,
                    heading REAL,
                    satellites INTEGER,
                    fix_quality INTEGER,
                    hdop REAL,
                    utm_x REAL,
                    utm_y REAL,
                    local_x REAL,
                    local_y REAL
                )
            ''')
            
            # GPS waypoints table (enhanced with GPS coordinates)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gps_waypoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude REAL,
                    utm_x REAL,
                    utm_y REAL,
                    local_x REAL,
                    local_y REAL,
                    type TEXT DEFAULT 'mining',
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("GPS database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing GPS database: {e}")
    
    def start_gps(self):
        """Start GPS module"""
        logger.info("🛰️ Starting GPS module...")
        
        try:
            # Try to open serial connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            
            self.gps_available = True
            logger.info(f"🛰️ GPS serial connection established on {self.port}")
            
        except Exception as e:
            logger.warning(f"🛰️ GPS hardware not available: {e}")
            self.gps_available = False
            # Continue in simulation mode
        
        self.running = True
        
        # Start GPS reading thread
        self.gps_thread = threading.Thread(target=self.gps_reader_thread, daemon=True)
        self.gps_thread.start()
        
        logger.info("🛰️ GPS module started")
    
    def stop_gps(self):
        """Stop GPS module"""
        logger.info("🛰️ Stopping GPS module...")
        
        self.running = False
        
        if self.serial_connection:
            try:
                self.serial_connection.close()
            except:
                pass
        
        logger.info("🛰️ GPS module stopped")
    
    def gps_reader_thread(self):
        """GPS data reading thread"""
        logger.info("🛰️ GPS reader thread started")
        
        while self.running:
            try:
                if self.gps_available and self.serial_connection:
                    # Read real GPS data
                    self.read_real_gps_data()
                else:
                    # Simulate GPS data for testing
                    self.simulate_gps_data()
                
                time.sleep(1)  # 1 Hz GPS updates
                
            except Exception as e:
                logger.error(f"GPS reader thread error: {e}")
                time.sleep(5)
        
        logger.info("🛰️ GPS reader thread stopped")
    
    def read_real_gps_data(self):
        """Read and parse real GPS data from serial port"""
        try:
            if self.serial_connection.in_waiting > 0:
                line = self.serial_connection.readline().decode('ascii', errors='replace').strip()
                
                if line.startswith('$'):
                    try:
                        msg = pynmea2.parse(line)
                        self.process_nmea_message(msg)
                    except pynmea2.ParseError as e:
                        logger.debug(f"NMEA parse error: {e}")
                        
        except Exception as e:
            logger.error(f"Error reading GPS data: {e}")
    
    def process_nmea_message(self, msg):
        """Process NMEA message"""
        with self.data_lock:
            if isinstance(msg, pynmea2.GGA):
                # Global Positioning System Fix Data
                if msg.latitude and msg.longitude:
                    self.current_position = (float(msg.latitude), float(msg.longitude))
                    self.current_altitude = float(msg.altitude) if msg.altitude else None
                    self.satellites_in_use = int(msg.num_sats) if msg.num_sats else 0
                    self.fix_quality = int(msg.gps_qual) if msg.gps_qual else 0
                    self.hdop = float(msg.horizontal_dil) if msg.horizontal_dil else 99.9
                    self.fix_available = self.fix_quality > 0
                    self.last_update = time.time()
                    
                    # Convert to UTM and local coordinates
                    self.update_coordinate_systems()
                    
                    # Store in database
                    self.store_gps_position()
                    
                    logger.debug(f"🛰️ GPS Fix: {self.current_position}, Alt: {self.current_altitude}, Sats: {self.satellites_in_use}")
            
            elif isinstance(msg, pynmea2.RMC):
                # Recommended Minimum Navigation Information
                if msg.spd_over_grnd:
                    self.current_speed = float(msg.spd_over_grnd) * 0.514444  # Convert knots to m/s
                if msg.true_course:
                    self.current_heading = float(msg.true_course)
            
            elif isinstance(msg, pynmea2.VTG):
                # Track Made Good and Ground Speed
                if msg.spd_over_grnd_kmph:
                    self.current_speed = float(msg.spd_over_grnd_kmph) / 3.6  # Convert km/h to m/s
                if msg.true_track:
                    self.current_heading = float(msg.true_track)
    
    def simulate_gps_data(self):
        """Simulate GPS data for testing"""
        with self.data_lock:
            # Simulate movement around a test area
            base_lat = 40.7128  # New York City coordinates for testing
            base_lon = -74.0060
            
            # Simulate slow movement
            time_offset = time.time() / 100  # Slow movement
            lat_offset = math.sin(time_offset) * 0.001  # ~100m movement
            lon_offset = math.cos(time_offset) * 0.001
            
            self.current_position = (base_lat + lat_offset, base_lon + lon_offset)
            self.current_altitude = 10.0 + math.sin(time_offset) * 2  # Simulate altitude changes
            self.current_speed = 1.5  # 1.5 m/s
            self.current_heading = (time_offset * 10) % 360  # Slowly rotating
            self.satellites_in_use = 8
            self.fix_quality = 1
            self.hdop = 1.2
            self.fix_available = True
            self.last_update = time.time()
            
            # Update coordinate systems
            self.update_coordinate_systems()
            
            # Store in database occasionally
            if int(time.time()) % 10 == 0:  # Every 10 seconds
                self.store_gps_position()
    
    def update_coordinate_systems(self):
        """Update UTM and local coordinate systems"""
        if not self.current_position:
            return
        
        try:
            lat, lon = self.current_position
            
            # Convert to UTM
            utm_x, utm_y, zone_num, zone_letter = utm.from_latlon(lat, lon)
            
            if not self.utm_zone:
                self.utm_zone = zone_num
                self.utm_letter = zone_letter
                self.local_origin = (utm_x, utm_y)
                logger.info(f"🛰️ UTM Zone set to {zone_num}{zone_letter}, Origin: ({utm_x:.2f}, {utm_y:.2f})")
            
            # Calculate local coordinates relative to origin
            if self.local_origin:
                local_x = utm_x - self.local_origin[0]
                local_y = utm_y - self.local_origin[1]
            else:
                local_x = utm_x
                local_y = utm_y
            
            # Store coordinates
            self.utm_coordinates = (utm_x, utm_y)
            self.local_coordinates = (local_x, local_y)
            
            # Add to position history
            self.position_history.append({
                'timestamp': time.time(),
                'lat': lat,
                'lon': lon,
                'utm_x': utm_x,
                'utm_y': utm_y,
                'local_x': local_x,
                'local_y': local_y
            })
            
            # Limit history size
            if len(self.position_history) > self.max_history:
                self.position_history.pop(0)
                
        except Exception as e:
            logger.error(f"Error updating coordinate systems: {e}")
    
    def store_gps_position(self):
        """Store GPS position in database"""
        try:
            if not self.current_position:
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            lat, lon = self.current_position
            utm_x, utm_y = getattr(self, 'utm_coordinates', (None, None))
            local_x, local_y = getattr(self, 'local_coordinates', (None, None))
            
            cursor.execute('''
                INSERT INTO gps_positions 
                (latitude, longitude, altitude, speed, heading, satellites, fix_quality, hdop, utm_x, utm_y, local_x, local_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lat, lon, self.current_altitude, self.current_speed, self.current_heading,
                  self.satellites_in_use, self.fix_quality, self.hdop, utm_x, utm_y, local_x, local_y))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing GPS position: {e}")
    
    def get_current_position(self):
        """Get current GPS position"""
        with self.data_lock:
            return {
                'latitude': self.current_position[0] if self.current_position else None,
                'longitude': self.current_position[1] if self.current_position else None,
                'altitude': self.current_altitude,
                'speed': self.current_speed,
                'heading': self.current_heading,
                'satellites': self.satellites_in_use,
                'fix_quality': self.fix_quality,
                'hdop': self.hdop,
                'fix_available': self.fix_available,
                'last_update': self.last_update,
                'utm_coordinates': getattr(self, 'utm_coordinates', None),
                'local_coordinates': getattr(self, 'local_coordinates', None)
            }
    
    def calculate_distance_to_waypoint(self, waypoint_lat, waypoint_lon):
        """Calculate distance to a GPS waypoint"""
        if not self.current_position:
            return None
        
        try:
            current_point = Point(self.current_position[0], self.current_position[1])
            waypoint_point = Point(waypoint_lat, waypoint_lon)
            
            distance = geodesic(current_point, waypoint_point).meters
            
            # Calculate bearing
            bearing = self.calculate_bearing(
                self.current_position[0], self.current_position[1],
                waypoint_lat, waypoint_lon
            )
            
            return {
                'distance': distance,
                'bearing': bearing
            }
            
        except Exception as e:
            logger.error(f"Error calculating distance to waypoint: {e}")
            return None
    
    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        """Calculate bearing between two GPS coordinates"""
        try:
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lon_rad = math.radians(lon2 - lon1)
            
            y = math.sin(delta_lon_rad) * math.cos(lat2_rad)
            x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
                 math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon_rad))
            
            bearing_rad = math.atan2(y, x)
            bearing_deg = math.degrees(bearing_rad)
            
            # Normalize to 0-360 degrees
            bearing_deg = (bearing_deg + 360) % 360
            
            return bearing_deg
            
        except Exception as e:
            logger.error(f"Error calculating bearing: {e}")
            return 0
    
    def add_gps_waypoint(self, name, latitude, longitude, altitude=None, waypoint_type='mining', priority=1):
        """Add a GPS waypoint"""
        try:
            # Convert to UTM and local coordinates
            utm_x, utm_y, _, _ = utm.from_latlon(latitude, longitude)
            
            local_x = local_y = None
            if self.local_origin:
                local_x = utm_x - self.local_origin[0]
                local_y = utm_y - self.local_origin[1]
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO gps_waypoints 
                (name, latitude, longitude, altitude, utm_x, utm_y, local_x, local_y, type, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, latitude, longitude, altitude, utm_x, utm_y, local_x, local_y, waypoint_type, priority))
            
            waypoint_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"🛰️ GPS waypoint added: {name} at ({latitude}, {longitude})")
            return waypoint_id
            
        except Exception as e:
            logger.error(f"Error adding GPS waypoint: {e}")
            return None
    
    def get_gps_waypoints(self):
        """Get all GPS waypoints"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, latitude, longitude, altitude, utm_x, utm_y, local_x, local_y, 
                       type, status, priority, created_at, completed_at
                FROM gps_waypoints ORDER BY priority DESC, created_at ASC
            ''')
            
            waypoints = []
            for row in cursor.fetchall():
                waypoint = {
                    'id': row[0],
                    'name': row[1],
                    'latitude': row[2],
                    'longitude': row[3],
                    'altitude': row[4],
                    'utm_x': row[5],
                    'utm_y': row[6],
                    'local_x': row[7],
                    'local_y': row[8],
                    'type': row[9],
                    'status': row[10],
                    'priority': row[11],
                    'created_at': row[12],
                    'completed_at': row[13]
                }
                
                # Calculate distance if current position is available
                if self.current_position:
                    distance_info = self.calculate_distance_to_waypoint(row[2], row[3])
                    if distance_info:
                        waypoint.update(distance_info)
                
                waypoints.append(waypoint)
            
            conn.close()
            return waypoints
            
        except Exception as e:
            logger.error(f"Error getting GPS waypoints: {e}")
            return []
    
    def get_position_history(self, limit=100):
        """Get position history"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, latitude, longitude, altitude, speed, heading, utm_x, utm_y, local_x, local_y
                FROM gps_positions ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'latitude': row[1],
                    'longitude': row[2],
                    'altitude': row[3],
                    'speed': row[4],
                    'heading': row[5],
                    'utm_x': row[6],
                    'utm_y': row[7],
                    'local_x': row[8],
                    'local_y': row[9]
                })
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"Error getting position history: {e}")
            return []
    
    def get_gps_status(self):
        """Get GPS module status"""
        with self.data_lock:
            return {
                'gps_available': self.gps_available,
                'fix_available': self.fix_available,
                'current_position': self.current_position,
                'altitude': self.current_altitude,
                'speed': self.current_speed,
                'heading': self.current_heading,
                'satellites': self.satellites_in_use,
                'fix_quality': self.fix_quality,
                'hdop': self.hdop,
                'last_update': self.last_update,
                'utm_zone': f"{self.utm_zone}{self.utm_letter}" if self.utm_zone else None,
                'local_origin': self.local_origin
            }

class GPSNavigator:
    def __init__(self, gps_module):
        self.gps_module = gps_module
        self.current_waypoint = None
        self.navigation_tolerance = 5.0  # 5 meters
        
    def navigate_to_gps_waypoint(self, waypoint):
        """Navigate to a GPS waypoint"""
        self.current_waypoint = waypoint
        
        while self.current_waypoint:
            current_pos = self.gps_module.get_current_position()
            
            if not current_pos['fix_available']:
                logger.warning("🛰️ No GPS fix available for navigation")
                time.sleep(1)
                continue
            
            # Calculate distance and bearing to waypoint
            distance_info = self.gps_module.calculate_distance_to_waypoint(
                waypoint['latitude'], waypoint['longitude']
            )
            
            if not distance_info:
                logger.error("🛰️ Could not calculate distance to waypoint")
                break
            
            distance = distance_info['distance']
            bearing = distance_info['bearing']
            
            logger.info(f"🛰️ Distance to {waypoint['name']}: {distance:.1f}m, Bearing: {bearing:.1f}°")
            
            # Check if we've reached the waypoint
            if distance <= self.navigation_tolerance:
                logger.info(f"🛰️ Reached GPS waypoint: {waypoint['name']}")
                self.mark_waypoint_completed(waypoint['id'])
                self.current_waypoint = None
                return True
            
            # Calculate navigation command
            current_heading = current_pos['heading'] or 0
            heading_error = bearing - current_heading
            
            # Normalize heading error to [-180, 180]
            while heading_error > 180:
                heading_error -= 360
            while heading_error < -180:
                heading_error += 360
            
            # Generate navigation command
            if abs(heading_error) > 10:  # Need to turn
                if heading_error > 0:
                    nav_command = 'turn_left'
                else:
                    nav_command = 'turn_right'
            else:
                nav_command = 'move_forward'
            
            logger.info(f"🛰️ Navigation command: {nav_command} (heading error: {heading_error:.1f}°)")
            
            # This would be sent to the vehicle controller
            # For now, just simulate movement
            time.sleep(1)
        
        return False
    
    def mark_waypoint_completed(self, waypoint_id):
        """Mark GPS waypoint as completed"""
        try:
            conn = sqlite3.connect(self.gps_module.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE gps_waypoints 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (waypoint_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"🛰️ GPS waypoint {waypoint_id} marked as completed")
            
        except Exception as e:
            logger.error(f"Error marking GPS waypoint completed: {e}")

def main():
    """Test GPS module"""
    gps = GPSModule()
    
    try:
        gps.start_gps()
        
        # Run for 30 seconds
        for i in range(30):
            status = gps.get_gps_status()
            print(f"GPS Status: {status}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping GPS module...")
    finally:
        gps.stop_gps()

if __name__ == "__main__":
    main()
