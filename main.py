import os
import smtplib
import ssl
from typing import List, Optional

from fastapi import FastAPI, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from exa_py import Exa

from payload import get_payload




app = FastAPI()


# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firestore database
cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./firebase-key.json"))
firebase_app = firebase_admin.initialize_app(cred)
db = firestore.client()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://maggieweb.vercel.app", "http://localhost:8080", "http://localhost:5173", "https://www.trymaggie.site"],  # Update if your frontend runs elsewhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Insights(BaseModel):
    summary: str
    tasks: list[str]
    topics: list[str]

class Email(BaseModel):
    email_address: str
    insights: Insights

class Resource(BaseModel):
    url: str
    title: str
    text: str
    image: Optional[str] = None


def parse_results(data:List[dict]) -> List[Resource]:
    results = []
    for result in data:
        title = result.title.strip()
        text = result.text.strip()
        text = text.lstrip('\n')
        image = None
        if hasattr(result, 'image'):
            image = result.image
        elif hasattr(result, 'favicon'):
            image = result.favicon
        results.append(Resource(
                url = result.url,
                title = title,
                text = text,
                image = image
        ))
    return results

def fetch_and_store_resources(query: str, session_id: str) -> List[Resource]:
    if not session_id:
        logger.error("No session ID provided for storing resources")
        return []
        
    exa = Exa(api_key = os.getenv("EXA_API_KEY"))
    result = exa.search_and_contents(
        query,
        text = True,
        type = "auto",
        num_results = 2
    )
    data = result.results
    if not data:
        logger.error("No websites found")
        return []
    
    resources = parse_results(data)
    
    # Store all resources in a single document under sessions/{session_id}/resources/
    if resources:
        try:
            doc_ref = db.collection("sessions").document(session_id).collection("resources").document("resources_doc")
            resource_data = {
                "timestamp": datetime.now().isoformat(),
                "resources": [resource.model_dump() for resource in resources]  # Store as array
            }
            doc_ref.set(resource_data)
            logger.info(f"Successfully stored {len(resources)} resources for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to store resources in Firestore: {str(e)}")
    
    return resources

@app.post("/sessions/resources")
async def create_session_resources(request: Request, background_tasks: BackgroundTasks):
    # Parse the request body first
    body = await request.json()
    
    # Extract session_id from body
    session_id = body.get("session_id", "")
    
    if not session_id:
        return JSONResponse(
            content={"message": "No session ID provided"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
        
    query = body.get("query", "")
    if not query:
        return JSONResponse(
            content={"message": "No query provided"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    background_tasks.add_task(fetch_and_store_resources, query, session_id)
    return {
        "message": "Resources created successfully. Continue the conversation with the user.",
        "status": "success",
        "status_code": status.HTTP_200_OK
    }
    
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.post("/emails")
async def send_email(email: Email):
    """
    Sends an email to the user about the insights of the conversation
    
        Args:
            email_address: The users's email address
            
        Returns:
            A confirmation message
        """
    email_address = email.email_address
    insights = email.insights

    if not email_address:
        logger.error("No email address provided")
        return JSONResponse(
            content={"message": "No email address provided"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    if not insights:
        logger.error("No insights provided")
        return JSONResponse(
            content={"message": "No insights provided"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    sender_email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    
    # Check if email credentials are configured
    if not sender_email or not password:
        logger.error("Email credentials not configured")
        return JSONResponse(
            content={"message": "Email service not properly configured"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Create a properly formatted email message with headers
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email_address
    msg['Subject'] = "Your Insights from Maggie"
    
    # Format the email body with better presentation
    email_body = f"""
    Hey there,

    Here are the insights of the conversation:
    
    Summary:
    {insights.summary}
    
    Tasks:
    {chr(10).join(f"- {task}" for task in insights.tasks)}
    
    Cognitive Distortions:
    {", ".join(insights.topics)}
    
    We hope Maggie was useful to your wellbeing journey.

    Sincerely,
    The Maggie Team
    """
    
    msg.attach(MIMEText(email_body, 'plain'))

    smtp_server = "smtp.gmail.com"
    port = 465  # For SSL

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(sender_email, password)
            server.send_message(msg)
        logger.info(f"Email sent to {email_address}")
        return JSONResponse(
            content={"message": "Email sent successfully"},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to send email: {error_msg}")
        return JSONResponse(
            content={"message": f"Failed to send email: {error_msg}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.post("/sessions/{session_id}/calls")
async def create_session_call(session_id: str, request: Request):
    logger.info(f"Received Ultravox request with session_id: {session_id}")
    
    if not session_id:
        logger.error("No session ID provided in request")
        return JSONResponse(
            content={"message": "No session ID provided"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
        
    api_key = os.getenv("ULTRAVOX_API_KEY")
    if not api_key:
        logger.error("Ultravox API key not configured in environment variables")
        return JSONResponse(
            content={"error": "Error, please try again later"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    try:
        payload = get_payload(session_id)
        logger.info(f"Generated payload for session {session_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.ultravox.ai/api/calls",
                headers={
                    "Content-Type": "application/json",
                    "X-Unsafe-API-Key": api_key,
                },
                json=payload,
            )
            logger.info(f"Ultravox API response status: {response.status_code}")
            logger.info(f"Ultravox API response body: {response.text}")
        try:
            data = response.json()
            # logger.info("data", data)
        except Exception:
            data = None
        if data and "joinUrl" in data:
            return {"joinUrl": data["joinUrl"]}
        else:
            error_text = response.text
            # logger.info(f"Ultravox API error: {error_text}")
            return JSONResponse(
                content={"error": "Failed to create call", "details": error_text},
                status_code=response.status_code
            )
    except Exception as e:
        return JSONResponse(
            content={"error": "Internal server error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 

@app.post("/sessions/cognitive-distortions")
async def add_session_cognitive_distortions(request: Request):
    """
    Endpoint handler for the cognitiveDistortions tool.
    Receives cognitive distortions and the session id and stores them in Firestore.
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Extract session_id from body
        session_id = body.get("session_id", "")
        
        if not session_id:
            return JSONResponse(
                content={"message": "No session ID provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        # logger.info("Received cognitive distortions:", body)
        
        # Extract the cognitive distortions
        cognitive_distortions = body.get("cognitiveDistortions", [])
        
        if not cognitive_distortions:
            return JSONResponse(
                content={"message": "No cognitive distortions provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get reference to the document under sessions/{session_id}/cognitive-distortions/distortions_doc
        doc_ref = db.collection("sessions").document(session_id).collection("cognitive-distortions").document("distortions_doc")
        doc = doc_ref.get()
        
        # Check if document already exists
        if doc.exists:
            # Document exists, append to existing distortions list
            existing_data = doc.to_dict()
            existing_distortions = existing_data.get("distortions", [])
            existing_distortions.extend(cognitive_distortions)
            
            distortion_data = {
                "timestamp": datetime.now().isoformat(),
                "distortions": existing_distortions
            }
            doc_ref.update(distortion_data)
        else:
            # Document doesn't exist, create new with distortions list
            distortion_data = {
                "timestamp": datetime.now().isoformat(),
                "distortions": cognitive_distortions
            }
            doc_ref.set(distortion_data)
        
        # logger.info(f"Cognitive distortions saved to Firestore: {distortion_data}")
        
        return {
            "message": "Cognitive distortions saved successfully. Continue the conversation with the user.",
            "distortion_id": doc_ref.id,
            "status": "success",
            "status_code": status.HTTP_200_OK
        }
        
    except Exception as e:
        logger.info(f"Error saving cognitive distortions: {str(e)}")
        return JSONResponse(
            content={
                "message": "Failed to save cognitive distortions. You can still continue the conversation with the user.",
                "error": str(e)
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.post("/sessions/summary")
async def create_session_summary(request: Request):
    # logger.info("in conversation summary")
    """
    Endpoint handler for the summarizeConversation tool.
    Receives and processes conversation summaries from Maggie.
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Extract session_id from body
        session_id = body.get("session_id", "")
        
        if not session_id:
            return JSONResponse(
                content={"message": "No session ID provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        # Extract the data
        conversation_summary = body.get("conversationSummary", "")
        identified_distortions = body.get("identifiedCognitiveDistortions", [])
        suggested_exercises = body.get("suggestedExercises", "")
        
        # Create a timestamped summary object
        summary = {
            "timestamp": datetime.now().isoformat(),
            "summary": conversation_summary,
            "cognitiveDistortions": identified_distortions,
            "suggestedExercises": suggested_exercises
        }
        
        # Save the summary to Firestore under sessions/{session_id}/summaries/
        doc_ref = db.collection("sessions").document(session_id).collection("summaries").document("summary_doc")
        doc_ref.set(summary)
        
        # Return a success response
        # logger.info("Summary saved to Firestore:", summary)
        
        return {
            "message": "Conversation summary saved successfully. Continue the conversation with the user.",
            "summary_id": doc_ref.id,
            "status": "success",
            "status_code": status.HTTP_200_OK
        }
        
    except Exception as e:
        logger.info(f"Error saving conversation summary: {str(e)}")
        return JSONResponse(
            content={
                "message": "Failed to save conversation summary. You can still continue the conversation with the user.",
                "error": str(e)
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.post("/sessions/tasks")
async def create_session_task(request: Request):
    """
    Endpoint handler for the addUserTasks tool.
    Receives and stores tasks created for the user during the conversation.
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Extract session_id from body
        session_id = body.get("session_id", "")
        
        if not session_id:
            return JSONResponse(
                content={"message": "No session ID provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        # Extract the tasks
        task = body.get("task", "")
        
        if not task:
            return JSONResponse(
                content={"message": "No task provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get reference to the document under sessions/{session_id}/tasks/
        doc_ref = db.collection("sessions").document(session_id).collection("tasks").document("tasks_doc")
        doc = doc_ref.get()
        
        # Check if document already exists
        if doc.exists:
            # Document exists, append to existing tasks list
            existing_data = doc.to_dict()
            existing_tasks = existing_data.get("tasks", [])
            existing_tasks.append(task)
            
            tasks_data = {
                "timestamp": datetime.now().isoformat(),
                "tasks": existing_tasks
            }
            doc_ref.update(tasks_data)
        else:
            # Document doesn't exist, create new with tasks list
            tasks_data = {
                "timestamp": datetime.now().isoformat(),
                "tasks": [task]
            }
            doc_ref.set(tasks_data)
        
        logger.info(f"User tasks saved to Firestore: {tasks_data}")
        
        return {
            "message": "User task saved successfully. Continue the conversation with the user.",
            "task_id": doc_ref.id,
            "status": "success",
            "status_code": status.HTTP_200_OK
        }
        
    except Exception as e:
        logger.info(f"Error saving user task: {str(e)}")
        return JSONResponse(
            content={
                "message": "Failed to save user task. You can still continue the conversation with the user.",
                "error": str(e)
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/summaries")
async def get_all_summaries():
    """
    Endpoint to retrieve all conversation summaries from Firestore.
    """
    try:
        # Get all session documents first, then their summaries
        sessions_ref = db.collection("sessions")
        session_docs = sessions_ref.stream()
        
        # Convert to list of dictionaries
        summaries = []
        for session_doc in session_docs:
            session_id = session_doc.id
            # Get the summary for this session
            summary_ref = db.collection("sessions").document(session_id).collection("summaries").document("summary_doc")
            summary_doc = summary_ref.get()
            if summary_doc.exists:
                summary = summary_doc.to_dict()
                summary["id"] = session_id  # Use session_id as the summary id
                summary["session_id"] = session_id
                summaries.append(summary)
        
        # Sort by timestamp (most recent first)
        def safe_timestamp_sort(item):
            timestamp = item.get("timestamp", "")
            if hasattr(timestamp, 'isoformat'):
                # If it's a datetime object, convert to string
                return timestamp.isoformat()
            return str(timestamp)
        
        summaries.sort(key=safe_timestamp_sort, reverse=True)
        
        return {"summaries": summaries}
        
    except Exception as e:
        logger.info(f"Error retrieving conversation summaries: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/summaries/{summary_id}")
async def get_summary(summary_id: str):
    """
    Endpoint to retrieve a specific conversation summary from Firestore.
    """
    try:
        # Get the document with the given ID from sessions/{summary_id}/summaries/summary_doc
        doc_ref = db.collection("sessions").document(summary_id).collection("summaries").document("summary_doc")
        doc = doc_ref.get()
        
        if not doc.exists:
            return JSONResponse(
                content={"error": "Summary not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Convert to dictionary and add the ID
        summary = doc.to_dict()
        summary["id"] = summary_id
        summary["session_id"] = summary_id
        
        return summary
        
    except Exception as e:
        logger.info(f"Error retrieving conversation summary: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/sessions/{session_id}/cognitive-distortions")
async def get_session_cognitive_distortions(session_id: str):
    """
    Endpoint to retrieve cognitive distortions for a specific session from Firestore.
    """
    try:
        # Get all documents from the sessions/{session_id}/cognitiveDistortions/ collection
        distortions_ref = db.collection("sessions").document(session_id).collection("cognitiveDistortions")
        docs = distortions_ref.stream()
        
        # Convert to list of dictionaries
        distortions_data = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            distortions_data.append(data)
        
        # Sort by timestamp (most recent first)
        def safe_timestamp_sort(item):
            timestamp = item.get("timestamp", "")
            if hasattr(timestamp, 'isoformat'):
                return timestamp.isoformat()
            return str(timestamp)
        
        distortions_data.sort(key=safe_timestamp_sort, reverse=True)
        
        return {"cognitiveDistortions": distortions_data}
        
    except Exception as e:
        logger.info(f"Error retrieving cognitive distortions: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/sessions/{session_id}/tasks")
async def get_session_tasks(session_id: str):
    """
    Endpoint to retrieve all user tasks from Firestore.
    """
    try:
        if not session_id:
            return JSONResponse(
                content={"message": "No session ID provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the document from sessions/{session_id}/tasks/tasks_doc
        tasks_ref = db.collection("sessions").document(session_id).collection("tasks").document("tasks_doc")
        doc = tasks_ref.get()
        
        # Convert to list of dictionaries
        tasks_data = []
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            data["session_id"] = session_id
            tasks_data.append(data)
        
        # Sort by timestamp (most recent first)
        def safe_timestamp_sort(item):
            timestamp = item.get("timestamp", "")
            if hasattr(timestamp, 'isoformat'):
                return timestamp.isoformat()
            return str(timestamp)
        
        tasks_data.sort(key=safe_timestamp_sort, reverse=True)
        
        return {"userTasks": tasks_data}
        
    except Exception as e:
        logger.info(f"Error retrieving user tasks: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/sessions/{session_id}/resources")
async def get_session_resources(session_id: str):
    """
    Endpoint to retrieve resources for the current session from Firestore.
    """
    try:
        if not session_id:
            return JSONResponse(
                content={"message": "No session ID provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the document from sessions/{session_id}/resources/resources_doc
        doc_ref = db.collection("sessions").document(session_id).collection("resources").document("resources_doc")
        doc = doc_ref.get()
        
        if not doc.exists:
            return JSONResponse(
                content={"message": "No resources found for this session"},
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Convert to dictionary and add the ID
        resources_data = doc.to_dict()
        resources_data["id"] = doc.id
        resources_data["session_id"] = session_id
        
        return resources_data
        
    except Exception as e:
        logger.info(f"Error retrieving resources: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post("/waitlist")
async def add_to_waitlist(request: Request):
    """
    Endpoint to add a user to the waitlist.
    """
    try:
        body = await request.json()
        email = body.get("email", "")
        if not email:
            return JSONResponse(
                content={"message": "No email provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        doc_ref = db.collection("waitlist").document(email)
        doc_ref.set({"email": email, "timestamp": datetime.now().isoformat()})
        return JSONResponse(
            content={"message": "User added to waitlist successfully"},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.info(f"Error adding user to waitlist: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )