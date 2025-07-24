#!/usr/bin/env python3
"""
SmartRover Safety Protocols Module
Implements comprehensive safety systems for autonomous mining operations
"""

import time
import threading
import logging
import json
import sqlite3
import math
import numpy as np
from datetime import datetime, timedelta
from collections import deque
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/safety.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SafetyMonitor:
    def __init__(self, vehicle_controller=None, database_path='/var/lib/smartrover/mining_data.db'):
        self.vehicle_controller = vehicle_controller
        self.database_path = database_path
        
        # Safety states
        self.safety_status = 'NORMAL'  # NORMAL, WARNING, CRITICAL, EMERGENCY
        self.emergency_stop_active = False
        self.safety_violations = []
        
        # Monitoring parameters
        self.max_speed = 2.0  # m/s
        self.max_acceleration = 1.5  # m/s²
        self.min_obstacle_distance = 30.0  # cm
        self.max_slope_angle = 25.0  # degrees
        self.max_temperature = 80.0  # °C
        self.min_battery_voltage = 10.5  # V
        self.max_operation_time = 8 * 3600  # 8 hours in seconds
        
        # Monitoring history
        self.speed_history = deque(maxlen=100)
        self.temperature_history = deque(maxlen=100)
        self.obstacle_history = deque(maxlen=50)
        self.violation_history = deque(maxlen=1000)
        
        # Threading
        self.running = False
        self.monitor_thread = None
        self.check_interval = 0.5  # 2 Hz monitoring
        
        # Safety zones (geofencing)
        self.safe_zones = []
        self.restricted_zones = []
        
        # Emergency contacts/systems
        self.emergency_callbacks = []
        
        # Initialize safety database
        self.init_safety_database()
        
        logger.info("🛡️ Safety monitor initialized")
    
    def init_safety_database(self):
        """Initialize safety monitoring database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Safety events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS safety_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    sensor_data TEXT,
                    vehicle_state TEXT,
                    action_taken TEXT,
                    resolved_at TIMESTAMP NULL
                )
            ''')
            
            # Safety zones table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS safety_zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    zone_type TEXT NOT NULL,
                    coordinates TEXT NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Safety configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS safety_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parameter_name TEXT UNIQUE NOT NULL,
                    parameter_value REAL NOT NULL,
                    unit TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default safety parameters
            default_params = [
                ('max_speed', self.max_speed, 'm/s', 'Maximum allowed vehicle speed'),
                ('max_acceleration', self.max_acceleration, 'm/s²', 'Maximum allowed acceleration'),
                ('min_obstacle_distance', self.min_obstacle_distance, 'cm', 'Minimum safe distance to obstacles'),
                ('max_slope_angle', self.max_slope_angle, 'degrees', 'Maximum allowed slope angle'),
                ('max_temperature', self.max_temperature, '°C', 'Maximum operating temperature'),
                ('min_battery_voltage', self.min_battery_voltage, 'V', 'Minimum battery voltage'),
                ('max_operation_time', self.max_operation_time, 'seconds', 'Maximum continuous operation time')
            ]
            
            for param in default_params:
                cursor.execute('''
                    INSERT OR IGNORE INTO safety_config (parameter_name, parameter_value, unit, description)
                    VALUES (?, ?, ?, ?)
                ''', param)
            
            conn.commit()
            conn.close()
            
            logger.info("🛡️ Safety database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing safety database: {e}")
    
    def start_monitoring(self):
        """Start safety monitoring"""
        logger.info("🛡️ Starting safety monitoring...")
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True, name="SafetyMonitor")
        self.monitor_thread.start()
        
        logger.info("🛡️ Safety monitoring started")
    
    def stop_monitoring(self):
        """Stop safety monitoring"""
        logger.info("🛡️ Stopping safety monitoring...")
        
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        
        logger.info("🛡️ Safety monitoring stopped")
    
    def monitor_loop(self):
        """Main safety monitoring loop"""
        logger.info("🛡️ Safety monitoring loop started")
        
        while self.running:
            try:
                # Perform all safety checks
                self.check_vehicle_speed()
                self.check_obstacle_proximity()
                self.check_system_temperature()
                self.check_battery_voltage()
                self.check_operation_time()
                self.check_vehicle_stability()
                self.check_geofencing()
                self.check_communication()
                
                # Update safety status
                self.update_safety_status()
                
                # Handle emergency conditions
                if self.safety_status == 'EMERGENCY':
                    self.handle_emergency()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in safety monitoring loop: {e}")
                time.sleep(1)
        
        logger.info("🛡️ Safety monitoring loop stopped")
    
    def check_vehicle_speed(self):
        """Check vehicle speed safety"""
        try:
            if not self.vehicle_controller:
                return
            
            # Get current speed
            current_speed = getattr(self.vehicle_controller, 'current_speed', 0)
            self.speed_history.append({
                'timestamp': time.time(),
                'speed': current_speed
            })
            
            # Check maximum speed
            if current_speed > self.max_speed:
                self.log_safety_violation(
                    'SPEED_EXCEEDED',
                    'CRITICAL',
                    f'Vehicle speed {current_speed:.2f} m/s exceeds maximum {self.max_speed} m/s',
                    {'current_speed': current_speed, 'max_speed': self.max_speed}
                )
            
            # Check acceleration
            if len(self.speed_history) >= 2:
                prev_speed = self.speed_history[-2]['speed']
                time_diff = self.speed_history[-1]['timestamp'] - self.speed_history[-2]['timestamp']
                
                if time_diff > 0:
                    acceleration = abs(current_speed - prev_speed) / time_diff
                    
                    if acceleration > self.max_acceleration:
                        self.log_safety_violation(
                            'ACCELERATION_EXCEEDED',
                            'WARNING',
                            f'Vehicle acceleration {acceleration:.2f} m/s² exceeds maximum {self.max_acceleration} m/s²',
                            {'acceleration': acceleration, 'max_acceleration': self.max_acceleration}
                        )
            
        except Exception as e:
            logger.error(f"Error checking vehicle speed: {e}")
    
    def check_obstacle_proximity(self):
        """Check obstacle proximity safety"""
        try:
            if not self.vehicle_controller or not self.vehicle_controller.sensor_array:
                return
            
            # Get ultrasonic sensor readings
            sensor_readings = self.vehicle_controller.sensor_array.read_all_sensors()
            
            self.obstacle_history.append({
                'timestamp': time.time(),
                'sensors': sensor_readings
            })
            
            # Check minimum distance to obstacles
            min_distance = min(sensor_readings)
            
            if min_distance < self.min_obstacle_distance:
                severity = 'CRITICAL' if min_distance < self.min_obstacle_distance / 2 else 'WARNING'
                
                self.log_safety_violation(
                    'OBSTACLE_TOO_CLOSE',
                    severity,
                    f'Obstacle detected at {min_distance:.1f} cm, minimum safe distance is {self.min_obstacle_distance} cm',
                    {'min_distance': min_distance, 'sensor_readings': sensor_readings}
                )
                
                # Automatic emergency stop if very close
                if min_distance < self.min_obstacle_distance / 3:
                    self.trigger_emergency_stop('Obstacle too close - automatic emergency stop')
            
        except Exception as e:
            logger.error(f"Error checking obstacle proximity: {e}")
    
    def check_system_temperature(self):
        """Check system temperature safety"""
        try:
            # Get CPU temperature
            temperature = self.get_cpu_temperature()
            
            if temperature is not None:
                self.temperature_history.append({
                    'timestamp': time.time(),
                    'temperature': temperature
                })
                
                if temperature > self.max_temperature:
                    severity = 'CRITICAL' if temperature > self.max_temperature + 10 else 'WARNING'
                    
                    self.log_safety_violation(
                        'TEMPERATURE_HIGH',
                        severity,
                        f'System temperature {temperature:.1f}°C exceeds maximum {self.max_temperature}°C',
                        {'temperature': temperature, 'max_temperature': self.max_temperature}
                    )
                    
                    # Automatic shutdown if critically high
                    if temperature > self.max_temperature + 15:
                        self.trigger_emergency_stop('System overheating - automatic shutdown')
            
        except Exception as e:
            logger.error(f"Error checking system temperature: {e}")
    
    def check_battery_voltage(self):
        """Check battery voltage safety"""
        try:
            # Simulate battery voltage reading (would be from ADC in real implementation)
            import random
            battery_voltage = 12.0 + random.uniform(-1.0, 1.0)  # Simulate voltage variation
            
            if battery_voltage < self.min_battery_voltage:
                severity = 'CRITICAL' if battery_voltage < self.min_battery_voltage - 0.5 else 'WARNING'
                
                self.log_safety_violation(
                    'BATTERY_LOW',
                    severity,
                    f'Battery voltage {battery_voltage:.2f}V below minimum {self.min_battery_voltage}V',
                    {'battery_voltage': battery_voltage, 'min_voltage': self.min_battery_voltage}
                )
                
                # Automatic return to dock if critically low
                if battery_voltage < self.min_battery_voltage - 1.0:
                    if self.vehicle_controller and not self.vehicle_controller.returning_to_dock:
                        self.vehicle_controller.return_to_dock()
                        logger.critical("🛡️ Low battery - automatically returning to dock")
            
        except Exception as e:
            logger.error(f"Error checking battery voltage: {e}")
    
    def check_operation_time(self):
        """Check continuous operation time safety"""
        try:
            if not self.vehicle_controller:
                return
            
            # Check if vehicle has been running too long
            if hasattr(self.vehicle_controller, 'start_time'):
                operation_time = time.time() - self.vehicle_controller.start_time
                
                if operation_time > self.max_operation_time:
                    self.log_safety_violation(
                        'OPERATION_TIME_EXCEEDED',
                        'WARNING',
                        f'Continuous operation time {operation_time/3600:.1f}h exceeds maximum {self.max_operation_time/3600:.1f}h',
                        {'operation_time': operation_time, 'max_time': self.max_operation_time}
                    )
                    
                    # Suggest maintenance break
                    if operation_time > self.max_operation_time * 1.2:
                        logger.warning("🛡️ Vehicle requires maintenance break")
            
        except Exception as e:
            logger.error(f"Error checking operation time: {e}")
    
    def check_vehicle_stability(self):
        """Check vehicle stability (tilt, vibration)"""
        try:
            # Simulate IMU data (would be from actual IMU in real implementation)
            import random
            
            # Simulate tilt angles
            roll = random.uniform(-5, 5)  # degrees
            pitch = random.uniform(-5, 5)  # degrees
            
            # Check slope angle
            slope_angle = math.sqrt(roll**2 + pitch**2)
            
            if slope_angle > self.max_slope_angle:
                severity = 'CRITICAL' if slope_angle > self.max_slope_angle * 1.5 else 'WARNING'
                
                self.log_safety_violation(
                    'SLOPE_TOO_STEEP',
                    severity,
                    f'Vehicle on slope of {slope_angle:.1f}°, maximum safe angle is {self.max_slope_angle}°',
                    {'slope_angle': slope_angle, 'roll': roll, 'pitch': pitch}
                )
                
                # Emergency stop if critically steep
                if slope_angle > self.max_slope_angle * 2:
                    self.trigger_emergency_stop('Slope too steep - risk of rollover')
            
        except Exception as e:
            logger.error(f"Error checking vehicle stability: {e}")
    
    def check_geofencing(self):
        """Check geofencing safety"""
        try:
            if not self.vehicle_controller:
                return
            
            current_position = getattr(self.vehicle_controller.slam_mapper, 'robot_position', [0, 0])
            
            # Check if vehicle is in restricted zones
            for zone in self.restricted_zones:
                if self.is_point_in_zone(current_position, zone):
                    self.log_safety_violation(
                        'RESTRICTED_ZONE_ENTRY',
                        'CRITICAL',
                        f'Vehicle entered restricted zone: {zone["name"]}',
                        {'position': current_position, 'zone': zone['name']}
                    )
                    
                    # Automatic stop and return
                    self.trigger_emergency_stop(f'Entered restricted zone: {zone["name"]}')
            
            # Check if vehicle is outside safe zones
            if self.safe_zones:
                in_safe_zone = any(self.is_point_in_zone(current_position, zone) for zone in self.safe_zones)
                
                if not in_safe_zone:
                    self.log_safety_violation(
                        'OUTSIDE_SAFE_ZONE',
                        'WARNING',
                        'Vehicle is outside designated safe zones',
                        {'position': current_position}
                    )
            
        except Exception as e:
            logger.error(f"Error checking geofencing: {e}")
    
    def check_communication(self):
        """Check communication safety"""
        try:
            # Check if vehicle controller is responsive
            if self.vehicle_controller:
                last_update = getattr(self.vehicle_controller, 'last_update_time', time.time())
                time_since_update = time.time() - last_update
                
                if time_since_update > 5.0:  # 5 seconds without update
                    self.log_safety_violation(
                        'COMMUNICATION_LOSS',
                        'CRITICAL',
                        f'No communication with vehicle controller for {time_since_update:.1f} seconds',
                        {'time_since_update': time_since_update}
                    )
                    
                    # Emergency stop if communication lost for too long
                    if time_since_update > 10.0:
                        self.trigger_emergency_stop('Communication loss - safety protocol activated')
            
        except Exception as e:
            logger.error(f"Error checking communication: {e}")
    
    def is_point_in_zone(self, point, zone):
        """Check if point is inside a safety zone"""
        try:
            # Simple rectangular zone check (can be extended for complex polygons)
            x, y = point
            coords = zone.get('coordinates', {})
            
            if 'min_x' in coords and 'max_x' in coords and 'min_y' in coords and 'max_y' in coords:
                return (coords['min_x'] <= x <= coords['max_x'] and 
                       coords['min_y'] <= y <= coords['max_y'])
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking point in zone: {e}")
            return False
    
    def update_safety_status(self):
        """Update overall safety status"""
        try:
            # Count recent violations by severity
            current_time = time.time()
            recent_violations = [v for v in self.violation_history 
                               if current_time - v['timestamp'] < 60]  # Last minute
            
            critical_count = sum(1 for v in recent_violations if v['severity'] == 'CRITICAL')
            warning_count = sum(1 for v in recent_violations if v['severity'] == 'WARNING')
            
            # Determine safety status
            if self.emergency_stop_active:
                new_status = 'EMERGENCY'
            elif critical_count > 0:
                new_status = 'CRITICAL'
            elif warning_count > 3:  # Multiple warnings
                new_status = 'WARNING'
            else:
                new_status = 'NORMAL'
            
            # Log status changes
            if new_status != self.safety_status:
                logger.info(f"🛡️ Safety status changed: {self.safety_status} -> {new_status}")
                self.safety_status = new_status
                
                # Notify emergency callbacks
                for callback in self.emergency_callbacks:
                    try:
                        callback(new_status, recent_violations)
                    except Exception as e:
                        logger.error(f"Error calling emergency callback: {e}")
            
        except Exception as e:
            logger.error(f"Error updating safety status: {e}")
    
    def log_safety_violation(self, event_type, severity, description, sensor_data=None):
        """Log a safety violation"""
        try:
            violation = {
                'timestamp': time.time(),
                'event_type': event_type,
                'severity': severity,
                'description': description,
                'sensor_data': sensor_data or {}
            }
            
            self.violation_history.append(violation)
            
            # Log to database
            conn = sqlite3.connect(self.database_path)
            cursor
