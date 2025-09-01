from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum

class MessageType(str, Enum):
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice_candidate"
    SCREEN_SHARE = "screen_share"
    MOUSE_EVENT = "mouse_event"
    KEYBOARD_EVENT = "keyboard_event"
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_RESPONSE = "connection_response"
    QUALITY_CHANGE = "quality_change"
    # New message types for connection approval
    CONNECTION_REQUEST_PENDING = "connection_request_pending"
    CONNECTION_APPROVE = "connection_approve"
    CONNECTION_REJECT = "connection_reject"

class WebRTCMessage(BaseModel):
    type: MessageType
    data: Dict[str, Any]
    target_id: Optional[str] = None
    source_id: Optional[str] = None

class MouseEvent(BaseModel):
    x: int
    y: int
    button: Optional[str] = None
    action: str

class KeyboardEvent(BaseModel):
    key: str
    action: str
    modifiers: Optional[Dict[str, bool]] = None

class ConnectionRequest(BaseModel):
    session_id: str
    password: Optional[str] = None

class ConnectionPendingRequest(BaseModel):
    client_id: str
    session_id: str
    client_info: Optional[Dict[str, str]] = None
