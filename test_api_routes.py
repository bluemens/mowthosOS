#!/usr/bin/env python3
"""
API Route Testing Script for MowthosOS Backend

This script tests all available API endpoints to ensure they're properly set up.
Run this to verify the backend is ready for frontend integration.
"""

import asyncio
import httpx
from typing import Dict, Optional
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "email": "test@example.com",
    "password": "TestPassword123",
    "first_name": "Test",
    "last_name": "User"
}

class APITester:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL)
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.headers: Dict[str, str] = {}
        
    async def close(self):
        await self.client.aclose()
        
    def set_auth_headers(self, token: str):
        """Set authorization headers for authenticated requests"""
        self.headers = {"Authorization": f"Bearer {token}"}
        
    async def test_health(self):
        """Test health endpoint"""
        print("\n🏥 Testing Health Endpoint...")
        try:
            response = await self.client.get("/health/")
            print(f"✓ Health check: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False
            
    async def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication Endpoints...")
        
        # 1. Register user
        print("\n1. Testing user registration...")
        try:
            response = await self.client.post("/auth/register", json=TEST_USER)
            if response.status_code == 201:
                print(f"✓ User registered successfully")
            elif response.status_code == 400:
                print(f"ℹ User already exists (expected if running multiple times)")
            else:
                print(f"✗ Registration failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"✗ Registration error: {e}")
            
        # 2. Login
        print("\n2. Testing login...")
        try:
            login_data = {
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            }
            response = await self.client.post("/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.set_auth_headers(self.access_token)
                print(f"✓ Login successful")
                print(f"  Access token received: {self.access_token[:20]}...")
            else:
                print(f"✗ Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False
            
        # 3. Get current user
        print("\n3. Testing get current user...")
        try:
            response = await self.client.get("/auth/me", headers=self.headers)
            if response.status_code == 200:
                user_data = response.json()
                print(f"✓ Current user retrieved")
                print(f"  User: {user_data['email']}")
            else:
                print(f"✗ Get user failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Get user error: {e}")
            
        # 4. Refresh token
        print("\n4. Testing token refresh...")
        try:
            response = await self.client.post("/auth/refresh", json={
                "refresh_token": self.refresh_token
            })
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.set_auth_headers(self.access_token)
                print(f"✓ Token refreshed successfully")
            else:
                print(f"✗ Refresh failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Refresh error: {e}")
            
        return True
        
    async def test_mower_endpoints(self):
        """Test mower control endpoints"""
        print("\n🚜 Testing Mower Endpoints...")
        
        endpoints = [
            ("GET", "/api/v1/mowers/devices", "List devices"),
            # Note: Other mower endpoints require actual device connection
        ]
        
        for method, endpoint, description in endpoints:
            print(f"\nTesting {description}...")
            try:
                if method == "GET":
                    response = await self.client.get(endpoint, headers=self.headers)
                print(f"✓ {description}: {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response: {response.json()}")
            except Exception as e:
                print(f"✗ {description} failed: {e}")
                
    async def test_cluster_endpoints(self):
        """Test cluster management endpoints"""
        print("\n🏘️ Testing Cluster Endpoints...")
        
        # 1. Create cluster
        print("\n1. Testing cluster creation...")
        cluster_id = None
        try:
            cluster_data = {
                "name": "Test Cluster",
                "address": "123 Test Street",
                "max_members": 5,
                "description": "Test cluster for API testing"
            }
            response = await self.client.post(
                "/api/v1/clusters/create", 
                json=cluster_data,
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                cluster_id = data["id"]
                print(f"✓ Cluster created")
                print(f"  Cluster ID: {cluster_id}")
                print(f"  Cluster code: {data['code']}")
            else:
                print(f"✗ Create cluster failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"✗ Create cluster error: {e}")
            
        # 2. Get my clusters
        print("\n2. Testing get my clusters...")
        try:
            response = await self.client.get(
                "/api/v1/clusters/my-clusters",
                headers=self.headers
            )
            if response.status_code == 200:
                clusters = response.json()
                print(f"✓ Retrieved {len(clusters)} cluster(s)")
            else:
                print(f"✗ Get clusters failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Get clusters error: {e}")
            
        # 3. Get cluster details (if we created one)
        if cluster_id:
            print(f"\n3. Testing get cluster details...")
            try:
                response = await self.client.get(
                    f"/api/v1/clusters/{cluster_id}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    print(f"✓ Cluster details retrieved")
                else:
                    print(f"✗ Get cluster details failed: {response.status_code}")
            except Exception as e:
                print(f"✗ Get cluster details error: {e}")
                
    async def test_device_endpoints(self):
        """Test device management endpoints"""
        print("\n📱 Testing Device Endpoints...")
        
        # 1. Get my devices
        print("\n1. Testing get my devices...")
        try:
            response = await self.client.get(
                "/api/v1/devices/my-devices",
                headers=self.headers
            )
            if response.status_code == 200:
                devices = response.json()
                print(f"✓ Retrieved {len(devices)} device(s)")
            else:
                print(f"✗ Get devices failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Get devices error: {e}")
            
    async def test_payment_endpoints(self):
        """Test payment endpoints"""
        print("\n💳 Testing Payment Endpoints...")
        
        # 1. Get subscription plans
        print("\n1. Testing get subscription plans...")
        try:
            response = await self.client.get("/api/v1/payments/plans")
            if response.status_code == 200:
                plans = response.json()
                print(f"✓ Retrieved {len(plans)} plan(s)")
                for plan in plans[:2]:  # Show first 2 plans
                    print(f"  - {plan['name']}: ${plan['monthly_price']}/month")
            else:
                print(f"✗ Get plans failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Get plans error: {e}")
            
        # 2. Get payment methods
        print("\n2. Testing get payment methods...")
        try:
            response = await self.client.get(
                "/api/v1/payments/payment-methods",
                headers=self.headers
            )
            if response.status_code == 200:
                methods = response.json()
                print(f"✓ Retrieved {len(methods)} payment method(s)")
            else:
                print(f"✗ Get payment methods failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Get payment methods error: {e}")
            
    async def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting MowthosOS API Route Tests")
        print("=" * 50)
        
        # Test endpoints in order
        await self.test_health()
        
        if await self.test_auth_endpoints():
            # Only test authenticated endpoints if login succeeded
            await self.test_mower_endpoints()
            await self.test_cluster_endpoints()
            await self.test_device_endpoints()
            await self.test_payment_endpoints()
        
        print("\n" + "=" * 50)
        print("✅ API Route Testing Complete!")
        print("\nNote: Some endpoints may require additional setup:")
        print("- Mower endpoints need actual device connection")
        print("- Payment endpoints need Stripe configuration")
        print("- Device telemetry needs actual device data")

async def main():
    """Main test runner"""
    tester = APITester()
    try:
        await tester.run_all_tests()
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())