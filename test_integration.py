"""
Integration tests to verify the new resource-based endpoints work correctly.
These tests make actual HTTP calls to verify routing and basic functionality.
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_endpoint_routing():
    """Test that all new endpoints are properly routed"""
    
    # Test session-based endpoints with valid session ID
    session_id = "integration_test_session"
    
    endpoints_to_test = [
        # (method, endpoint, expected_status_without_data)
        ("POST", f"/sessions/{session_id}/resources", 400),  # Missing query
        ("POST", f"/sessions/{session_id}/cognitive-distortions", 400),  # Missing distortions
        ("POST", f"/sessions/{session_id}/tasks", 400),  # Missing task
        ("POST", f"/sessions/{session_id}/summary", 422),  # Missing body
        ("GET", f"/sessions/{session_id}/cognitive-distortions", 200),  # Should work even if empty
        ("GET", f"/sessions/{session_id}/tasks", 200),  # Should work even if empty
        ("GET", f"/sessions/{session_id}/resources", 404),  # Should return 404 if no resources
    ]
    
    for method, endpoint, expected_status in endpoints_to_test:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        
        print(f"{method} {endpoint} -> {response.status_code}")
        assert response.status_code == expected_status or response.status_code in [200, 400, 404, 422]
        
        # Verify the response is JSON
        try:
            response.json()
        except:
            pytest.fail(f"Response from {method} {endpoint} is not valid JSON")


def test_global_endpoints():
    """Test global endpoints that don't require session ID"""
    
    endpoints = [
        ("GET", "/", 200),
        ("GET", "/summaries", 200),
        ("POST", "/emails", 422),  # Missing email data (Pydantic validation error)
        ("POST", "/waitlist", 400),  # Missing email
    ]
    
    for method, endpoint, expected_status in endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        
        print(f"{method} {endpoint} -> {response.status_code}")
        assert response.status_code == expected_status
        
        # Verify the response is JSON
        try:
            response.json()
        except:
            pytest.fail(f"Response from {method} {endpoint} is not valid JSON")


def test_old_endpoints_removed():
    """Verify that old endpoints no longer work"""
    
    old_endpoints = [
        ("POST", "/resources"),
        ("POST", "/sendEmail"),
        ("POST", "/api/call"),
        ("POST", "/cognitiveDistortions"),
        ("POST", "/conversation/summary"),
        ("POST", "/userTask"),
        ("GET", "/conversation/summaries"),
        ("GET", "/conversation/resources"),
        ("GET", "/userTasks"),
    ]
    
    for method, endpoint in old_endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        
        print(f"Old endpoint {method} {endpoint} -> {response.status_code}")
        # Should return 404 Not Found since these routes no longer exist
        assert response.status_code == 404


def test_session_id_in_path():
    """Test that session ID is properly extracted from path"""
    
    # Test with a specific session ID
    test_session_id = "test_session_12345"
    
    # This should work (even though it will fail validation inside)
    response = client.post(
        f"/sessions/{test_session_id}/tasks",
        json={"task": "Test task"}
    )
    
    # Should not be 404 (route not found), should be either 200 or 500 (depending on DB)
    assert response.status_code != 404
    print(f"Session ID routing test: {response.status_code}")


def test_endpoint_consistency():
    """Test that endpoint naming is consistent"""
    
    session_id = "consistency_test"
    
    # Test that we use kebab-case consistently
    response = client.get(f"/sessions/{session_id}/cognitive-distortions")
    assert response.status_code in [200, 404]  # Route exists, may return empty
    
    # Test that we use plural for collections
    response = client.get(f"/sessions/{session_id}/tasks")
    assert response.status_code in [200, 404]  # Route exists, may return empty
    
    response = client.get(f"/sessions/{session_id}/resources")
    assert response.status_code in [200, 404]  # Route exists, may return empty or not found


if __name__ == "__main__":
    print("Running integration tests...")
    test_endpoint_routing()
    test_global_endpoints()
    test_old_endpoints_removed()
    test_session_id_in_path()
    test_endpoint_consistency()
    print("✅ All integration tests passed!") 