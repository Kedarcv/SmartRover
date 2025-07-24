#!/usr/bin/env python3
"""
SmartRover Real-time Data Streaming Module
Handles WebSocket-based real-time sensor data streaming and live updates
"""

import asyncio
import websockets
import json
import time
import threading
import logging
import queue
import numpy as np
from datetime import datetime
import sqlite3
import cv2
import base64
from collections import deque
import psutil
import platform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/streaming.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataStreamManager:
    def __init__(self, vehicle_controller=None, database_path='/var/lib/smartrover/mining_data.db'):
        self.vehicle_controller = vehicle_controller
        self.database_path = database_path
        
        # WebSocket connections
        self.websocket_clients = set()
        self.client_subscriptions = {}  # client -> set of data types
        
        # Data queues for different stream types
        self.sensor_queue = queue.Queue(maxsize=100)
        self.video_queue = queue.Queue(maxsize=10)
        self.system_queue = queue.Queue(maxsize=50)
        self.gps_queue = queue.Queue(maxsize=100)
        self.mining_queue = queue.Queue(maxsize=50)
        
        # Stream configuration
        self.stream_rates = {
            'sensors': 10,  # 10 Hz
            'video': 5,     # 5 FPS
            'system': 1,    # 1 Hz
            'gps': 2,       # 2 Hz
            'mining': 2     # 2 Hz
        }
        
        # Data buffers for historical data
        self.sensor_buffer = deque(maxlen=1000)
        self.system_buffer = deque(maxlen=300)
        self.gps_buffer = deque(maxlen=600)
        
        # Threading
        self.running = False
        self.data_threads = {}
        
        # Statistics
        self.stream_stats = {
            'total_messages_sent': 0,
            'total_bytes_sent': 0,
            'connected_clients': 0,
            'start_time': time.time()
        }
        
        logger.info("📡 Data stream manager initialized")
    
    def start_streaming(self):
        """Start all data streaming threads"""
        logger.info("📡 Starting real-time data streaming...")
        
        self.running = True
        
        # Start data collection threads
        self.data_threads['sensors'] = threading.Thread(
            target=self.sensor_data_thread, daemon=True, name="SensorStream"
        )
        self.data_threads['video'] = threading.Thread(
            target=self.video_data_thread, daemon=True, name="VideoStream"
        )
        self.data_threads['system'] = threading.Thread(
            target=self.system_data_thread, daemon=True, name="SystemStream"
        )
        self.data_threads['gps'] = threading.Thread(
            target=self.gps_data_thread, daemon=True, name="GPSStream"
        )
        self.data_threads['mining'] = threading.Thread(
            target=self.mining_data_thread, daemon=True, name="MiningStream"
        )
        
        # Start all threads
        for thread in self.data_threads.values():
            thread.start()
        
        logger.info("📡 All streaming threads started")
    
    def stop_streaming(self):
        """Stop all streaming threads"""
        logger.info("📡 Stopping data streaming...")
        
        self.running = False
        
        # Wait for threads to finish
        for thread in self.data_threads.values():
            if thread.is_alive():
                thread.join(timeout=2)
        
        logger.info("📡 Data streaming stopped")
    
    def sensor_data_thread(self):
        """Thread for collecting sensor data"""
        logger.info("📡 Sensor data thread started")
        
        while self.running:
            try:
                if self.vehicle_controller:
                    # Get sensor data from vehicle controller
                    sensor_data = {
                        'timestamp': time.time(),
                        'type': 'sensors',
                        'data': {
                            'ultrasonic': getattr(self.vehicle_controller.sensor_array, 'read_all_sensors', lambda: [0, 0, 0, 0])(),
                            'camera_available': getattr(self.vehicle_controller, 'camera_available', False),
                            'position': getattr(self.vehicle_controller.slam_mapper, 'robot_position', [0, 0]),
                            'heading': getattr(self.vehicle_controller.slam_mapper, 'robot_heading', 0),
                            'speed': getattr(self.vehicle_controller, 'current_speed', 0),
                            'battery_voltage': self.get_battery_voltage(),
                            'temperature': self.get_system_temperature(),
                            'obstacle_detected': False  # Will be updated by AI
                        }
                    }
                    
                    # Add to buffer
                    self.sensor_buffer.append(sensor_data)
                    
                    # Add to queue for streaming
                    try:
                        self.sensor_queue.put_nowait(sensor_data)
                    except queue.Full:
                        # Remove oldest item and add new one
                        try:
                            self.sensor_queue.get_nowait()
                            self.sensor_queue.put_nowait(sensor_data)
                        except queue.Empty:
                            pass
                
                time.sleep(1.0 / self.stream_rates['sensors'])
                
            except Exception as e:
                logger.error(f"Error in sensor data thread: {e}")
                time.sleep(1)
        
        logger.info("📡 Sensor data thread stopped")
    
    def video_data_thread(self):
        """Thread for collecting video data"""
        logger.info("📡 Video data thread started")
        
        camera = None
        try:
            # Try to initialize camera
            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                logger.warning("📡 Camera not available for video streaming")
                camera = None
        except Exception as e:
            logger.warning(f"📡 Camera initialization failed: {e}")
            camera = None
        
        while self.running:
            try:
                video_data = {
                    'timestamp': time.time(),
                    'type': 'video',
                    'data': {
                        'frame': None,
                        'resolution': None,
                        'fps': self.stream_rates['video'],
                        'available': camera is not None
                    }
                }
                
                if camera and camera.isOpened():
                    ret, frame = camera.read()
                    if ret:
                        # Resize frame for streaming
                        frame = cv2.resize(frame, (320, 240))
                        
                        # Encode frame as JPEG
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        
                        # Convert to base64
                        frame_b64 = base64.b64encode(buffer).decode('utf-8')
                        
                        video_data['data']['frame'] = frame_b64
                        video_data['data']['resolution'] = [320, 240]
                
                # Add to queue
                try:
                    self.video_queue.put_nowait(video_data)
                except queue.Full:
                    try:
                        self.video_queue.get_nowait()
                        self.video_queue.put_nowait(video_data)
                    except queue.Empty:
                        pass
                
                time.sleep(1.0 / self.stream_rates['video'])
                
            except Exception as e:
                logger.error(f"Error in video data thread: {e}")
                time.sleep(1)
        
        if camera:
            camera.release()
        
        logger.info("📡 Video data thread stopped")
    
    def system_data_thread(self):
        """Thread for collecting system data"""
        logger.info("📡 System data thread started")
        
        while self.running:
            try:
                system_data = {
                    'timestamp': time.time(),
                    'type': 'system',
                    'data': {
                        'cpu_percent': psutil.cpu_percent(),
                        'memory_percent': psutil.virtual_memory().percent,
                        'disk_percent': psutil.disk_usage('/').percent,
                        'temperature': self.get_cpu_temperature(),
                        'uptime': time.time() - psutil.boot_time(),
                        'network_stats': self.get_network_stats(),
                        'vehicle_status': {
                            'running': getattr(self.vehicle_controller, 'running', False) if self.vehicle_controller else False,
                            'mining_active': getattr(self.vehicle_controller, 'mining_active', False) if self.vehicle_controller else False,
                            'returning_to_dock': getattr(self.vehicle_controller, 'returning_to_dock', False) if self.vehicle_controller else False
                        },
                        'connectivity': {
                            'wifi_connected': True,  # Assume connected if streaming
                            'bluetooth_connected': False,  # Would be updated by Bluetooth module
                            'gps_available': False  # Would be updated by GPS module
                        }
                    }
                }
                
                # Add to buffer
                self.system_buffer.append(system_data)
                
                # Add to queue
                try:
                    self.system_queue.put_nowait(system_data)
                except queue.Full:
                    try:
                        self.system_queue.get_nowait()
                        self.system_queue.put_nowait(system_data)
                    except queue.Empty:
                        pass
                
                time.sleep(1.0 / self.stream_rates['system'])
                
            except Exception as e:
                logger.error(f"Error in system data thread: {e}")
                time.sleep(1)
        
        logger.info("📡 System data thread stopped")
    
    def gps_data_thread(self):
        """Thread for collecting GPS data"""
        logger.info("📡 GPS data thread started")
        
        while self.running:
            try:
                # Simulate GPS data (would be replaced with real GPS module)
                gps_data = {
                    'timestamp': time.time(),
                    'type': 'gps',
                    'data': {
                        'latitude': None,
                        'longitude': None,
                        'altitude': None,
                        'speed': None,
                        'heading': None,
                        'satellites': 0,
                        'fix_quality': 0,
                        'hdop': 99.9,
                        'fix_available': False,
                        'utm_coordinates': None,
                        'local_coordinates': None
                    }
                }
                
                # Add to buffer
                self.gps_buffer.append(gps_data)
                
                # Add to queue
                try:
                    self.gps_queue.put_nowait(gps_data)
                except queue.Full:
                    try:
                        self.gps_queue.get_nowait()
                        self.gps_queue.put_nowait(gps_data)
                    except queue.Empty:
                        pass
                
                time.sleep(1.0 / self.stream_rates['gps'])
                
            except Exception as e:
                logger.error(f"Error in GPS data thread: {e}")
                time.sleep(1)
        
        logger.info("📡 GPS data thread stopped")
    
    def mining_data_thread(self):
        """Thread for collecting mining operation data"""
        logger.info("📡 Mining data thread started")
        
        while self.running:
            try:
                mining_data = {
                    'timestamp': time.time(),
                    'type': 'mining',
                    'data': {
                        'active': getattr(self.vehicle_controller, 'mining_active', False) if self.vehicle_controller else False,
                        'current_waypoint': getattr(self.vehicle_controller.waypoint_navigator, 'current_waypoint', None) if self.vehicle_controller else None,
                        'waypoints_completed': getattr(self.vehicle_controller, 'waypoints_completed', 0) if self.vehicle_controller else 0,
                        'minerals_collected': getattr(self.vehicle_controller, 'minerals_collected', 0) if self.vehicle_controller else 0,
                        'total_distance': getattr(self.vehicle_controller.slam_mapper, 'total_distance', 0) if self.vehicle_controller else 0,
                        'session_id': getattr(self.vehicle_controller, 'current_session_id', None) if self.vehicle_controller else None,
                        'returning_to_dock': getattr(self.vehicle_controller, 'returning_to_dock', False) if self.vehicle_controller else False,
                        'path_data': self.get_current_path_data()
                    }
                }
                
                # Add to queue
                try:
                    self.mining_queue.put_nowait(mining_data)
                except queue.Full:
                    try:
                        self.mining_queue.get_nowait()
                        self.mining_queue.put_nowait(mining_data)
                    except queue.Empty:
                        pass
                
                time.sleep(1.0 / self.stream_rates['mining'])
                
            except Exception as e:
                logger.error(f"Error in mining data thread: {e}")
                time.sleep(1)
        
        logger.info("📡 Mining data thread stopped")
    
    def get_battery_voltage(self):
        """Get battery voltage (simulated)"""
        # In real implementation, this would read from ADC
        import random
        return round(12.0 + random.uniform(-0.5, 0.5), 2)
    
    def get_system_temperature(self):
        """Get system temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
                return round(temp, 1)
        except:
            return None
    
    def get_cpu_temperature(self):
        """Get CPU temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
                return round(temp, 1)
        except:
            return None
    
    def get_network_stats(self):
        """Get network statistics"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except:
            return None
    
    def get_current_path_data(self):
        """Get current path planning data"""
        if not self.vehicle_controller:
            return None
        
        try:
            # Get path from SLAM mapper
            path_history = getattr(self.vehicle_controller.slam_mapper, 'path_history', [])
            obstacles = getattr(self.vehicle_controller.slam_mapper, 'obstacles', [])
            
            return {
                'path_history': list(path_history)[-50:],  # Last 50 points
                'obstacles': obstacles[-20:],  # Last 20 obstacles
                'current_position': getattr(self.vehicle_controller.slam_mapper, 'robot_position', [0, 0]),
                'heading': getattr(self.vehicle_controller.slam_mapper, 'robot_heading', 0)
            }
        except:
            return None
    
    async def handle_websocket_client(self, websocket, path):
        """Handle WebSocket client connection"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"📡 WebSocket client connected: {client_id}")
        
        self.websocket_clients.add(websocket)
        self.client_subscriptions[websocket] = set()
        self.stream_stats['connected_clients'] = len(self.websocket_clients)
        
        try:
            # Send welcome message
            welcome_msg = {
                'type': 'welcome',
                'timestamp': time.time(),
                'message': 'Connected to SmartRover Real-time Data Stream',
                'available_streams': list(self.stream_rates.keys()),
                'stream_rates': self.stream_rates,
                'server_stats': self.get_stream_stats()
            }
            await websocket.send(json.dumps(welcome_msg))
            
            # Handle client messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    error_msg = {
                        'type': 'error',
                        'timestamp': time.time(),
                        'message': 'Invalid JSON format'
                    }
                    await websocket.send(json.dumps(error_msg))
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"📡 WebSocket client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"📡 WebSocket error for client {client_id}: {e}")
        finally:
            # Cleanup
            self.websocket_clients.discard(websocket)
            self.client_subscriptions.pop(websocket, None)
            self.stream_stats['connected_clients'] = len(self.websocket_clients)
    
    async def handle_client_message(self, websocket, data):
        """Handle message from WebSocket client"""
        msg_type = data.get('type', 'unknown')
        
        if msg_type == 'subscribe':
            # Subscribe to data streams
            streams = data.get('streams', [])
            for stream in streams:
                if stream in self.stream_rates:
                    self.client_subscriptions[websocket].add(stream)
            
            response = {
                'type': 'subscription_updated',
                'timestamp': time.time(),
                'subscribed_streams': list(self.client_subscriptions[websocket])
            }
            await websocket.send(json.dumps(response))
            
        elif msg_type == 'unsubscribe':
            # Unsubscribe from data streams
            streams = data.get('streams', [])
            for stream in streams:
                self.client_subscriptions[websocket].discard(stream)
            
            response = {
                'type': 'subscription_updated',
                'timestamp': time.time(),
                'subscribed_streams': list(self.client_subscriptions[websocket])
            }
            await websocket.send(json.dumps(response))
            
        elif msg_type == 'get_historical':
            # Send historical data
            stream_type = data.get('stream', 'sensors')
            limit = min(data.get('limit', 100), 1000)  # Max 1000 points
            
            historical_data = self.get_historical_data(stream_type, limit)
            
            response = {
                'type': 'historical_data',
                'timestamp': time.time(),
                'stream': stream_type,
                'data': historical_data
            }
            await websocket.send(json.dumps(response))
            
        elif msg_type == 'ping':
            # Respond to ping
            response = {
                'type': 'pong',
                'timestamp': time.time(),
                'server_time': time.time()
            }
            await websocket.send(json.dumps(response))
            
        elif msg_type == 'get_stats':
            # Send streaming statistics
            response = {
                'type': 'stats',
                'timestamp': time.time(),
                'data': self.get_stream_stats()
            }
            await websocket.send(json.dumps(response))
    
    def get_historical_data(self, stream_type, limit):
        """Get historical data for a stream type"""
        if stream_type == 'sensors':
            return list(self.sensor_buffer)[-limit:]
        elif stream_type == 'system':
            return list(self.system_buffer)[-limit:]
        elif stream_type == 'gps':
            return list(self.gps_buffer)[-limit:]
        else:
            return []
    
    def get_stream_stats(self):
        """Get streaming statistics"""
        uptime = time.time() - self.stream_stats['start_time']
        
        return {
            'connected_clients': self.stream_stats['connected_clients'],
            'total_messages_sent': self.stream_stats['total_messages_sent'],
            'total_bytes_sent': self.stream_stats['total_bytes_sent'],
            'uptime_seconds': uptime,
            'messages_per_second': self.stream_stats['total_messages_sent'] / max(uptime, 1),
            'bytes_per_second': self.stream_stats['total_bytes_sent'] / max(uptime, 1),
            'queue_sizes': {
                'sensors': self.sensor_queue.qsize(),
                'video': self.video_queue.qsize(),
                'system': self.system_queue.qsize(),
                'gps': self.gps_queue.qsize(),
                'mining': self.mining_queue.qsize()
            }
        }
    
    async def broadcast_data(self):
        """Broadcast data to all connected WebSocket clients"""
        logger.info("📡 Starting data broadcast loop")
        
        while self.running:
            try:
                # Collect data from all queues
                data_to_send = {}
                
                # Get sensor data
                try:
                    while not self.sensor_queue.empty():
                        data_to_send['sensors'] = self.sensor_queue.get_nowait()
                except queue.Empty:
                    pass
                
                # Get video data
                try:
                    while not self.video_queue.empty():
                        data_to_send['video'] = self.video_queue.get_nowait()
                except queue.Empty:
                    pass
                
                # Get system data
                try:
                    while not self.system_queue.empty():
                        data_to_send['system'] = self.system_queue.get_nowait()
                except queue.Empty:
                    pass
                
                # Get GPS data
                try:
                    while not self.gps_queue.empty():
                        data_to_send['gps'] = self.gps_queue.get_nowait()
                except queue.Empty:
                    pass
                
                # Get mining data
                try:
                    while not self.mining_queue.empty():
                        data_to_send['mining'] = self.mining_queue.get_nowait()
                except queue.Empty:
                    pass
                
                # Send data to subscribed clients
                if data_to_send and self.websocket_clients:
                    disconnected_clients = set()
                    
                    for websocket in self.websocket_clients.copy():
                        try:
                            client_data = {}
                            subscriptions = self.client_subscriptions.get(websocket, set())
                            
                            # Only send subscribed data types
                            for stream_type, data in data_to_send.items():
                                if stream_type in subscriptions:
                                    client_data[stream_type] = data
                            
                            if client_data:
                                message = {
                                    'type': 'stream_data',
                                    'timestamp': time.time(),
                                    'data': client_data
                                }
                                
                                message_json = json.dumps(message)
                                await websocket.send(message_json)
                                
                                # Update statistics
                                self.stream_stats['total_messages_sent'] += 1
                                self.stream_stats['total_bytes_sent'] += len(message_json)
                                
                        except websockets.exceptions.ConnectionClosed:
                            disconnected_clients.add(websocket)
                        except Exception as e:
                            logger.error(f"📡 Error sending data to client: {e}")
                            disconnected_clients.add(websocket)
                    
                    # Remove disconnected clients
                    for websocket in disconnected_clients:
                        self.websocket_clients.discard(websocket)
                        self.client_subscriptions.pop(websocket, None)
                    
                    if disconnected_clients:
                        self.stream_stats['connected_clients'] = len(self.websocket_clients)
                
                # Control broadcast rate
                await asyncio.sleep(0.1)  # 10 Hz broadcast rate
                
            except Exception as e:
                logger.error(f"📡 Error in broadcast loop: {e}")
                await asyncio.sleep(1)
        
        logger.info("📡 Data broadcast loop stopped")
    
    async def start_websocket_server(self, host='0.0.0.0', port=8765):
        """Start WebSocket server"""
        logger.info(f"📡 Starting WebSocket server on {host}:{port}")
        
        # Start data streaming threads
        self.start_streaming()
        
        # Start WebSocket server
        server = await websockets.serve(
            self.handle_websocket_client,
            host,
            port,
            ping_interval=30,
            ping_timeout=10,
            max_size=1024*1024  # 1MB max message size
        )
        
        # Start broadcast task
        broadcast_task = asyncio.create_task(self.broadcast_data())
        
        logger.info(f"📡 WebSocket server started on ws://{host}:{port}")
        
        try:
            await server.wait_closed()
        finally:
            broadcast_task.cancel()
            self.stop_streaming()

class StreamingAPI:
    def __init__(self, stream_manager):
        self.stream_manager = stream_manager
    
    def get_current_data(self, stream_type='all'):
        """Get current data for API endpoints"""
        if stream_type == 'all':
            return {
                'sensors': self.get_latest_from_buffer(self.stream_manager.sensor_buffer),
                'system': self.get_latest_from_buffer(self.stream_manager.system_buffer),
                'gps': self.get_latest_from_buffer(self.stream_manager.gps_buffer),
                'timestamp': time.time()
            }
        elif stream_type == 'sensors':
            return self.get_latest_from_buffer(self.stream_manager.sensor_buffer)
        elif stream_type == 'system':
            return self.get_latest_from_buffer(self.stream_manager.system_buffer)
        elif stream_type == 'gps':
            return self.get_latest_from_buffer(self.stream_manager.gps_buffer)
        else:
            return None
    
    def get_latest_from_buffer(self, buffer):
        """Get latest data from buffer"""
        if buffer:
            return buffer[-1]
        return None
    
    def get_historical_data(self, stream_type, start_time=None, end_time=None, limit=100):
        """Get historical data with time filtering"""
        if stream_type == 'sensors':
            buffer = self.stream_manager.sensor_buffer
        elif stream_type == 'system':
            buffer = self.stream_manager.system_buffer
        elif stream_type == 'gps':
            buffer = self.stream_manager.gps_buffer
        else:
            return []
        
        data = list(buffer)
        
        # Filter by time if specified
        if start_time:
            data = [d for d in data if d['timestamp'] >= start_time]
        if end_time:
            data = [d for d in data if d['timestamp'] <= end_time]
        
        # Limit results
        if len(data) > limit:
            data = data[-limit:]
        
        return data
    
    def get_stream_statistics(self):
        """Get streaming statistics"""
        return self.stream_manager.get_stream_stats()

def main():
    """Test streaming server"""
    import asyncio
    
    # Create stream manager
    stream_manager = DataStreamManager()
    
    # Start WebSocket server
    try:
        asyncio.run(stream_manager.start_websocket_server())
    except KeyboardInterrupt:
        logger.info("📡 Streaming server stopped by user")
    except Exception as e:
        logger.error(f"📡 Streaming server error: {e}")

if __name__ == "__main__":
    main()
