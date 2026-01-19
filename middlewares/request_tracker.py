import time
from fastapi import Request
from controllers.system_controller import *

async def request_tracker_middleware(request: Request, call_next):
    """Middleware to track all API requests for metrics"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        response_time_ms = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Track this request
        from controllers.system_controller import track_request
        await track_request(
            response_time_ms=response_time_ms,
            is_error=(response.status_code >= 400),
            endpoint=request.url.path
        )
        
        # Add response time header for debugging
        response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"
        
        return response
        
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        
        # Track error request
        from controllers.system_controller import track_request
        await track_request(
            response_time_ms=response_time_ms,
            is_error=True,
            endpoint=request.url.path
        )
        
        raise

# Simple endpoint for testing request tracking
async def test_tracking_endpoint():
    """Test endpoint to verify tracking is working"""
    from controllers.system_controller import _request_history
    
    return {
        "total_tracked_requests": len(_request_history),
        "recent_requests": _request_history[-10:] if _request_history else [],
        "avg_response_time": await calculate_api_response_time(),
        "error_rate": await calculate_error_rate()
    }

