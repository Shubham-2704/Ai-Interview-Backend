from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from web_socket.manager import manager
from utils.auth import decode_token

router = APIRouter(prefix="/api/notification", tags=["Notifications"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        # Decode token
        user = decode_token(token)
        if not user or "id" not in user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
            
        user_id = user["id"]
        
        # Accept connection and store
        await manager.connect(user_id, websocket)
        print(f"✅ User {user_id} connected to WebSocket")
        
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(user_id, websocket)
            print(f"❌ User {user_id} disconnected from WebSocket")
            
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")
