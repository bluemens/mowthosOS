#!/usr/bin/env python3
"""
Test script for the Mammotion Mower Control API.

This script provides an interactive interface to test the FastAPI microservice
that controls Mammotion robotic mowers.
"""

import requests
import json
import sys
from typing import Optional, Dict, Any
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 30  # seconds

class MowthosAPITester:
    """Test client for the Mammotion Mower Control API."""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.timeout = DEFAULT_TIMEOUT
        self.logged_in = False
        self.device_name: Optional[str] = None
        self.session_id: Optional[str] = None
        
    def print_separator(self, title: str = ""):
        """Print a formatted separator line."""
        if title:
            print(f"\n{'='*60}")
            print(f" {title}")
            print(f"{'='*60}")
        else:
            print(f"\n{'-'*60}")
    
    def print_success(self, message: str):
        """Print a success message."""
        print(f"✅ {message}")
    
    def print_error(self, message: str):
        """Print an error message."""
        print(f"❌ {message}")
    
    def print_info(self, message: str):
        """Print an info message."""
        print(f"ℹ️  {message}")
    
    def print_json(self, data: Dict[str, Any], title: str = "Response"):
        """Pretty print JSON data."""
        self.print_separator(title)
        print(json.dumps(data, indent=2, default=str))
    
    def check_server_health(self) -> bool:
        """Check if the API server is running and healthy."""
        try:
            self.print_info("Checking server health...")
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            response.raise_for_status()
            
            health_data = response.json()
            self.print_success(f"Server is healthy: {health_data.get('status', 'unknown')}")
            self.print_info(f"Service: {health_data.get('service', 'unknown')}")
            return True
            
        except requests.exceptions.ConnectionError:
            self.print_error(f"Cannot connect to server at {self.base_url}")
            self.print_info("Make sure the FastAPI server is running with: python main.py")
            return False
        except requests.exceptions.RequestException as e:
            self.print_error(f"Health check failed: {e}")
            return False
    
    def get_login_credentials(self) -> Dict[str, str]:
        """Prompt user for login credentials."""
        self.print_separator("Login")
        print("Please enter your Mammotion account credentials:")
        
        email = input("Email/Username: ").strip()
        if not email:
            self.print_error("Email is required")
            sys.exit(1)
        
        password = input("Password: ").strip()
        if not password:
            self.print_error("Password is required")
            sys.exit(1)
        
        device_name = input("Device name (optional, press Enter to use default): ").strip()
        
        credentials = {
            "account": email,
            "password": password
        }
        
        if device_name:
            credentials["device_name"] = device_name
        
        return credentials
    
    def login(self, credentials: Dict[str, str]) -> bool:
        """Login to the Mammotion API."""
        try:
            self.print_info("Logging in to Mammotion...")
            
            response = self.session.post(
                f"{self.base_url}/login",
                json=credentials,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            login_data = response.json()
            
            if login_data.get("success"):
                self.logged_in = True
                self.device_name = login_data.get("device_name")
                self.session_id = login_data.get("session_id")
                
                self.print_success("Login successful!")
                self.print_info(f"Device: {self.device_name}")
                self.print_info(f"Session ID: {self.session_id}")
                return True
            else:
                self.print_error(f"Login failed: {login_data.get('message', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Login request failed: {e}")
            return False
    
    def get_mower_status(self) -> bool:
        """Get the current status of the mower."""
        if not self.logged_in or not self.device_name:
            self.print_error("Not logged in or no device available")
            return False
        
        try:
            self.print_info(f"Getting status for device: {self.device_name}")
            
            response = self.session.get(
                f"{self.base_url}/status",
                params={"device_name": self.device_name},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            status_data = response.json()
            self.print_mower_status(status_data)
            return True
            
        except requests.exceptions.RequestException as e:
            self.print_error(f"Status request failed: {e}")
            return False
    
    def print_mower_status(self, status: Dict[str, Any]):
        """Print mower status in a readable format."""
        self.print_separator("Mower Status")
        
        # Basic info
        print(f"Device: {status.get('device_name', 'Unknown')}")
        print(f"Online: {'Yes' if status.get('online') else 'No'}")
        print(f"Last Updated: {status.get('last_updated', 'Unknown')}")
        
        # Work status
        print(f"\nWork Status:")
        print(f"  Mode: {status.get('work_mode', 'Unknown')} (Code: {status.get('work_mode_code', 'Unknown')})")
        print(f"  Progress: {status.get('work_progress', 'Unknown')}%")
        print(f"  Area: {status.get('work_area', 'Unknown')} m²")
        
        # Battery and charging
        print(f"\nBattery & Charging:")
        print(f"  Battery Level: {status.get('battery_level', 'Unknown')}%")
        print(f"  Charging State: {status.get('charging_state', 'Unknown')}")
        print(f"  Blade Status: {'Active' if status.get('blade_status') else 'Inactive'}")
        
        # Location
        location = status.get('location')
        if location:
            print(f"\nLocation:")
            print(f"  Latitude: {location.get('latitude', 'Unknown')}")
            print(f"  Longitude: {location.get('longitude', 'Unknown')}")
            print(f"  Position Type: {location.get('position_type', 'Unknown')}")
            print(f"  Orientation: {location.get('orientation', 'Unknown')}°")
        else:
            print(f"\nLocation: Not available")
    
    def list_devices(self) -> bool:
        """List all available devices."""
        try:
            self.print_info("Getting device list...")
            
            response = self.session.get(f"{self.base_url}/devices", timeout=self.timeout)
            response.raise_for_status()
            
            devices_data = response.json()
            self.print_separator("Available Devices")
            
            devices = devices_data.get("devices", [])
            if not devices:
                print("No devices found.")
                return True
            
            for i, device in enumerate(devices, 1):
                print(f"\nDevice {i}:")
                print(f"  Name: {device.get('name', 'Unknown')}")
                print(f"  IoT ID: {device.get('iot_id', 'Unknown')}")
                print(f"  Preference: {device.get('preference', 'Unknown')}")
                print(f"  Has Cloud: {'Yes' if device.get('has_cloud') else 'No'}")
                print(f"  Has BLE: {'Yes' if device.get('has_ble') else 'No'}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.print_error(f"Device list request failed: {e}")
            return False
    
    def send_command(self, command: str) -> bool:
        """Send a command to the mower."""
        if not self.logged_in or not self.device_name:
            self.print_error("Not logged in or no device available")
            return False
        
        command_endpoints = {
            "start": "/start-mow",
            "stop": "/stop-mow",
            "pause": "/pause-mowing",
            "resume": "/resume-mowing",
            "dock": "/return-to-dock"
        }
        
        if command not in command_endpoints:
            self.print_error(f"Unknown command: {command}")
            return False
        
        try:
            self.print_info(f"Sending {command} command to device: {self.device_name}")
            
            response = self.session.post(
                f"{self.base_url}{command_endpoints[command]}",
                json={"device_name": self.device_name},
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            command_data = response.json()
            
            if command_data.get("success"):
                self.print_success(f"{command.title()} command sent successfully!")
                self.print_info(f"Message: {command_data.get('message', 'No message')}")
                return True
            else:
                self.print_error(f"Command failed: {command_data.get('message', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Command request failed: {e}")
            return False
    
    def interactive_menu(self):
        """Show interactive menu for testing commands."""
        while True:
            self.print_separator("Mowthos API Test Menu")
            print("1. Get mower status")
            print("2. List devices")
            print("3. Start mowing")
            print("4. Stop mowing")
            print("5. Pause mowing")
            print("6. Resume mowing")
            print("7. Return to dock")
            print("8. Refresh status")
            print("9. Exit")
            
            choice = input("\nEnter your choice (1-9): ").strip()
            
            if choice == "1":
                self.get_mower_status()
            elif choice == "2":
                self.list_devices()
            elif choice == "3":
                self.send_command("start")
            elif choice == "4":
                self.send_command("stop")
            elif choice == "5":
                self.send_command("pause")
            elif choice == "6":
                self.send_command("resume")
            elif choice == "7":
                self.send_command("dock")
            elif choice == "8":
                self.get_mower_status()
            elif choice == "9":
                self.print_info("Goodbye!")
                break
            else:
                self.print_error("Invalid choice. Please enter a number between 1-9.")
            
            input("\nPress Enter to continue...")

def main():
    """Main function to run the API tester."""
    print("🤖 Mammotion Mower Control API Tester")
    print("=" * 50)
    
    # Initialize tester
    tester = MowthosAPITester()
    
    # Check server health
    if not tester.check_server_health():
        sys.exit(1)
    
    # Get login credentials
    credentials = tester.get_login_credentials()
    
    # Login
    if not tester.login(credentials):
        sys.exit(1)
    
    # Get initial status
    print("\n" + "="*60)
    print(" Getting initial mower status...")
    print("="*60)
    tester.get_mower_status()
    
    # Show interactive menu
    tester.interactive_menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1) 