#!/usr/bin/env python3
"""
Simple test script to verify the productivity API is working
"""

import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_health():
    """Test health endpoint"""
    print("=== Testing Health Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_distraction_urls():
    """Test distraction URLs endpoint"""
    print("\n=== Testing Distraction URLs ===")
    test_data = {
        "user_id": "test_user",
        "urls": ["facebook.com", "twitter.com", "youtube.com"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/distraction-urls",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_productive_urls():
    """Test productive URLs endpoint"""
    print("\n=== Testing Productive URLs ===")
    test_data = {
        "user_id": "test_user",
        "urls": ["github.com", "stackoverflow.com", "docs.python.org"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/productive-urls",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_usage_data():
    """Test usage data endpoint with corrected keys"""
    print("\n=== Testing Usage Data ===")
    test_data = {
        "user_id": "test_user",
        "url": "https://github.com/user/repo",
        "domain": "github.com",
        "duration": 300,
        "interactions": {"clicks": 10, "scrolls": 5, "keystrokes": 100},
        "timestamp": "2024-01-01T10:00:00",
        "is_distraction": False,  # [Correction] Matches backend expectations
        "is_productive": True    # [Correction] Matches backend expectations
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/usage-data",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_get_question():
    """Test get question endpoint"""
    print("\n=== Testing Get Question ===")
    test_data = {
        "user_id": "test_user",
        "domain": "facebook.com",
        "excessTime": 30
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/get-question",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_question_answer():
    """Test question answer endpoint"""
    print("\n=== Testing Question Answer ===")
    test_data = {
        "user_id": "test_user",
        "domain": "facebook.com",
        "answer": "No, I should focus on work",
        "timestamp": "2024-01-01T10:30:00"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/question-answer",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_get_insights():
    """Test get insights endpoint"""
    print("\n=== Testing Get Insights ===")
    try:
        response = requests.get(f"{BASE_URL}/get-insights?user_id=test_user")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_daily_summary():
    """Test daily summary endpoint"""
    print("\n=== Testing Daily Summary ===")
    try:
        response = requests.get(f"{BASE_URL}/daily-summary?user_id=test_user&date=2024-01-01")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting API Tests...")
    print("Make sure your Flask server is running on http://localhost:5000")
    
    tests = [
        ("Health Check", test_health),
        ("Distraction URLs", test_distraction_urls),
        ("Productive URLs", test_productive_urls),
        ("Usage Data", test_usage_data),
        ("Get Question", test_get_question),
        ("Question Answer", test_question_answer),
        ("Get Insights", test_get_insights),
        ("Daily Summary", test_daily_summary),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        if test_func():
            print(f"✅ {test_name} PASSED")
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the server logs for more details.")

if __name__ == "__main__":
    main()