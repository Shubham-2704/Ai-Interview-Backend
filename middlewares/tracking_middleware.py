import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from utils.backend_tracking import track_page_view, track_user_session

class TrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip tracking for certain paths
        skip_paths = ["/api/analytics", "/health", "/metrics", "/static", "/favicon.ico"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Start timer
        start_time = time.time()
        
        # Generate session ID if not exists
        session_id = request.cookies.get("session_id") or str(uuid.uuid4())
        
        # Get user ID from auth if available
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Extract user from token (you'll need to decode JWT)
            try:
                token = auth_header.split(" ")[1]
                # Decode token to get user_id
                # user_id = decode_token(token).get("sub")
                pass
            except:
                pass
        
        # Track page view
        try:
            await track_page_view(
                request=request,
                user_id=user_id,
                session_id=session_id,
                page_path=str(request.url.path),
                page_title=f"{request.method} {request.url.path}"
            )
            
            # Track session activity
            await track_user_session(
                user_id=user_id,
                session_id=session_id,
                action="request",
                data={
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("user-agent"),
                    "ip_address": request.client.host
                }
            )
        except Exception as e:
            print(f"Tracking error: {e}")
        
        # Process request
        response = await call_next(request)
        
        # Add session ID cookie if not exists
        if not request.cookies.get("session_id"):
            response.set_cookie(
                key="session_id",
                value=session_id,
                max_age=30*24*60*60,  # 30 days
                httponly=True,
                samesite="lax"
            )
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Add tracking headers
        response.headers["X-Session-ID"] = session_id
        response.headers["X-Response-Time"] = str(round(response_time * 1000, 2))
        
        return response


