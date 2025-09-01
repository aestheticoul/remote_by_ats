from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import uuid
import asyncio
from models import WebRTCMessage, MessageType

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sessions: Dict[str, Dict[str, str]] = {}
        self.pending_connections: Dict[str, Dict[str, str]] = {}  # New: track pending requests
        
    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        print(f"New connection: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            print(f"Connection removed: {connection_id}")
        
        # Clean up sessions
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if session.get("host_id") == connection_id or session.get("client_id") == connection_id:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            print(f"Session removed: {session_id}")
            del self.sessions[session_id]
            
        # Clean up pending connections
        pending_to_remove = []
        for pending_id, pending in self.pending_connections.items():
            if pending.get("client_id") == connection_id or pending.get("host_id") == connection_id:
                pending_to_remove.append(pending_id)
                
        for pending_id in pending_to_remove:
            del self.pending_connections[pending_id]
    
    async def send_personal_message(self, message: dict, connection_id: str):
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message))
                if message.get("type") != "screen_frame":
                    print(f"Message sent to {connection_id}: {message.get('type')}")
            except Exception as e:
                print(f"Failed to send message to {connection_id}: {e}")
        else:
            print(f"Connection {connection_id} not found in active connections")
    
    async def create_session(self, host_id: str) -> str:
        session_id = str(uuid.uuid4())[:8]
        self.sessions[session_id] = {
            "host_id": host_id, 
            "client_id": None,
            "status": "waiting"  # New: track session status
        }
        print(f"Session created: {session_id} for host: {host_id}")
        return session_id
    
    async def request_join_session(self, session_id: str, client_id: str, client_info: dict = None) -> str:
        """Create a pending connection request"""
        if session_id not in self.sessions:
            return None
            
        pending_id = str(uuid.uuid4())[:8]
        self.pending_connections[pending_id] = {
            "session_id": session_id,
            "client_id": client_id,
            "host_id": self.sessions[session_id]["host_id"],
            "client_info": client_info or {},
            "status": "pending"
        }
        
        print(f"Pending connection created: {pending_id} for session {session_id}")
        return pending_id
    
    async def approve_connection(self, pending_id: str) -> bool:
        """Approve a pending connection request"""
        if pending_id not in self.pending_connections:
            return False
            
        pending = self.pending_connections[pending_id]
        session_id = pending["session_id"]
        client_id = pending["client_id"]
        
        if session_id in self.sessions and not self.sessions[session_id]["client_id"]:
            self.sessions[session_id]["client_id"] = client_id
            self.sessions[session_id]["status"] = "connected"
            
            # Clean up pending request
            del self.pending_connections[pending_id]
            
            print(f"Connection approved: {client_id} joined session {session_id}")
            return True
            
        return False
    
    async def reject_connection(self, pending_id: str) -> bool:
        """Reject a pending connection request"""
        if pending_id not in self.pending_connections:
            return False
            
        pending = self.pending_connections[pending_id]
        
        # Clean up pending request
        del self.pending_connections[pending_id]
        
        print(f"Connection rejected for pending request: {pending_id}")
        return True
    
    async def join_session(self, session_id: str, client_id: str) -> bool:
        """Direct join (for backward compatibility)"""
        if session_id in self.sessions and not self.sessions[session_id]["client_id"]:
            self.sessions[session_id]["client_id"] = client_id
            self.sessions[session_id]["status"] = "connected"
            print(f"Client {client_id} joined session {session_id}")
            return True
        return False
    
    async def relay_message(self, message: WebRTCMessage, sender_id: str):
        session_id = None
        target_id = None
        
        for sid, session in self.sessions.items():
            if session["host_id"] == sender_id:
                target_id = session["client_id"]
                session_id = sid
                break
            elif session["client_id"] == sender_id:
                target_id = session["host_id"]
                session_id = sid
                break
        
        if target_id and target_id in self.active_connections:
            message.source_id = sender_id
            message.target_id = target_id
            await self.send_personal_message(message.dict(), target_id)
            print(f"Relayed {message.type} from {sender_id} to {target_id}")
        else:
            print(f"Could not relay message from {sender_id} - target not found")

manager = ConnectionManager()
