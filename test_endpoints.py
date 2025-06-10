import requests
import json
import time

# Base URL - adjust this to your server's URL
BASE_URL = "http://localhost:8000"  # Change to your server URL

# Test session ID
TEST_SESSION_ID = "test_session_123"

def make_request(method, url, data=None, expected_status=200):
    """Helper function to test an endpoint"""
    try:
        if method == "POST":
            response = requests.post(url, json=data)
        elif method == "GET":
            response = requests.get(url)
        
        print(f"\n{'='*60}")
        print(f"{method} {url}")
        print(f"Request Data: {json.dumps(data, indent=2) if data else 'None'}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == expected_status:
            print("✅ Test PASSED")
        else:
            print(f"❌ Test FAILED - Expected {expected_status}, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test ERROR: {str(e)}")

def run_tests():
    print("🚀 Starting API Endpoint Tests")
    print(f"Base URL: {BASE_URL}")
    
    # Test 1: Root endpoint (GET)
    # make_request("GET", f"{BASE_URL}/")
    
    # Test 2: Add to waitlist
    # make_request("POST", f"{BASE_URL}/waitlist", {
    #     "email": "test@example.com"
    # })
    
    # Test 3: Create session resources
    # make_request("POST", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/resources", {
    #     "query": "mental health resources"
    # })
    
    # Test 4: Add cognitive distortions
    # make_request("POST", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/cognitive-distortions", {
    #     "cognitiveDistortions": [
    #         "All-or-nothing thinking",
    #         "Catastrophizing",
    #         "Mind reading"
    #     ]
    # })
    
    # Test 5: Add user tasks (first task)
    # make_request("POST", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/tasks", {
    #     "task": "Practice deep breathing for 5 minutes daily"
    # })
    
    # Test 6: Add another user task (should append to existing)
    # make_request("POST", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/tasks", {
    #     "task": "Write in gratitude journal before bed"
    # })
    
    # Test 7: Create session summary
    # make_request("POST", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/summary", {
    #     "conversationSummary": "User discussed feelings of anxiety and overwhelm at work. We identified several cognitive distortions and created actionable tasks.",
    #     "identifiedCognitiveDistortions": [
    #         "Catastrophizing",
    #         "All-or-nothing thinking"
    #     ],
    #     "suggestedExercises": "Practice mindfulness meditation and challenge negative thoughts using CBT techniques."
    # })
    
    # Test 8: Send email (this might fail if email credentials aren't set up)
    # make_request("POST", f"{BASE_URL}/emails", {
        # "email_address": "test@example.com",
        # "insights": {
        #     "summary": "User discussed feelings of anxiety and overwhelm at work.",
        #     "tasks": [
        #         "Practice deep breathing for 5 minutes daily",
        #         "Write in gratitude journal before bed"
        #     ],
        #     "topics": [
        #         "Catastrophizing",
        #         "All-or-nothing thinking"
        #     ]
        # }
    # }, expected_status=500)  # Expecting 500 if email not configured
    
    # # Test 9: Create session call (might fail if Ultravox API key not set)
    # make_request("POST", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/calls", {}, 
    #              expected_status=200)  # Expecting 500 if API key not configured
    
    print("\n" + "="*60)
    print("🏁 API Tests Completed!")
    print("\nNow testing GET endpoints to verify data was stored:")
    
    # # Test GET endpoints to verify data was stored
    make_request("GET", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/cognitive-distortions")
    make_request("GET", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/tasks")
    make_request("GET", f"{BASE_URL}/sessions/{TEST_SESSION_ID}/resources")
    # make_request("GET", f"{BASE_URL}/summaries")
    # make_request("GET", f"{BASE_URL}/summaries/{TEST_SESSION_ID}")

if __name__ == "__main__":
    run_tests() 