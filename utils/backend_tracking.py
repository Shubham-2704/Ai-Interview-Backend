import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
import requests
from config.database import database

# MongoDB collections
user_tracking = database["user_tracking"]
page_views = database["page_views"]
events = database["events"]

# Google Analytics Measurement Protocol (for backend tracking)
GA_MEASUREMENT_ID = os.getenv("GA4_MEASUREMENT_ID")
GA_API_SECRET = os.getenv("GA4_API_SECRET")  # Optional: For enhanced tracking

async def track_page_view(
    request: Request,
    user_id: Optional[str] = None,
    session_id: str = None,
    page_path: str = "/",
    page_title: str = "Unknown Page",
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
    referrer: Optional[str] = None
):
    """Track page view from backend"""
    
    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Get user info
    client_ip = ip_address or request.client.host
    user_agent_str = user_agent or request.headers.get("user-agent", "unknown")
    
    # Prepare tracking data
    tracking_data = {
        "timestamp": datetime.now(timezone.utc),
        "session_id": session_id,
        "user_id": user_id,
        "page_path": page_path,
        "page_title": page_title,
        "user_agent": user_agent_str,
        "ip_address": client_ip,
        "referrer": referrer or request.headers.get("referer"),
        "method": request.method,
        "url": str(request.url)
    }
    
    # Store in MongoDB
    await page_views.insert_one(tracking_data)
    
    # Also send to Google Analytics via Measurement Protocol
    await send_to_google_analytics({
        "client_id": user_id or session_id,
        "user_id": user_id,
        "events": [{
            "name": "page_view",
            "params": {
                "page_location": page_path,
                "page_title": page_title,
                "engagement_time_msec": 1000,
                "session_id": session_id
            }
        }]
    })
    
    return session_id

async def track_event(
    user_id: Optional[str],
    session_id: str,
    event_name: str,
    event_category: str = "general",
    event_label: Optional[str] = None,
    event_value: Optional[int] = None,
    page_path: Optional[str] = None,
    additional_params: Optional[Dict] = None
):
    """Track custom event from backend"""
    
    event_data = {
        "timestamp": datetime.now(timezone.utc),
        "session_id": session_id,
        "user_id": user_id,
        "event_name": event_name,
        "event_category": event_category,
        "event_label": event_label,
        "event_value": event_value,
        "page_path": page_path,
        "additional_params": additional_params or {}
    }
    
    # Store in MongoDB
    await events.insert_one(event_data)
    
    # Send to Google Analytics
    await send_to_google_analytics({
        "client_id": user_id or session_id,
        "user_id": user_id,
        "events": [{
            "name": event_name,
            "params": {
                "event_category": event_category,
                "event_label": event_label,
                "value": event_value,
                "session_id": session_id,
                "page_location": page_path,
                **(additional_params or {})
            }
        }]
    })

async def track_user_session(
    user_id: Optional[str],
    session_id: str,
    action: str = "visit",  # visit, login, logout, activity
    data: Optional[Dict] = None
):
    """Track user session activities"""
    
    session_data = {
        "timestamp": datetime.now(timezone.utc),
        "user_id": user_id,
        "session_id": session_id,
        "action": action,
        "data": data or {},
        "user_agent": data.get("user_agent") if data else None,
        "ip_address": data.get("ip_address") if data else None
    }
    
    await database["user_tracking"].insert_one(session_data)

async def send_to_google_analytics(payload: Dict):
    """Send data to Google Analytics Measurement Protocol"""
    try:
        if not GA_MEASUREMENT_ID or GA_MEASUREMENT_ID == "G-XXXXXXXXXX":
            return  # Skip if not configured
        
        # Build endpoint
        endpoint = f"https://www.google-analytics.com/mp/collect?measurement_id={GA_MEASUREMENT_ID}"
        if GA_API_SECRET:
            endpoint += f"&api_secret={GA_API_SECRET}"
        
        # Add timestamp
        payload["timestamp_micros"] = int(datetime.now(timezone.utc).timestamp() * 1000000)
        
        # Send to GA
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=2
        )
        
        if response.status_code != 204:
            print(f"GA Tracking Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error sending to Google Analytics: {e}")
