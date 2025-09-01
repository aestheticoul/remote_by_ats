from PIL import ImageGrab, Image
import base64
import io
import asyncio
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

class ScreenCapture:
    def __init__(self):
        self.is_capturing = False
        self.quality = 80
        self.scale_factor = 0.7
        self.actual_screen_width = 1920  # Default for headless
        self.actual_screen_height = 1080  # Default for headless
        self.is_headless = os.getenv("ENVIRONMENT") == "production"
        
    def capture_screen(self) -> Optional[dict]:
        try:
            if self.is_headless:
                # Create a dummy screen for demo purposes in production
                return self.create_dummy_screen()
            
            logger.info("📸 Capturing screen...")
            
            # Try to get actual screen dimensions
            try:
                import pyautogui
                self.actual_screen_width, self.actual_screen_height = pyautogui.size()
                screenshot = pyautogui.screenshot()
            except Exception:
                # Fallback to PIL
                screenshot = ImageGrab.grab()
                self.actual_screen_width, self.actual_screen_height = screenshot.size
            
            logger.info(f"📐 Screen size: {self.actual_screen_width}x{self.actual_screen_height}")
            
            # Resize for streaming performance
            if self.scale_factor != 1.0:
                new_size = (int(screenshot.width * self.scale_factor), 
                           int(screenshot.height * self.scale_factor))
                screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"📏 Resized to: {new_size}")
            
            canvas_width, canvas_height = screenshot.size
            
            # Convert to JPEG and encode to base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format='JPEG', quality=self.quality, optimize=True)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            logger.info(f"✅ Screen captured successfully - {len(img_str)} bytes")
            
            return {
                "frame": f"data:image/jpeg;base64,{img_str}",
                "actual_screen_width": self.actual_screen_width,
                "actual_screen_height": self.actual_screen_height,
                "canvas_width": canvas_width,
                "canvas_height": canvas_height,
                "scale_factor": self.scale_factor
            }
            
        except Exception as e:
            logger.error(f"❌ Screen capture error: {e}")
            return self.create_dummy_screen()
    
    def create_dummy_screen(self) -> dict:
        """Create a dummy screen for demo in headless environment"""
        try:
            # Create a simple demo image
            width, height = int(1920 * self.scale_factor), int(1080 * self.scale_factor)
            image = Image.new('RGB', (width, height), color='#2c3e50')
            
            # Add some demo content
            try:
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(image)
                
                # Try to use a default font, fallback to basic if not available
                try:
                    font = ImageFont.truetype("arial.ttf", 48)
                except:
                    font = ImageFont.load_default()
                
                text = "Remote Desktop Demo\n\nRunning on Render\n\nConnect from client to test!"
                draw.multiline_text((width//4, height//3), text, fill='white', font=font, align='center')
                
            except Exception as e:
                logger.warning(f"Could not add text to demo image: {e}")
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=self.quality)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return {
                "frame": f"data:image/jpeg;base64,{img_str}",
                "actual_screen_width": 1920,
                "actual_screen_height": 1080,
                "canvas_width": width,
                "canvas_height": height,
                "scale_factor": self.scale_factor
            }
            
        except Exception as e:
            logger.error(f"Failed to create dummy screen: {e}")
            return None
    
    async def start_streaming(self, websocket_manager, host_connection_id: str, fps: int = 15):
        logger.info(f"🚀 Starting screen streaming for host: {host_connection_id} at {fps} FPS")
        
        self.is_capturing = True
        frame_delay = 1.0 / fps
        frame_count = 0
        
        while self.is_capturing:
            try:
                logger.debug(f"📸 Capturing frame #{frame_count}")
                screen_data = self.capture_screen()
                
                if screen_data:
                    message = {
                        "type": "screen_frame",
                        "data": screen_data
                    }
                    
                    # Send to host (for preview)
                    await websocket_manager.send_personal_message(message, host_connection_id)
                    
                    # Send to connected clients
                    for session_id, session in websocket_manager.sessions.items():
                        if session["host_id"] == host_connection_id:
                            client_id = session.get("client_id")
                            if client_id and client_id in websocket_manager.active_connections:
                                await websocket_manager.send_personal_message(message, client_id)
                            break
                    
                    frame_count += 1
                    if frame_count % 30 == 0:  # Log every 30 frames
                        logger.info(f"📤 Sent {frame_count} frames")
                
                await asyncio.sleep(frame_delay)
                
            except Exception as e:
                logger.error(f"❌ Streaming error at frame #{frame_count}: {e}")
                await asyncio.sleep(1)
        
        self.is_capturing = False
        logger.info(f"🛑 Screen streaming stopped after {frame_count} frames")
    
    def stop_streaming(self):
        logger.info("🛑 Stopping screen streaming...")
        self.is_capturing = False

screen_capture = ScreenCapture()
