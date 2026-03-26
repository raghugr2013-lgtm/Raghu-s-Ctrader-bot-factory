"""
WebSocket Manager for Real-Time Bot Updates
Provides live streaming of bot status, trades, and alerts
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import json
from datetime import datetime, timezone

router = APIRouter()

class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections by client_id
        self.active_connections: Dict[str, WebSocket] = {}
        # Track which bots each client is subscribed to
        self.subscriptions: Dict[str, Set[str]] = {}
        # Global broadcast connections
        self.global_subscribers: Set[str] = set()
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.global_subscribers.add(client_id)
        print(f"[WS] Client connected: {client_id}")
    
    def disconnect(self, client_id: str):
        """Handle client disconnection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.subscriptions:
            del self.subscriptions[client_id]
        self.global_subscribers.discard(client_id)
        print(f"[WS] Client disconnected: {client_id}")
    
    def subscribe_to_bot(self, client_id: str, bot_id: str):
        """Subscribe client to specific bot updates"""
        if client_id not in self.subscriptions:
            self.subscriptions[client_id] = set()
        self.subscriptions[client_id].add(bot_id)
    
    def unsubscribe_from_bot(self, client_id: str, bot_id: str):
        """Unsubscribe client from specific bot updates"""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(bot_id)
    
    async def send_to_client(self, client_id: str, message: dict):
        """Send message to specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                print(f"[WS] Error sending to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast_to_bot_subscribers(self, bot_id: str, message: dict):
        """Send message to all clients subscribed to a specific bot"""
        disconnected = []
        for client_id, subs in self.subscriptions.items():
            if bot_id in subs:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception:
                    disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)
    
    async def broadcast_global(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for client_id in self.global_subscribers:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception:
                    disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)
    
    def get_stats(self):
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "global_subscribers": len(self.global_subscribers),
            "bot_subscriptions": {k: list(v) for k, v in self.subscriptions.items()}
        }


# Global WebSocket manager instance
ws_manager = WebSocketManager()


@router.websocket("/ws/bot-updates")
async def websocket_bot_updates(websocket: WebSocket):
    """
    WebSocket endpoint for real-time bot updates
    
    Message types received from client:
    - {"action": "subscribe", "bot_id": "..."}
    - {"action": "unsubscribe", "bot_id": "..."}
    - {"action": "ping"}
    
    Message types sent to client:
    - {"type": "connected", "client_id": "..."}
    - {"type": "BOT_STATUS_UPDATE", ...}
    - {"type": "NEW_TRADE", ...}
    - {"type": "DD_WARNING", ...}
    - {"type": "DD_BREACH", ...}
    - {"type": "pong"}
    """
    import uuid
    client_id = str(uuid.uuid4())[:8]
    
    await ws_manager.connect(websocket, client_id)
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        while True:
            try:
                # Wait for message with timeout for keepalive
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                action = message.get("action")
                
                if action == "subscribe":
                    bot_id = message.get("bot_id")
                    if bot_id:
                        ws_manager.subscribe_to_bot(client_id, bot_id)
                        await websocket.send_json({
                            "type": "subscribed",
                            "bot_id": bot_id
                        })
                
                elif action == "unsubscribe":
                    bot_id = message.get("bot_id")
                    if bot_id:
                        ws_manager.unsubscribe_from_bot(client_id, bot_id)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "bot_id": bot_id
                        })
                
                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({
                        "type": "keepalive",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except:
                    break
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error for client {client_id}: {e}")
    finally:
        ws_manager.disconnect(client_id)


@router.get("/ws/stats")
async def get_ws_stats():
    """Get WebSocket connection statistics"""
    return ws_manager.get_stats()


# Helper functions for external modules to broadcast messages
async def broadcast_bot_status(bot_id: str, status: dict):
    """Broadcast bot status update"""
    message = {
        "type": "BOT_STATUS_UPDATE",
        "bot_id": bot_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **status
    }
    await ws_manager.broadcast_global(message)


async def broadcast_new_trade(bot_id: str, trade: dict):
    """Broadcast new trade notification"""
    message = {
        "type": "NEW_TRADE",
        "bot_id": bot_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **trade
    }
    await ws_manager.broadcast_global(message)


async def broadcast_dd_warning(bot_id: str, current_dd: float, max_dd: float):
    """Broadcast drawdown warning"""
    message = {
        "type": "DD_WARNING",
        "bot_id": bot_id,
        "current_drawdown": current_dd,
        "max_drawdown_limit": max_dd,
        "severity": "HIGH" if current_dd >= max_dd * 0.9 else "MEDIUM",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast_global(message)


async def broadcast_dd_breach(bot_id: str, current_dd: float, reason: str):
    """Broadcast drawdown breach (auto-stop)"""
    message = {
        "type": "DD_BREACH",
        "bot_id": bot_id,
        "current_drawdown": current_dd,
        "reason": reason,
        "action": "AUTO_STOPPED",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast_global(message)


async def broadcast_bot_alert(bot_id: str, alert_type: str, message_text: str, severity: str = "INFO"):
    """Broadcast general bot alert"""
    message = {
        "type": "BOT_ALERT",
        "bot_id": bot_id,
        "alert_type": alert_type,
        "message": message_text,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast_global(message)
