import bluetooth
import json
import time

def connect_to_vehicle_bluetooth():
    """Example Bluetooth client for connecting to mining vehicle"""
    
    # Search for nearby Bluetooth devices
    print("Searching for mining vehicles...")
    nearby_devices = bluetooth.discover_devices(lookup_names=True)
    
    mining_vehicle = None
    for addr, name in nearby_devices:
        if "MiningVehicleControl" in name or "SmartRover" in name:
            mining_vehicle = (addr, name)
            break
    
    if not mining_vehicle:
        print("No mining vehicles found")
        return
    
    addr, name = mining_vehicle
    print(f"Found vehicle: {name} at {addr}")
    
    # Connect to the vehicle
    try:
        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        
        # Find the service port
        services = bluetooth.find_service(address=addr)
        port = None
        for service in services:
            if service["name"] == "MiningVehicleControl":
                port = service["port"]
                break
        
        if not port:
            print("Mining vehicle service not found")
            return
        
        sock.connect((addr, port))
        print(f"Connected to {name}")
        
        # Authenticate
        auth_message = {
            "type": "auth",
            "email": "cvlised360@gmail.com",
            "password": "Cvlised@360"
        }
        
        sock.send(json.dumps(auth_message).encode('utf-8'))
        response = json.loads(sock.recv(1024).decode('utf-8'))
        
        if response.get('success'):
            print("Authentication successful")
            
            # Get vehicle status
            while True:
                status_request = {"type": "get_status"}
                sock.send(json.dumps(status_request).encode('utf-8'))
                
                status_response = json.loads(sock.recv(1024).decode('utf-8'))
                if status_response.get('success'):
                    data = status_response['data']
                    print(f"Vehicle Status: {data['system_status']['running']}")
                    print(f"Position: {data['position']}")
                    print(f"Speed: {data['action_data']['speed']}")
                
                time.sleep(2)
        else:
            print("Authentication failed")
            
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    connect_to_vehicle_bluetooth()
