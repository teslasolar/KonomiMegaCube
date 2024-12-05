from fastapi import FastAPI, WebSocket, HTTPException, Path, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import asyncio
from pathlib import Path as FilePath
from typing import Dict, Set, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from sim.services.cube.manager import CubeManager
from sim.core.database import db
from sim.core.config import config
import uuid
import ssl

logger = logging.getLogger(__name__)

class CubeConfig(BaseModel):
    """Configuration for cube creation"""
    name: str = Field(..., description="Name of the cube")
    cube_type: str = Field("standalone", description="Type of cube")
    config: Dict = Field(default_factory=dict, description="Additional configuration")

class CubeMessage(BaseModel):
    """Message to be sent to a cube"""
    message_type: str = Field(..., description="Type of message")
    data: Dict = Field(..., description="Message payload")

class StandaloneCubeServer:
    def __init__(self):
        self.app = FastAPI(
            title="Standalone Cube Server",
            description="API for managing standalone cubes with WebSocket support",
            version="1.0.0"
        )
        self.setup_middleware()
        self.cube_manager = CubeManager()
        self.active_connections: Set[WebSocket] = set()
        self.instance_id = str(uuid.uuid4())
        self.setup_routes()
        
    def setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
    def setup_routes(self):
        # HTML endpoint
        @self.app.get("/", response_class=HTMLResponse, tags=["UI"])
        async def get_html():
            """Get the HTML interface for the cube server"""
            html_path = FilePath("sim/templates/standalone/cube_server.html")
            with open(html_path) as f:
                content = f.read()
            return HTMLResponse(content)
            
        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time cube communication"""
            await self.handle_websocket_connection(websocket)
            
        # REST API endpoints
        @self.app.get("/api/cube/status", tags=["Cube Management"])
        async def get_cube_status():
            """Get the current status of the cube server"""
            try:
                return {
                    "status": "active",
                    "instance_id": self.instance_id,
                    "connected_clients": len(self.active_connections),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting status: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/cube/create", tags=["Cube Management"])
        async def create_cube(config: CubeConfig):
            """Create a new cube with the specified configuration"""
            try:
                result = await self.cube_manager.create_scada_cube(
                    cube_id=str(uuid.uuid4()),
                    name=config.name,
                    scada_type=config.cube_type,
                    configuration=config.config
                )
                return {
                    "cube_id": result.cube_id,
                    "status": "created",
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Error creating cube: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/cube/{cube_id}", tags=["Cube Management"])
        async def get_cube_info(cube_id: str = Path(..., description="ID of the cube to retrieve")):
            """Get information about a specific cube"""
            try:
                cube_info = await self.cube_manager.get_cube_info(cube_id)
                if not cube_info:
                    raise HTTPException(status_code=404, detail="Cube not found")
                return cube_info
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting cube info: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/cube/{cube_id}/message", tags=["Cube Management"])
        async def send_cube_message(
            cube_id: str = Path(..., description="ID of the cube to send message to"),
            message: CubeMessage = Body(..., description="Message to send to the cube")
        ):
            """Send a message to a specific cube"""
            try:
                await self.broadcast_message({
                    "type": message.message_type,
                    "cube_id": cube_id,
                    "data": message.data,
                    "timestamp": datetime.utcnow().isoformat()
                })
                return {"status": "message_sent", "cube_id": cube_id}
            except Exception as e:
                logger.error(f"Error sending message: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
            
    async def handle_websocket_connection(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        
        try:
            while True:
                data = await websocket.receive_json()
                await self.process_message(websocket, data)
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            self.active_connections.remove(websocket)
            
    async def process_message(self, websocket: WebSocket, data: Dict):
        try:
            message_type = data.get("type")
            if message_type == "create_cube":
                result = await self.cube_manager.create_scada_cube(
                    cube_id=data.get("cube_id"),
                    name=data.get("name"),
                    scada_type="standalone",
                    configuration=data.get("config", {})
                )
                await websocket.send_json({
                    "type": "cube_created",
                    "cube_id": result.cube_id,
                    "status": "success"
                })
            elif message_type == "list_cubes":
                cubes = await self.cube_manager.list_cubes()
                await websocket.send_json({
                    "type": "cube_list",
                    "cubes": cubes
                })
            elif message_type == "peer_discovery":
                await self.handle_peer_discovery(websocket, data)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
            
    async def handle_peer_discovery(self, websocket: WebSocket, data: Dict):
        peer_id = data.get("peer_id")
        if peer_id:
            await websocket.send_json({
                "type": "peer_ack",
                "instance_id": self.instance_id
            })

    async def broadcast_message(self, message: Dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {str(e)}")

def create_standalone_server():
    server = StandaloneCubeServer()
    return server.app

if __name__ == "__main__":
    import uvicorn
    port = config.get_port("standalone_cube")
    if config.is_port_available(port):
        uvicorn.run(create_standalone_server(), host="0.0.0.0", port=port)
    else:
        raise RuntimeError(f"Port {port} is not available")
