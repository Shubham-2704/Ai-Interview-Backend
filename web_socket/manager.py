from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # user_id -> list of sockets (multi-tab support)
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, payload: dict):
        for ws in self.active_connections.get(user_id, []):
            await ws.send_json(payload)

    async def broadcast(self, payload: dict):
        for sockets in self.active_connections.values():
            for ws in sockets:
                await ws.send_json(payload)

manager = ConnectionManager()