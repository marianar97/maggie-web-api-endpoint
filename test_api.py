import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json
from datetime import datetime
from main import app

# Create test client
client = TestClient(app)

# Test data
test_session_id = "test_session_123"
test_summary_id = "summary_456"


class TestSessionCalls:
    """Test session call endpoints"""
    
    @patch('main.get_payload')
    @patch('httpx.AsyncClient')
    def test_create_session_call_success(self, mock_client, mock_get_payload):
        """Test POST /sessions/{session_id}/calls"""
        # Mock the payload
        mock_get_payload.return_value = {"test": "payload"}
        
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"joinUrl": "https://test.com/join"}
        mock_response.text = '{"joinUrl": "https://test.com/join"}'
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch.dict('os.environ', {'ULTRAVOX_API_KEY': 'test_key'}):
            response = client.post(f"/sessions/{test_session_id}/calls")
        
        assert response.status_code == 200
        data = response.json()
        assert "joinUrl" in data
        assert data["joinUrl"] == "https://test.com/join"
    
    def test_create_session_call_missing_api_key(self):
        """Test POST /sessions/{session_id}/calls without API key"""
        with patch.dict('os.environ', {}, clear=True):
            response = client.post(f"/sessions/{test_session_id}/calls")
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data


class TestSessionCognitiveDistortions:
    """Test cognitive distortions endpoints"""
    
    @patch('main.db')
    def test_create_cognitive_distortions_success(self, mock_db):
        """Test POST /sessions/{session_id}/cognitive-distortions"""
        # Mock Firestore document reference
        mock_doc_ref = Mock()
        mock_doc_ref.id = "distortion_123"
        mock_collection = Mock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value.document.return_value.collection.return_value = mock_collection
        
        response = client.post(
            f"/sessions/{test_session_id}/cognitive-distortions",
            json={"cognitiveDistortions": ["catastrophizing", "all-or-nothing"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "Cognitive distortions saved successfully" in data["message"]
        assert data["distortion_id"] == "distortion_123"
    
    def test_create_cognitive_distortions_empty_list(self):
        """Test POST /sessions/{session_id}/cognitive-distortions with empty list"""
        response = client.post(
            f"/sessions/{test_session_id}/cognitive-distortions",
            json={"cognitiveDistortions": []}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "No cognitive distortions provided" in data["message"]
    
    @patch('main.db')
    def test_get_cognitive_distortions_success(self, mock_db):
        """Test GET /sessions/{session_id}/cognitive-distortions"""
        # Mock Firestore response
        mock_doc = Mock()
        mock_doc.to_dict.return_value = {
            "timestamp": "2024-01-15T10:30:00Z",
            "distortions": ["catastrophizing"]
        }
        mock_doc.id = "distortion_123"
        
        mock_stream = [mock_doc]
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = mock_stream
        
        response = client.get(f"/sessions/{test_session_id}/cognitive-distortions")
        
        assert response.status_code == 200
        data = response.json()
        assert "cognitiveDistortions" in data
        assert len(data["cognitiveDistortions"]) == 1


class TestSessionTasks:
    """Test user tasks endpoints"""
    
    @patch('main.db')
    def test_create_task_success_new_document(self, mock_db):
        """Test POST /sessions/{session_id}/tasks - creating new tasks document"""
        mock_doc_ref = Mock()
        mock_doc_ref.id = "tasks_doc"
        
        mock_doc = Mock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc
        
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        response = client.post(
            f"/sessions/{test_session_id}/tasks",
            json={"task": "Practice breathing exercises for 5 minutes daily"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "User task saved successfully" in data["message"]
        assert data["task_id"] == "tasks_doc"
    
    @patch('main.db')
    def test_create_task_append_to_existing(self, mock_db):
        """Test POST /sessions/{session_id}/tasks - appending to existing tasks"""
        mock_doc_ref = Mock()
        mock_doc_ref.id = "tasks_doc"
        
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "timestamp": "2024-01-15T10:30:00Z",
            "tasks": ["Existing task"]
        }
        mock_doc_ref.get.return_value = mock_doc
        
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        response = client.post(
            f"/sessions/{test_session_id}/tasks",
            json={"task": "New task"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "User task saved successfully" in data["message"]
    
    def test_create_task_missing_task(self):
        """Test POST /sessions/{session_id}/tasks with missing task"""
        response = client.post(
            f"/sessions/{test_session_id}/tasks",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "No task provided" in data["message"]
    
    @patch('main.db')
    def test_get_tasks_success(self, mock_db):
        """Test GET /sessions/{session_id}/tasks"""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "timestamp": "2024-01-15T10:30:00Z",
            "tasks": ["Practice breathing exercises", "Journal daily"]
        }
        mock_doc.id = "tasks_doc"
        
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.get(f"/sessions/{test_session_id}/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert "userTasks" in data
        assert len(data["userTasks"]) == 1
        assert data["userTasks"][0]["tasks"] == ["Practice breathing exercises", "Journal daily"]


class TestSessionSummary:
    """Test session summary endpoints"""
    
    @patch('main.db')
    def test_create_summary_success(self, mock_db):
        """Test POST /sessions/{session_id}/summary"""
        mock_doc_ref = Mock()
        mock_doc_ref.id = "summary_doc"
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        response = client.post(
            f"/sessions/{test_session_id}/summary",
            json={
                "conversationSummary": "User discussed anxiety about work presentations",
                "identifiedCognitiveDistortions": ["catastrophizing"],
                "suggestedExercises": "Practice progressive muscle relaxation"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "Conversation summary saved successfully" in data["message"]
        assert data["summary_id"] == "summary_doc"


class TestSessionResources:
    """Test session resources endpoints"""
    
    @patch('main.Exa')
    @patch('main.db')  
    def test_create_session_resources_success(self, mock_db, mock_exa_class):
        """Test POST /sessions/{session_id}/resources"""
        # Mock Exa API
        mock_exa_instance = Mock()
        mock_result = Mock()
        mock_result.results = [
            Mock(
                url="https://example.com",
                title="Test Title",
                text="Test content",
                image="https://example.com/image.jpg",
                favicon=None
            )
        ]
        mock_exa_instance.search_and_contents.return_value = mock_result
        mock_exa_class.return_value = mock_exa_instance
        
        # Mock Firestore
        mock_doc_ref = Mock()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        with patch.dict('os.environ', {'EXA_API_KEY': 'test_key'}):
            response = client.post(
                f"/sessions/{test_session_id}/resources",
                json={"query": "anxiety management techniques"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Resources created successfully" in data["message"]
    
    def test_create_session_resources_missing_query(self):
        """Test POST /sessions/{session_id}/resources with missing query"""
        response = client.post(
            f"/sessions/{test_session_id}/resources",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "No query provided" in data["message"]
    
    def test_create_session_resources_empty_session_id(self):
        """Test POST /sessions/{session_id}/resources with empty session ID"""
        response = client.post(
            "/sessions//resources",
            json={"query": "test"}
        )
        
        # FastAPI returns 404 for empty path parameter (route doesn't match)
        assert response.status_code == 404
    
    @patch('main.db')
    def test_get_resources_success(self, mock_db):
        """Test GET /sessions/{session_id}/resources"""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "timestamp": "2024-01-15T10:30:00Z",
            "resources": [
                {
                    "url": "https://example.com",
                    "title": "Anxiety Management",
                    "text": "Helpful techniques for managing anxiety",
                    "image": "https://example.com/image.jpg"
                }
            ]
        }
        mock_doc.id = "resources_doc"
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.get(f"/sessions/{test_session_id}/resources")
        
        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert data["id"] == "resources_doc"
    
    @patch('main.db')
    def test_get_resources_not_found(self, mock_db):
        """Test GET /sessions/{session_id}/resources when no resources exist"""
        mock_doc = Mock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.get(f"/sessions/{test_session_id}/resources")
        
        assert response.status_code == 404
        data = response.json()
        assert "No resources found" in data["message"]


class TestGlobalEndpoints:
    """Test global (non-session specific) endpoints"""
    
    def test_root_endpoint(self):
        """Test GET /"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello, World!"
    
    @patch('main.db')
    def test_get_all_summaries(self, mock_db):
        """Test GET /summaries"""
        # Mock session documents
        mock_session_docs = []
        for i in range(3):
            mock_session_doc = Mock()
            mock_session_doc.id = f"session_{i}"
            mock_session_docs.append(mock_session_doc)
        
        # Set up the collection chain properly
        mock_sessions_collection = Mock()
        mock_sessions_collection.stream.return_value = mock_session_docs
        
        # Mock get() for each summary document
        mock_summary_docs = []
        for i in range(3):
            mock_summary_doc = Mock()
            mock_summary_doc.exists = True
            mock_summary_doc.to_dict.return_value = {
                "timestamp": f"2024-01-{15+i}T10:30:00Z",
                "summary": f"Summary {i}",
                "cognitiveDistortions": ["catastrophizing"],
                "suggestedExercises": f"Exercise {i}"
            }
            mock_summary_docs.append(mock_summary_doc)
        
        # Set up the mock to return sessions collection first, then individual summary docs
        call_count = 0
        def mock_collection(*args):
            nonlocal call_count
            if args[0] == "sessions" and call_count == 0:
                call_count += 1
                return mock_sessions_collection
            else:
                # This is for getting individual summaries
                mock_doc = Mock()
                mock_doc.collection.return_value.document.return_value.get.return_value = mock_summary_docs[call_count - 1] if call_count <= 3 else Mock(exists=False)
                call_count += 1
                return Mock(document=Mock(return_value=mock_doc))
        
        mock_db.collection.side_effect = mock_collection
        
        response = client.get("/summaries")
        
        assert response.status_code == 200
        data = response.json()
        assert "summaries" in data
        assert len(data["summaries"]) == 3
    
    @patch('main.db')
    def test_get_specific_summary(self, mock_db):
        """Test GET /summaries/{summary_id}"""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "timestamp": "2024-01-15T10:30:00Z",
            "summary": "Test summary",
            "cognitiveDistortions": ["catastrophizing"],
            "suggestedExercises": "Test exercise"
        }
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.get(f"/summaries/{test_summary_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_summary_id
        assert data["summary"] == "Test summary"
    
    @patch('main.db')
    def test_get_summary_not_found(self, mock_db):
        """Test GET /summaries/{summary_id} when summary doesn't exist"""
        mock_doc = Mock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        
        response = client.get(f"/summaries/{test_summary_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "Summary not found" in data["error"]
    
    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_success(self, mock_smtp):
        """Test POST /emails"""
        # Mock SMTP server
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        with patch.dict('os.environ', {
            'EMAIL_ADDRESS': 'test@example.com',
            'EMAIL_PASSWORD': 'test_password'
        }):
            response = client.post(
                "/emails",
                json={
                    "email_address": "user@example.com",
                    "insights": {
                        "summary": "User made progress",
                        "tasks": ["Practice breathing", "Journal daily"],
                        "topics": ["anxiety", "stress"]
                    }
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "Email sent successfully" in data["message"]
    
    @patch('main.db')
    def test_add_to_waitlist(self, mock_db):
        """Test POST /waitlist"""
        mock_doc_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        response = client.post(
            "/waitlist",
            json={"email": "user@example.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "User added to waitlist successfully" in data["message"]


class TestErrorHandling:
    """Test error handling across endpoints"""
    
    def test_empty_session_id(self):
        """Test endpoints with empty session ID"""
        response = client.post(
            "/sessions//tasks",
            json={"task": "test task"}
        )
        # FastAPI returns 404 for empty path parameter (route doesn't match)
        assert response.status_code == 404
    
    def test_malformed_json(self):
        """Test endpoints with malformed JSON"""
        response = client.post(
            f"/sessions/{test_session_id}/tasks",
            content="invalid json",
            headers={"content-type": "application/json"}
        )
        
        # When JSON parsing fails inside the endpoint, it returns 500
        assert response.status_code == 500
    
    @patch('main.db')
    def test_database_error_handling(self, mock_db):
        """Test handling of database errors"""
        mock_db.collection.side_effect = Exception("Database connection failed")
        
        response = client.post(
            f"/sessions/{test_session_id}/tasks",
            json={"task": "test task"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to save user task" in data["message"]


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v"]) 