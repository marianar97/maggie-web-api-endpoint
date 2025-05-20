import os
import smtplib
import ssl

from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
import httpx
import json
from datetime import datetime
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from payload import get_payload




app = FastAPI()
SESSION_ID = ""

# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firestore database
cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./firebase-key.json"))
firebase_app = firebase_admin.initialize_app(cred)
db = firestore.client()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://maggieweb.vercel.app", "http://localhost:8080"],  # Update if your frontend runs elsewhere
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

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.post("/api/ultravox")
async def create_ultravox_call(request: Request):
    global SESSION_ID
    SESSION_ID = request.headers.get("x-session-id")
    api_key = os.getenv("ULTRAVOX_API_KEY")
    if not api_key:
        logger.info("Ultravox API key not configured")
        return JSONResponse(
            content={"error": "Error, please try again later"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    try:
        payload = get_payload("Mariana")
        # logger.info("payload", payload)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.ultravox.ai/api/calls",
                headers={
                    "Content-Type": "application/json",
                    "X-Unsafe-API-Key": api_key,
                },
                json=payload,
            )
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
                content={"error": "Failed to create Ultravox call", "details": error_text},
                status_code=response.status_code
            )
    except Exception as e:
        return JSONResponse(
            content={"error": "Internal server error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 

@app.post("/conversation/summary")
async def send_conversation_summary(request: Request):
    # logger.info("in conversation summary")
    """
    Endpoint handler for the summarizeConversation tool.
    Receives and processes conversation summaries from Maggie.
    """
    try:
        # Parse the request body
        body = await request.json()
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
        
        # Save the summary to Firestore with a fixed document name
        doc_ref = db.collection("summaries").document(SESSION_ID)
        doc_ref.set(summary)
        
        # Return a success response
        # logger.info("Summary saved to Firestore:", summary)
        
        return {
            "message": "Conversation summary saved successfully. Continue the conversation with the user.",
            "summary_id": doc_ref.id
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

@app.get("/conversation/summaries")
async def get_conversation_summaries():
    """
    Endpoint to retrieve all conversation summaries from Firestore.
    """
    try:
        # Get all documents from the summaries collection
        summaries_ref = db.collection("summaries")
        docs = summaries_ref.stream()
        
        # Convert to list of dictionaries
        summaries = []
        for doc in docs:
            summary = doc.to_dict()
            summary["id"] = doc.id
            summaries.append(summary)
        
        # Sort by timestamp (most recent first)
        summaries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {"summaries": summaries}
        
    except Exception as e:
        logger.info(f"Error retrieving conversation summaries: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/conversation/summary/{summary_id}")
async def get_conversation_summary(summary_id: str):
    """
    Endpoint to retrieve a specific conversation summary from Firestore.
    """
    try:
        # Get the document with the given ID
        doc_ref = db.collection("summaries").document(summary_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return JSONResponse(
                content={"error": "Summary not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Convert to dictionary and add the ID
        summary = doc.to_dict()
        summary["id"] = doc.id
        
        return summary
        
    except Exception as e:
        logger.info(f"Error retrieving conversation summary: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 

@app.post("/cognitiveDistortions")
async def add_cognitive_distortions(request: Request):
    """
    Endpoint handler for the cognitiveDistortions tool.
    Receives cognitive distortions and the session id and stores them in Firestore.
    """
    try:
        # Parse the request body
        body = await request.json()
        # logger.info("Received cognitive distortions:", body)
        
        # Extract the cognitive distortions
        cognitive_distortions = body.get("cognitiveDistortions", [])
        
        if not cognitive_distortions:
            return JSONResponse(
                content={"message": "No cognitive distortions provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create a timestamped distortions object
        distortion_data = {
            "timestamp": datetime.now().isoformat(),
            "distortions": cognitive_distortions
        }
        
        # Save to Firestore in the "CognitiveDistortions" collection
        doc_ref = db.collection("cognitiveDistortions").document(SESSION_ID)
        doc_ref.set(distortion_data)
        
        # logger.info(f"Cognitive distortions saved to Firestore: {distortion_data}")
        
        return {
            "message": "Cognitive distortions saved successfully. Continue the conversation with the user.",
            "distortion_id": doc_ref.id
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

@app.get("/cognitiveDistortions/{session_id}")
async def get_cognitive_distortions(session_id: str):
    """
    Endpoint to retrieve cognitive distortions for a specific session from Firestore.
    """
    try:
        # Get all documents from the CognitiveDistortions collection
        distortions_ref = db.collection("cognitiveDistortions").document(session_id)
        doc = distortions_ref.get()
        
        # Convert to list of dictionaries
        distortions_data = []
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            distortions_data.append(data)
        
        # Sort by timestamp (most recent first)
        distortions_data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {"cognitiveDistortions": distortions_data}
        
    except Exception as e:
        logger.info(f"Error retrieving cognitive distortions: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 

@app.post("/userTasks")
async def add_user_tasks(request: Request):
    """
    Endpoint handler for the addUserTasks tool.
    Receives and stores tasks created for the user during the conversation.
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Extract the tasks
        tasks = body.get("tasks", [])
        
        if not tasks:
            return JSONResponse(
                content={"message": "No tasks provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        
        # Create a timestamped tasks object
        tasks_data = {
            "timestamp": datetime.now().isoformat(),
            "tasks": tasks,
            "completed": [False] * len(tasks)  # Initialize all tasks as not completed
        }
        
        # Save to Firestore in the "userTasks" collection
        doc_ref = db.collection("userTasks").document(SESSION_ID)
        doc_ref.set(tasks_data)
        
        logger.info(f"User tasks saved to Firestore: {tasks_data}")
        
        return {
            "message": "User tasks saved successfully. Continue the conversation with the user.",
            "task_id": doc_ref.id
        }
        
    except Exception as e:
        logger.info(f"Error saving user tasks: {str(e)}")
        return JSONResponse(
            content={
                "message": "Failed to save user tasks. You can still continue the conversation with the user.",
                "error": str(e)
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.get("/userTasks")
async def get_user_tasks(request: Request):
    """
    Endpoint to retrieve all user tasks from Firestore.
    """
    try:
        # Parse the request body
        if not SESSION_ID:
            return JSONResponse(
                content={"message": "No session id provided"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all documents from the userTasks collection
        tasks_ref = db.collection("userTasks").document(SESSION_ID)
        doc = tasks_ref.get()
        
        # Convert to list of dictionaries
        tasks_data = []
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            tasks_data.append(data)
        
        # Sort by timestamp (most recent first)
        tasks_data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {"userTasks": tasks_data}
        
    except Exception as e:
        logger.info(f"Error retrieving user tasks: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@app.post("/sendEmail")
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

