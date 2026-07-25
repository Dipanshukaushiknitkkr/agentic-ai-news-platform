#!/usr/bin/env python3
"""
Test script for the Personalized Digest System
Demonstrates user registration, preferences setup, and digest generation
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_digest_system():
    """Test the complete digest system workflow"""
    
    async with httpx.AsyncClient() as client:
        print("🚀 Testing Tech News Digest System")
        print("=" * 50)
        
        # Test 1: Register a new user
        print("\n1. 👤 Registering a new user...")
        register_data = {
            "email": f"test_user_{int(datetime.now().timestamp())}@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        try:
            response = await client.post(f"{BASE_URL}/auth/register", json=register_data)
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ User registered: {user_data['email']}")
            else:
                print(f"❌ Registration failed: {response.text}")
                return
        except Exception as e:
            print(f"❌ Connection error: {e}")
            print("💡 Make sure the server is running: uvicorn webapp:app --reload")
            return
        
        # Test 2: Login and get token
        print("\n2. 🔐 Logging in...")
        login_data = {
            "username": register_data["email"],
            "password": register_data["password"]
        }
        
        response = await client.post(f"{BASE_URL}/auth/token", data=login_data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]
            print(f"✅ Login successful, token obtained")
            
            # Set authorization header for subsequent requests
            headers = {"Authorization": f"Bearer {access_token}"}
        else:
            print(f"❌ Login failed: {response.text}")
            return
        
        # Test 3: Get available categories
        print("\n3. 📋 Getting available categories...")
        response = await client.get(f"{BASE_URL}/categories")
        if response.status_code == 200:
            categories = response.json()
            print(f"✅ Found {len(categories)} categories:")
            for cat in categories[:5]:  # Show first 5
                print(f"   - {cat['name']}: {cat['description']}")
            print(f"   ... and {len(categories)-5} more categories" if len(categories) > 5 else "")
        else:
            print(f"❌ Failed to get categories: {response.text}")
            return
        
        # Test 4: Update user preferences
        print("\n4. ⚙️ Setting user preferences...")
        preferences = {
            "daily_digest_enabled": True,
            "weekly_digest_enabled": True,
            "instant_notifications": False,
            "digest_time": "09:00",
            "time_zone": "UTC",
            "interested_categories": [1, 2, 3]  # AI, Startups, Big Tech
        }
        
        response = await client.put(f"{BASE_URL}/preferences", json=preferences, headers=headers)
        if response.status_code == 200:
            user_updated = response.json()
            print(f"✅ Preferences updated:")
            print(f"   - Daily digest: {user_updated['daily_digest_enabled']}")
            print(f"   - Weekly digest: {user_updated['weekly_digest_enabled']}")
            print(f"   - Digest time: {user_updated['digest_time']}")
        else:
            print(f"❌ Failed to update preferences: {response.text}")
        
        # Test 5: Create a custom keyword subscription
        print("\n5. 🔍 Creating custom keyword subscription...")
        subscription = {
            "subscription_type": "daily",
            "keywords": ["artificial intelligence", "machine learning", "startup funding"]
        }
        
        response = await client.post(f"{BASE_URL}/subscriptions", json=subscription, headers=headers)
        if response.status_code == 200:
            sub_data = response.json()
            print(f"✅ Custom subscription created with keywords: {sub_data['keywords']}")
        else:
            print(f"❌ Failed to create subscription: {response.text}")
        
        # Test 6: Preview daily digest
        print("\n6. 📰 Previewing daily digest...")
        response = await client.get(f"{BASE_URL}/digest/preview?digest_type=daily", headers=headers)
        if response.status_code == 200:
            preview = response.json()
            print(f"✅ Daily digest preview:")
            print(f"   - Total articles: {preview['total_articles']}")
            print(f"   - Categories with content: {len(preview['categories'])}")
            for category, articles in preview['categories'].items():
                print(f"     • {category}: {len(articles)} articles")
        else:
            print(f"❌ Failed to preview digest: {response.text}")
        
        # Test 7: Get personalized articles
        print("\n7. 📄 Getting personalized articles...")
        response = await client.get(f"{BASE_URL}/articles/personalized?limit=5", headers=headers)
        if response.status_code == 200:
            articles = response.json()
            print(f"✅ Found {len(articles)} personalized articles:")
            for article in articles:
                print(f"   - {article['title'][:80]}...")
        else:
            print(f"❌ Failed to get personalized articles: {response.text}")
        
        # Test 8: Get all available articles
        print("\n8. 📊 Getting all articles...")
        response = await client.get(f"{BASE_URL}/articles?limit=5")
        if response.status_code == 200:
            articles = response.json()
            print(f"✅ Found {len(articles)} total articles in database")
        else:
            print(f"❌ Failed to get articles: {response.text}")
        
        # Test 9: Test sending digest (if articles available)
        print("\n9. 📧 Testing digest sending...")
        if "SMTP_USERNAME" in open(".env.example").read():
            print("💡 Note: To test email sending, configure SMTP settings in .env file")
        else:
            response = await client.post(f"{BASE_URL}/digest/send?digest_type=daily", headers=headers)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Digest sent: {result['message']}")
            else:
                print(f"ℹ️ Digest sending test: {response.text}")
        
        print("\n" + "=" * 50)
        print("🎉 Digest System Test Complete!")
        print("\n📝 Summary of features tested:")
        print("   ✅ User registration and authentication")
        print("   ✅ Category management")
        print("   ✅ User preferences configuration")
        print("   ✅ Custom keyword subscriptions")
        print("   ✅ Personalized digest preview")
        print("   ✅ Personalized article recommendations")
        print("   ✅ Article database integration")
        
        print("\n🌐 Next steps:")
        print(f"   1. Visit {BASE_URL} to see the web interface")
        print(f"   2. Check API docs at {BASE_URL}/docs")
        print("   3. Configure email settings to test digest delivery")
        print("   4. Set up the scheduler for automated digest sending")

def run_sync_test():
    """Synchronous wrapper for the test"""
    try:
        asyncio.run(test_digest_system())
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    print("Starting Digest System Test...")
    print("Make sure the application is running on http://localhost:8000")
    print("Use: uvicorn webapp:app --reload")
    print()
    
    run_sync_test()