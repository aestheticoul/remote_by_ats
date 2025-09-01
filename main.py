from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import json
import asyncio
import logging
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Import system control libraries
import pyautogui
import time

# Import your modules
from websocket_manager import manager
from screen_capture import screen_capture
from models import WebRTCMessage, MessageType, MouseEvent, KeyboardEvent
from config import settings

# ✅ FIX: Handle pyautogui for headless environment
pyautogui = None
try:
    # Set display for headless environment
    if os.getenv('ENVIRONMENT') == 'production':
        os.environ['DISPLAY'] = ':99'  # Virtual display
    
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.01
    logger.info("✅ PyAutoGUI loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ PyAutoGUI not available: {e}")
    logger.info("Running in headless mode - mouse/keyboard control disabled")
    pyautogui = None

app = FastAPI(
    title="Remote Desktop WebApp",
    description="Professional Remote Desktop Application",
    version="1.0.0",
    debug=settings.DEBUG,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*.onrender.com", "localhost", "127.0.0.1"]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


app = FastAPI(title="Remote Desktop WebApp - AnyDesk Clone")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="static")

# Health check endpoint (required by Render)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "service": "Remote Desktop WebApp",
        "features": ["Screen Sharing", "Mouse Control", "Keyboard Control"],
        "active_connections": len(manager.active_connections),
        "active_sessions": len(manager.sessions)
    }

# Add startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Remote Desktop WebApp starting up on Render")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Port: {settings.PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Remote Desktop WebApp shutting down")
    try:
        screen_capture.stop_streaming()
    except Exception as e:
        logger.error(f"Error stopping screen capture: {e}")

@app.get("/", response_class=HTMLResponse)
async def get_landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/host", response_class=HTMLResponse)
async def get_host_page(request: Request):
    return templates.TemplateResponse("host.html", {"request": request})

@app.get("/client", response_class=HTMLResponse)
async def get_client_page(request: Request):
    return templates.TemplateResponse("client.html", {"request": request})

def execute_mouse_event(mouse_data):
    """Execute actual mouse actions with proper coordinate mapping"""

    if pyautogui is None:
        logger.info("🖱️ Mouse event simulated (headless mode)")
        return True
    try:
        # Get coordinates from client
        canvas_x = int(mouse_data.get('x', 0))
        canvas_y = int(mouse_data.get('y', 0))
        button = mouse_data.get('button', 'left')
        action = mouse_data.get('action', 'move')
        
        # Get actual screen dimensions
        actual_screen_width, actual_screen_height = pyautogui.size()
        
        # Get canvas dimensions (scaled frame size)
        canvas_width = screen_capture.actual_screen_width * screen_capture.scale_factor if hasattr(screen_capture, 'actual_screen_width') and screen_capture.scale_factor else actual_screen_width
        canvas_height = screen_capture.actual_screen_height * screen_capture.scale_factor if hasattr(screen_capture, 'actual_screen_height') and screen_capture.scale_factor else actual_screen_height
        
        # Calculate coordinate mapping from canvas to actual screen
        scale_x = actual_screen_width / canvas_width
        scale_y = actual_screen_height / canvas_height
        
        # Map canvas coordinates to actual screen coordinates
        actual_x = int(canvas_x * scale_x)
        actual_y = int(canvas_y * scale_y)
        
        # Ensure coordinates are within screen bounds
        actual_x = max(0, min(actual_x, actual_screen_width - 1))
        actual_y = max(0, min(actual_y, actual_screen_height - 1))
        
        print(f"🖱️ Mouse {action}:")
        print(f"   Canvas coords: ({canvas_x}, {canvas_y})")
        print(f"   Actual coords: ({actual_x}, {actual_y})")
        print(f"   Scale: ({scale_x:.2f}, {scale_y:.2f})")
        
        if action == 'mousemove':
            pyautogui.moveTo(actual_x, actual_y, duration=0)
            
        elif action == 'mousedown':
            pyautogui.moveTo(actual_x, actual_y, duration=0)
            if button == 'left':
                pyautogui.mouseDown(button='left')
            elif button == 'right':
                pyautogui.mouseDown(button='right')
            elif button == 'middle':
                pyautogui.mouseDown(button='middle')
                
        elif action == 'mouseup':
            if button == 'left':
                pyautogui.mouseUp(button='left')
            elif button == 'right':
                pyautogui.mouseUp(button='right')
            elif button == 'middle':
                pyautogui.mouseUp(button='middle')
                
        elif action == 'click':
            pyautogui.click(actual_x, actual_y, button=button)
            
        elif action == 'doubleclick':
            pyautogui.doubleClick(actual_x, actual_y)
            
        elif action == 'wheel':
            delta_y = mouse_data.get('deltaY', 0)
            scroll_amount = int(delta_y / 120)
            if scroll_amount != 0:
                pyautogui.scroll(-scroll_amount, actual_x, actual_y)
        
        print(f"✅ Mouse {action} executed at ({actual_x}, {actual_y})")
        return True
        
    except Exception as e:
        print(f"❌ Mouse control error: {e}")
        return False

def execute_keyboard_event(keyboard_data):
    """Execute actual keyboard actions on the host computer"""
    if pyautogui is None:
        logger.info("⌨️ Keyboard event simulated (headless mode)")
        return True
    try:
        key = keyboard_data.get('key', '')
        action = keyboard_data.get('action', 'keydown')
        modifiers = keyboard_data.get('modifiers', {})
        
        print(f"⌨️ Executing keyboard {action}: '{key}' with modifiers: {modifiers}")
        
        # Only process keydown events to avoid duplicate actions
        if action != 'keydown':
            return True
        
        # Map special keys
        key_mapping = {
            'Enter': 'enter',
            'Tab': 'tab',
            'Escape': 'esc',
            'Backspace': 'backspace',
            'Delete': 'delete',
            'ArrowUp': 'up',
            'ArrowDown': 'down',
            'ArrowLeft': 'left',
            'ArrowRight': 'right',
            'Home': 'home',
            'End': 'end',
            'PageUp': 'pageup',
            'PageDown': 'pagedown',
            'Insert': 'insert',
            'CapsLock': 'capslock',
            'NumLock': 'numlock',
            'ScrollLock': 'scrolllock',
            'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4',
            'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8',
            'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12',
            ' ': 'space'
        }
        
        # Build key combination
        keys_to_press = []
        
        # Add modifier keys first
        if modifiers.get('ctrl'):
            keys_to_press.append('ctrl')
        if modifiers.get('shift'):
            keys_to_press.append('shift')
        if modifiers.get('alt'):
            keys_to_press.append('alt')
        if modifiers.get('meta'):
            keys_to_press.append('win')
        
        # Add the main key
        if key in key_mapping:
            keys_to_press.append(key_mapping[key])
        elif len(key) == 1:
            # Single character key
            keys_to_press.append(key.lower())
        else:
            # Try to use the key as-is
            keys_to_press.append(key.lower())
        
        # Execute the key combination
        if len(keys_to_press) == 1:
            # Single key
            pyautogui.press(keys_to_press[0])
        else:
            # Key combination
            pyautogui.hotkey(*keys_to_press)
        
        print(f"✅ Keyboard action executed: {'+'.join(keys_to_press)}")
        return True
        
    except Exception as e:
        print(f"❌ Keyboard control error: {e}")
        return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    print(f"🔗 WebSocket connection opened: {connection_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message = WebRTCMessage(**message_data)
            
            if message.type == MessageType.CONNECTION_REQUEST:
                if message.data.get("action") == "create_session":
                    session_id = await manager.create_session(connection_id)
                    password = message.data.get("password")
                    if password:
                        manager.sessions[session_id]["password"] = password
                    
                    response = {
                        "type": "session_created",
                        "data": {
                            "session_id": session_id,
                            "password": password if password else None
                        }
                    }
                    await manager.send_personal_message(response, connection_id)
                    print(f"📋 Session created: {session_id} by {connection_id}")
                
                elif message.data.get("action") == "join_session":
                    session_id = message.data.get("session_id")
                    provided_password = message.data.get("password")
                    
                    print(f"🔌 Client {connection_id} requesting to join session: {session_id}")
                    
                    # Check if session exists
                    if session_id not in manager.sessions:
                        response = {
                            "type": "session_join_response",
                            "data": {"success": False, "error": "Session not found", "session_id": session_id}
                        }
                        await manager.send_personal_message(response, connection_id)
                        continue
                    
                    session = manager.sessions[session_id]
                    
                    # Check password if set
                    if session.get("password") and session["password"] != provided_password:
                        response = {
                            "type": "session_join_response",
                            "data": {"success": False, "error": "Invalid password", "session_id": session_id}
                        }
                        await manager.send_personal_message(response, connection_id)
                        continue
                    
                    # Check if session is already full
                    if session.get("client_id"):
                        response = {
                            "type": "session_join_response",
                            "data": {"success": False, "error": "Session is full", "session_id": session_id}
                        }
                        await manager.send_personal_message(response, connection_id)
                        continue
                    
                    # 🆕 CREATE PENDING CONNECTION REQUEST
                    client_info = {
                        "connection_time": str(asyncio.get_event_loop().time()),
                        "user_agent": message.data.get("user_agent", "Unknown"),
                        "ip_address": "Remote Client"
                    }
                    
                    pending_id = await manager.request_join_session(session_id, connection_id, client_info)
                    
                    if pending_id:
                        # Notify HOST about the connection request
                        host_id = session["host_id"]
                        host_notification = {
                            "type": "connection_request_pending",
                            "data": {
                                "pending_id": pending_id,
                                "session_id": session_id,
                                "client_id": connection_id,
                                "client_info": client_info,
                                "message": "A client wants to connect to your session"
                            }
                        }
                        await manager.send_personal_message(host_notification, host_id)
                        
                        # Notify CLIENT that request is pending
                        client_response = {
                            "type": "connection_request_sent",
                            "data": {
                                "pending_id": pending_id,
                                "session_id": session_id,
                                "message": "Connection request sent. Waiting for host approval..."
                            }
                        }
                        await manager.send_personal_message(client_response, connection_id)
                        
                        print(f"🔔 Connection request sent to host for session {session_id}")
                    else:
                        response = {
                            "type": "session_join_response",
                            "data": {"success": False, "error": "Unable to create connection request"}
                        }
                        await manager.send_personal_message(response, connection_id)
                
                elif message.data.get("action") == "set_password":
                    session_id = message.data.get("session_id")
                    new_password = message.data.get("password")
                    
                    if session_id in manager.sessions:
                        if manager.sessions[session_id]["host_id"] == connection_id:
                            manager.sessions[session_id]["password"] = new_password
                            response = {
                                "type": "password_updated",
                                "data": {"success": True, "password": new_password}
                            }
                        else:
                            response = {
                                "type": "password_updated",
                                "data": {"success": False, "error": "Not authorized to set password"}
                            }
                        await manager.send_personal_message(response, connection_id)
                
                elif message.data.get("action") == "disconnect":
                    for session_id, session in manager.sessions.items():
                        if session.get("client_id") == connection_id:
                            session["client_id"] = None
                            session["status"] = "waiting"
                            host_message = {
                                "type": "client_disconnected",
                                "data": {"client_id": connection_id}
                            }
                            await manager.send_personal_message(host_message, session["host_id"])
                            print(f"🔌 Client {connection_id} disconnected from session {session_id}")
                            break
            
            # 🆕 HANDLE CONNECTION APPROVAL
            elif message.type == MessageType.CONNECTION_APPROVE:
                pending_id = message.data.get("pending_id")
                
                if pending_id in manager.pending_connections:
                    pending = manager.pending_connections[pending_id]
                    
                    # Verify the approver is the host
                    if pending["host_id"] == connection_id:
                        success = await manager.approve_connection(pending_id)
                        
                        if success:
                            client_id = pending["client_id"]
                            session_id = pending["session_id"]
                            
                            # Notify CLIENT of approval
                            client_response = {
                                "type": "session_join_response",
                                "data": {
                                    "success": True,
                                    "session_id": session_id,
                                    "message": "Connection approved! You can now control the remote desktop."
                                }
                            }
                            await manager.send_personal_message(client_response, client_id)
                            
                            # Notify HOST of successful connection
                            host_response = {
                                "type": "client_connected",
                                "data": {
                                    "client_id": client_id,
                                    "session_id": session_id,
                                    "message": "Client connected successfully"
                                }
                            }
                            await manager.send_personal_message(host_response, connection_id)
                            
                            print(f"✅ Connection approved: {client_id} joined session {session_id}")
                        else:
                            # Approval failed
                            error_response = {
                                "type": "connection_approval_failed",
                                "data": {"error": "Failed to approve connection"}
                            }
                            await manager.send_personal_message(error_response, connection_id)
            
            # 🆕 HANDLE CONNECTION REJECTION
            elif message.type == MessageType.CONNECTION_REJECT:
                pending_id = message.data.get("pending_id")
                reject_reason = message.data.get("reason", "Connection rejected by host")
                
                if pending_id in manager.pending_connections:
                    pending = manager.pending_connections[pending_id]
                    
                    # Verify the rejector is the host
                    if pending["host_id"] == connection_id:
                        client_id = pending["client_id"]
                        
                        # Notify CLIENT of rejection
                        client_response = {
                            "type": "session_join_response",
                            "data": {
                                "success": False,
                                "error": reject_reason,
                                "rejected": True
                            }
                        }
                        await manager.send_personal_message(client_response, client_id)
                        
                        # Clean up pending connection
                        await manager.reject_connection(pending_id)
                        
                        print(f"❌ Connection rejected: {pending_id} - Reason: {reject_reason}")
            
            # 🎥 HANDLE SCREEN SHARING
            elif message.type == MessageType.SCREEN_SHARE:
                if message.data.get("action") == "start":
                    quality = message.data.get("quality", "medium")
                    fps = message.data.get("fps", 15)
                    
                    print(f"📺 Starting screen sharing for {connection_id} - Quality: {quality}, FPS: {fps}")
                    
                    # Adjust quality settings
                    if quality == "low":
                        screen_capture.quality = 60
                        screen_capture.scale_factor = 0.5
                        fps = 10
                    elif quality == "high":
                        screen_capture.quality = 90
                        screen_capture.scale_factor = 1.0
                        fps = 20
                    else:  # medium
                        screen_capture.quality = 80
                        screen_capture.scale_factor = 0.7
                        fps = 15
                    
                    try:
                        # Stop any existing streaming first
                        screen_capture.stop_streaming()
                        
                        # Start new streaming task
                        task = asyncio.create_task(
                            screen_capture.start_streaming(manager, connection_id, fps)
                        )
                        
                        print(f"✅ Screen capture task started")
                        
                        response = {
                            "type": "sharing_started",
                            "data": {"quality": quality, "fps": fps}
                        }
                        await manager.send_personal_message(response, connection_id)
                        
                    except Exception as e:
                        print(f"❌ Error starting screen sharing: {e}")
                        error_response = {
                            "type": "sharing_error",
                            "data": {"error": str(e)}
                        }
                        await manager.send_personal_message(error_response, connection_id)
                    
                elif message.data.get("action") == "stop":
                    print(f"🛑 Stopping screen sharing for {connection_id}")
                    screen_capture.stop_streaming()
                    response = {"type": "sharing_stopped", "data": {}}
                    await manager.send_personal_message(response, connection_id)
            
            # 🖱️ HANDLE MOUSE EVENTS
            elif message.type == MessageType.MOUSE_EVENT:
                print(f"🖱️ Received mouse event from {connection_id}")
                mouse_event = MouseEvent(**message.data)
                
                # Execute the mouse action on the HOST computer
                success = execute_mouse_event(message.data)
                
                if not success:
                    print(f"❌ Failed to execute mouse event: {message.data}")
                
                # Also relay to other peers if needed
                await manager.relay_message(message, connection_id)
            
            # ⌨️ HANDLE KEYBOARD EVENTS
            elif message.type == MessageType.KEYBOARD_EVENT:
                print(f"⌨️ Received keyboard event from {connection_id}")
                keyboard_event = KeyboardEvent(**message.data)
                
                # Execute the keyboard action on the HOST computer
                success = execute_keyboard_event(message.data)
                
                if not success:
                    print(f"❌ Failed to execute keyboard event: {message.data}")
                
                # Also relay to other peers if needed
                await manager.relay_message(message, connection_id)
            
            # 🎚️ HANDLE QUALITY CHANGE
            elif message.type == MessageType.QUALITY_CHANGE:
                quality = message.data.get("quality", "medium")
                print(f"🎚️ Quality change requested: {quality}")
                
                if quality == "low":
                    screen_capture.quality = 60
                    screen_capture.scale_factor = 0.5
                elif quality == "high":
                    screen_capture.quality = 90
                    screen_capture.scale_factor = 1.0
                else:
                    screen_capture.quality = 80
                    screen_capture.scale_factor = 0.7
                
                response = {
                    "type": "quality_changed",
                    "data": {"quality": quality}
                }
                await manager.send_personal_message(response, connection_id)
            
            # 🔗 HANDLE WEBRTC SIGNALING
            elif message.type in [MessageType.OFFER, MessageType.ANSWER, MessageType.ICE_CANDIDATE]:
                await manager.relay_message(message, connection_id)
                
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected: {connection_id}")
        manager.disconnect(connection_id)
    except Exception as e:
        print(f"❌ WebSocket error for connection {connection_id}: {e}")
        manager.disconnect(connection_id)

# 🧪 TEST ENDPOINT FOR SCREEN CAPTURE
@app.get("/test/screenshot")
async def test_screenshot():
    """Test endpoint to verify screen capture works"""
    try:
        screen_data = screen_capture.capture_screen()
        if screen_data:
            return {
                "success": True,
                "message": "Screen capture working",
                "frame_size": len(screen_data["frame"]) if isinstance(screen_data, dict) and "frame" in screen_data else len(str(screen_data)),
                "screen_size": f"{screen_capture.actual_screen_width}x{screen_capture.actual_screen_height}" if hasattr(screen_capture, 'actual_screen_width') else "Unknown"
            }
        else:
            return {"success": False, "error": "Screen capture failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 🐛 DEBUG ENDPOINTS
@app.get("/debug/sessions")
async def debug_sessions():
    return {
        "active_connections": list(manager.active_connections.keys()),
        "sessions": {
            sid: {
                "host_id": session.get("host_id"),
                "client_id": session.get("client_id"),
                "has_password": "password" in session
            }
            for sid, session in manager.sessions.items()
        },
        "pending_connections": {
            pid: {
                "session_id": pending.get("session_id"),
                "client_id": pending.get("client_id"),
                "host_id": pending.get("host_id")
            }
            for pid, pending in manager.pending_connections.items()
        }
    }

# 💚 HEALTH CHECK
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "AnyDesk Clone - Remote Desktop WebApp",
        "features": ["Screen Sharing", "Mouse Control", "Keyboard Control", "Connection Approval"],
        "active_connections": len(manager.active_connections),
        "active_sessions": len(manager.sessions),
        "pending_connections": len(manager.pending_connections)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
