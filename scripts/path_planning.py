#!/usr/bin/env python3
"""
SmartRover Advanced Path Planning Module
Implements A*, RRT, and other path planning algorithms for autonomous navigation
"""

import numpy as np
import math
import heapq
import random
import time
import logging
from collections import deque
import matplotlib.pyplot as plt
from scipy.spatial import KDTree
import json
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartrover/path_planning.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PathPlanner:
    def __init__(self, map_width=2000, map_height=2000, resolution=1.0):
        self.map_width = map_width
        self.map_height = map_height
        self.resolution = resolution  # meters per pixel
        
        # Occupancy grid (0 = free, 1 = occupied, 0.5 = unknown)
        self.occupancy_grid = np.zeros((map_height, map_width), dtype=np.float32)
        
        # Cost map for path planning
        self.cost_map = np.ones((map_height, map_width), dtype=np.float32)
        
        # Inflation radius for obstacles (in pixels)
        self.inflation_radius = 10
        
        # Vehicle parameters
        self.vehicle_radius = 5  # pixels
        self.max_speed = 2.0  # m/s
        self.max_acceleration = 1.0  # m/s²
        self.max_turn_rate = 45  # degrees/second
        
        # Path planning parameters
        self.planning_timeout = 30.0  # seconds
        
        logger.info(f"🗺️ Path planner initialized: {map_width}x{map_height} @ {resolution}m/pixel")
    
    def update_occupancy_grid(self, obstacles, robot_position):
        """Update occupancy grid with new obstacle information"""
        try:
            # Clear previous dynamic obstacles (keep static ones)
            self.occupancy_grid *= 0.9  # Fade old obstacles
            
            # Add new obstacles
            for obstacle in obstacles:
                x, y = obstacle['position']
                distance = obstacle['distance']
                
                # Convert to grid coordinates
                grid_x = int(x / self.resolution)
                grid_y = int(y / self.resolution)
                
                # Mark obstacle in grid
                if 0 <= grid_x < self.map_width and 0 <= grid_y < self.map_height:
                    # Create circular obstacle
                    obstacle_radius = max(3, int(distance / 100))  # Scale with distance
                    for dx in range(-obstacle_radius, obstacle_radius + 1):
                        for dy in range(-obstacle_radius, obstacle_radius + 1):
                            if dx*dx + dy*dy <= obstacle_radius*obstacle_radius:
                                ox, oy = grid_x + dx, grid_y + dy
                                if 0 <= ox < self.map_width and 0 <= oy < self.map_height:
                                    self.occupancy_grid[oy, ox] = 1.0
            
            # Inflate obstacles for safety
            self.inflate_obstacles()
            
            # Update cost map
            self.update_cost_map()
            
        except Exception as e:
            logger.error(f"Error updating occupancy grid: {e}")
    
    def inflate_obstacles(self):
        """Inflate obstacles by vehicle radius for safe path planning"""
        try:
            inflated_grid = self.occupancy_grid.copy()
            
            for y in range(self.map_height):
                for x in range(self.map_width):
                    if self.occupancy_grid[y, x] > 0.5:  # Obstacle
                        # Inflate around this obstacle
                        for dx in range(-self.inflation_radius, self.inflation_radius + 1):
                            for dy in range(-self.inflation_radius, self.inflation_radius + 1):
                                if dx*dx + dy*dy <= self.inflation_radius*self.inflation_radius:
                                    nx, ny = x + dx, y + dy
                                    if 0 <= nx < self.map_width and 0 <= ny < self.map_height:
                                        inflated_grid[ny, nx] = max(inflated_grid[ny, nx], 0.8)
            
            self.occupancy_grid = inflated_grid
            
        except Exception as e:
            logger.error(f"Error inflating obstacles: {e}")
    
    def update_cost_map(self):
        """Update cost map based on occupancy grid"""
        try:
            # Base cost is 1.0 for free space
            self.cost_map = np.ones_like(self.occupancy_grid)
            
            # Increase cost near obstacles
            for y in range(self.map_height):
                for x in range(self.map_width):
                    if self.occupancy_grid[y, x] > 0.9:  # Obstacle
                        self.cost_map[y, x] = 1000.0  # Very high cost
                    elif self.occupancy_grid[y, x] > 0.5:  # Near obstacle
                        self.cost_map[y, x] = 10.0  # High cost
                    elif self.occupancy_grid[y, x] > 0.1:  # Uncertain area
                        self.cost_map[y, x] = 2.0  # Moderate cost
            
        except Exception as e:
            logger.error(f"Error updating cost map: {e}")
    
    def heuristic(self, a, b):
        """Heuristic function for A* (Euclidean distance)"""
        return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)
    
    def get_neighbors(self, node):
        """Get valid neighbors for a node"""
        x, y = node
        neighbors = []
        
        # 8-connected grid
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = x + dx, y + dy
                
                # Check bounds
                if 0 <= nx < self.map_width and 0 <= ny < self.map_height:
                    # Check if not obstacle
                    if self.occupancy_grid[ny, nx] < 0.9:
                        neighbors.append((nx, ny))
        
        return neighbors
    
    def astar_path_planning(self, start, goal):
        """A* path planning algorithm"""
        logger.info(f"🗺️ Planning path from {start} to {goal} using A*")
        
        start_time = time.time()
        
        # Convert to grid coordinates
        start_grid = (int(start[0] / self.resolution), int(start[1] / self.resolution))
        goal_grid = (int(goal[0] / self.resolution), int(goal[1] / self.resolution))
        
        # Check if start and goal are valid
        if not (0 <= start_grid[0] < self.map_width and 0 <= start_grid[1] < self.map_height):
            logger.error("Start position out of bounds")
            return None
        
        if not (0 <= goal_grid[0] < self.map_width and 0 <= goal_grid[1] < self.map_height):
            logger.error("Goal position out of bounds")
            return None
        
        if self.occupancy_grid[start_grid[1], start_grid[0]] > 0.9:
            logger.error("Start position is in obstacle")
            return None
        
        if self.occupancy_grid[goal_grid[1], goal_grid[0]] > 0.9:
            logger.error("Goal position is in obstacle")
            return None
        
        # A* algorithm
        open_set = []
        heapq.heappush(open_set, (0, start_grid))
        came_from = {}
        g_score = {start_grid: 0}
        f_score = {start_grid: self.heuristic(start_grid, goal_grid)}
        
        while open_set:
            # Check timeout
            if time.time() - start_time > self.planning_timeout:
                logger.warning("A* planning timeout")
                break
            
            current = heapq.heappop(open_set)[1]
            
            if current == goal_grid:
                # Reconstruct path
                path = []
                while current in came_from:
                    # Convert back to world coordinates
                    world_pos = (current[0] * self.resolution, current[1] * self.resolution)
                    path.append(world_pos)
                    current = came_from[current]
                
                # Add start position
                path.append(start)
                path.reverse()
                
                logger.info(f"🗺️ A* path found with {len(path)} waypoints in {time.time() - start_time:.2f}s")
                return self.smooth_path(path)
            
            for neighbor in self.get_neighbors(current):
                # Calculate movement cost
                move_cost = 1.0
                if abs(neighbor[0] - current[0]) + abs(neighbor[1] - current[1]) == 2:
                    move_cost = 1.414  # Diagonal movement
                
                # Add terrain cost
                terrain_cost = self.cost_map[neighbor[1], neighbor[0]]
                tentative_g_score = g_score[current] + move_cost * terrain_cost
                
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, goal_grid)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        logger.warning("🗺️ A* failed to find path")
        return None
    
    def rrt_path_planning(self, start, goal, max_iterations=5000):
        """RRT (Rapidly-exploring Random Tree) path planning"""
        logger.info(f"🗺️ Planning path from {start} to {goal} using RRT")
        
        start_time = time.time()
        
        class RRTNode:
            def __init__(self, x, y):
                self.x = x
                self.y = y
                self.parent = None
        
        # Initialize tree with start node
        start_node = RRTNode(start[0], start[1])
        nodes = [start_node]
        
        step_size = 20.0  # meters
        goal_threshold = 10.0  # meters
        
        for i in range(max_iterations):
            # Check timeout
            if time.time() - start_time > self.planning_timeout:
                logger.warning("RRT planning timeout")
                break
            
            # Sample random point (bias towards goal)
            if random.random() < 0.1:  # 10% chance to sample goal
                rand_x, rand_y = goal[0], goal[1]
            else:
                rand_x = random.uniform(0, self.map_width * self.resolution)
                rand_y = random.uniform(0, self.map_height * self.resolution)
            
            # Find nearest node
            min_dist = float('inf')
            nearest_node = None
            for node in nodes:
                dist = math.sqrt((node.x - rand_x)**2 + (node.y - rand_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_node = node
            
            # Create new node in direction of random point
            if min_dist > step_size:
                theta = math.atan2(rand_y - nearest_node.y, rand_x - nearest_node.x)
                new_x = nearest_node.x + step_size * math.cos(theta)
                new_y = nearest_node.y + step_size * math.sin(theta)
            else:
                new_x, new_y = rand_x, rand_y
            
            # Check if path to new node is collision-free
            if self.is_path_collision_free((nearest_node.x, nearest_node.y), (new_x, new_y)):
                new_node = RRTNode(new_x, new_y)
                new_node.parent = nearest_node
                nodes.append(new_node)
                
                # Check if we reached the goal
                goal_dist = math.sqrt((new_x - goal[0])**2 + (new_y - goal[1])**2)
                if goal_dist < goal_threshold:
                    # Reconstruct path
                    path = []
                    current = new_node
                    while current:
                        path.append((current.x, current.y))
                        current = current.parent
                    
                    path.reverse()
                    path.append(goal)  # Add exact goal
                    
                    logger.info(f"🗺️ RRT path found with {len(path)} waypoints in {time.time() - start_time:.2f}s")
                    return self.smooth_path(path)
        
        logger.warning("🗺️ RRT failed to find path")
        return None
    
    def is_path_collision_free(self, start, end):
        """Check if path between two points is collision-free"""
        try:
            # Bresenham's line algorithm
            x0, y0 = int(start[0] / self.resolution), int(start[1] / self.resolution)
            x1, y1 = int(end[0] / self.resolution), int(end[1] / self.resolution)
            
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx - dy
            
            x, y = x0, y0
            
            while True:
                # Check bounds
                if not (0 <= x < self.map_width and 0 <= y < self.map_height):
                    return False
                
                # Check collision
                if self.occupancy_grid[y, x] > 0.9:
                    return False
                
                if x == x1 and y == y1:
                    break
                
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x += sx
                if e2 < dx:
                    err += dx
                    y += sy
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking path collision: {e}")
            return False
    
    def smooth_path(self, path):
        """Smooth path using simple line-of-sight optimization"""
        if len(path) < 3:
            return path
        
        try:
            smoothed_path = [path[0]]  # Start with first point
            
            i = 0
            while i < len(path) - 1:
                # Look ahead to find furthest visible point
                furthest = i + 1
                for j in range(i + 2, len(path)):
                    if self.is_path_collision_free(path[i], path[j]):
                        furthest = j
                    else:
                        break
                
                smoothed_path.append(path[furthest])
                i = furthest
            
            logger.info(f"🗺️ Path smoothed from {len(path)} to {len(smoothed_path)} waypoints")
            return smoothed_path
            
        except Exception as e:
            logger.error(f"Error smoothing path: {e}")
            return path
    
    def plan_path(self, start, goal, algorithm='astar'):
        """Plan path using specified algorithm"""
        logger.info(f"🗺️ Planning path using {algorithm}")
        
        if algorithm == 'astar':
            return self.astar_path_planning(start, goal)
        elif algorithm == 'rrt':
            return self.rrt_path_planning(start, goal)
        else:
            logger.error(f"Unknown path planning algorithm: {algorithm}")
            return None
    
    def calculate_path_cost(self, path):
        """Calculate total cost of a path"""
        if not path or len(path) < 2:
            return 0
        
        total_cost = 0
        for i in range(len(path) - 1):
            # Distance cost
            distance = math.sqrt(
                (path[i+1][0] - path[i][0])**2 + 
                (path[i+1][1] - path[i][1])**2
            )
            
            # Terrain cost (sample along path)
            mid_x = (path[i][0] + path[i+1][0]) / 2
            mid_y = (path[i][1] + path[i+1][1]) / 2
            grid_x = int(mid_x / self.resolution)
            grid_y = int(mid_y / self.resolution)
            
            terrain_cost = 1.0
            if 0 <= grid_x < self.map_width and 0 <= grid_y < self.map_height:
                terrain_cost = self.cost_map[grid_y, grid_x]
            
            total_cost += distance * terrain_cost
        
        return total_cost
    
    def generate_velocity_profile(self, path):
        """Generate velocity profile for path following"""
        if not path or len(path) < 2:
            return []
        
        velocities = []
        
        for i in range(len(path)):
            if i == 0 or i == len(path) - 1:
                # Start and end with zero velocity
                velocities.append(0.0)
            else:
                # Calculate curvature
                p1 = np.array(path[i-1])
                p2 = np.array(path[i])
                p3 = np.array(path[i+1])
                
                # Vectors
                v1 = p2 - p1
                v2 = p3 - p2
                
                # Angle between vectors
                angle = math.acos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))
                curvature = abs(math.pi - angle)
                
                # Velocity based on curvature
                max_vel = self.max_speed
                if curvature > 0.1:  # Sharp turn
                    max_vel *= 0.3
                elif curvature > 0.05:  # Moderate turn
                    max_vel *= 0.6
                
                velocities.append(max_vel)
        
        return velocities
    
    def export_path_data(self, path, algorithm_used='unknown'):
        """Export path data for visualization and analysis"""
        if not path:
            return None
        
        return {
            'path': path,
            'algorithm': algorithm_used,
            'waypoint_count': len(path),
            'total_distance': sum(
                math.sqrt((path[i+1][0] - path[i][0])**2 + (path[i+1][1] - path[i][1])**2)
                for i in range(len(path) - 1)
            ),
            'total_cost': self.calculate_path_cost(path),
            'velocity_profile': self.generate_velocity_profile(path),
            'timestamp': time.time()
        }

class PathFollower:
    def __init__(self, path_planner):
        self.path_planner = path_planner
        self.current_path = None
        self.current_waypoint_index = 0
        self.waypoint_tolerance = 2.0  # meters
        
        # Pure pursuit parameters
        self.lookahead_distance = 5.0  # meters
        self.min_lookahead = 2.0
        self.max_lookahead = 10.0
        
    def set_path(self, path):
        """Set new path to follow"""
        self.current_path = path
        self.current_waypoint_index = 0
        logger.info(f"🗺️ New path set with {len(path)} waypoints")
    
    def get_steering_command(self, current_position, current_heading, current_speed):
        """Get steering command using pure pursuit algorithm"""
        if not self.current_path or self.current_waypoint_index >= len(self.current_path):
            return {'action': 'stop', 'speed': 0.0, 'steering': 0.0}
        
        try:
            # Adaptive lookahead distance
            lookahead = max(self.min_lookahead, min(self.max_lookahead, current_speed * 2.0))
            
            # Find lookahead point
            lookahead_point = self.find_lookahead_point(current_position, lookahead)
            
            if not lookahead_point:
                # No lookahead point found, head to next waypoint
                if self.current_waypoint_index < len(self.current_path):
                    lookahead_point = self.current_path[self.current_waypoint_index]
                else:
                    return {'action': 'stop', 'speed': 0.0, 'steering': 0.0}
            
            # Calculate steering angle using pure pursuit
            dx = lookahead_point[0] - current_position[0]
            dy = lookahead_point[1] - current_position[1]
            
            # Angle to lookahead point
            target_angle = math.atan2(dy, dx)
            
            # Heading error
            heading_error = target_angle - math.radians(current_heading)
            
            # Normalize heading error
            while heading_error > math.pi:
                heading_error -= 2 * math.pi
            while heading_error < -math.pi:
                heading_error += 2 * math.pi
            
            # Calculate steering command
            if abs(heading_error) > math.radians(45):  # Large heading error
                if heading_error > 0:
                    action = 'turn_left'
                else:
                    action = 'turn_right'
                speed = 0.3  # Slow down for sharp turns
            elif abs(heading_error) > math.radians(10):  # Moderate heading error
                action = 'straight'
                speed = 0.6
            else:  # Small heading error
                action = 'straight'
                speed = 1.0
            
            # Check if we've reached current waypoint
            current_waypoint = self.current_path[self.current_waypoint_index]
            distance_to_waypoint = math.sqrt(
                (current_position[0] - current_waypoint[0])**2 + 
                (current_position[1] - current_waypoint[1])**2
            )
            
            if distance_to_waypoint < self.waypoint_tolerance:
                self.current_waypoint_index += 1
                logger.info(f"🗺️ Reached waypoint {self.current_waypoint_index}/{len(self.current_path)}")
                
                if self.current_waypoint_index >= len(self.current_path):
                    logger.info("🗺️ Path following completed")
                    return {'action': 'stop', 'speed': 0.0, 'steering': 0.0}
            
            return {
                'action': action,
                'speed': speed,
                'steering': math.degrees(heading_error),
                'lookahead_point': lookahead_point,
                'distance_to_waypoint': distance_to_waypoint,
                'waypoint_index': self.current_waypoint_index
            }
            
        except Exception as e:
            logger.error(f"Error calculating steering command: {e}")
            return {'action': 'stop', 'speed': 0.0, 'steering': 0.0}
    
    def find_lookahead_point(self, current_position, lookahead_distance):
        """Find lookahead point on path"""
        if not self.current_path:
            return None
        
        try:
            # Start from current waypoint
            for i in range(self.current_waypoint_index, len(self.current_path) - 1):
                p1 = self.current_path[i]
                p2 = self.current_path[i + 1]
                
                # Check if lookahead circle intersects with path segment
                intersection = self.line_circle_intersection(
                    current_position, lookahead_distance, p1, p2
                )
                
                if intersection:
                    return intersection
            
            # If no intersection found, return last waypoint
            return self.current_path[-1]
            
        except Exception as e:
            logger.error(f"Error finding lookahead point: {e}")
            return None
    
    def line_circle_intersection(self, center, radius, p1, p2):
        """Find intersection of line segment with circle"""
        try:
            # Vector from p1 to p2
            d = np.array([p2[0] - p1[0], p2[1] - p1[1]])
            # Vector from p1 to circle center
            f = np.array([p1[0] - center[0], p1[1] - center[1]])
            
            a = np.dot(d, d)
            b = 2 * np.dot(f, d)
            c = np.dot(f, f) - radius * radius
            
            discriminant = b * b - 4 * a * c
            
            if discriminant < 0:
                return None  # No intersection
            
            discriminant = math.sqrt(discriminant)
            
            # Two possible intersections
            t1 = (-b - discriminant) / (2 * a)
            t2 = (-b + discriminant) / (2 * a)
            
            # Check if intersections are on line segment
            for t in [t1, t2]:
                if 0 <= t <= 1:
                    intersection = (p1[0] + t * d[0], p1[1] + t * d[1])
                    return intersection
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating line-circle intersection: {e}")
            return None

def main():
    """Test path planning"""
    planner = PathPlanner()
    
    # Add some obstacles
    obstacles = [
        {'position': [500, 500], 'distance': 50},
        {'position': [800, 300], 'distance': 75},
        {'position': [600, 700], 'distance': 60}
    ]
    
    planner.update_occupancy_grid(obstacles, [100, 100])
    
    # Plan path
    start = (100, 100)
    goal = (900, 900)
    
    path = planner.plan_path(start, goal, 'astar')
    
    if path:
        print(f"Path found with {len(path)} waypoints")
        path_data = planner.export_path_data(path, 'astar')
        print(f"Total distance: {path_data['total_distance']:.2f}m")
        print(f"Total cost: {path_data['total_cost']:.2f}")
    else:
        print("No path found")

if __name__ == "__main__":
    main()
