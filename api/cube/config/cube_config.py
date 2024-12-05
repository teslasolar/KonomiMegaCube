"""
Configuration for the cube-based architecture with kTools integration
"""
from typing import Dict, Any
from pathlib import Path

# Base configuration
CUBE_CONFIG = {
    "version": "1.0.0",
    "architecture": {
        "dimensions": (1000, 1000, 1000),
        "face_size": (1000, 1000),
        "max_nodes": 9,  # 8 vertices + 1 central node
        "training": {
            "batch_size": 32,
            "max_memory_per_node": "100MB",
            "optimization_level": "memory_efficient"
        }
    },
    "ktools": {
        "enabled_modules": [
            "kfastapi",
            "kwebsockets",
            "korm",
            "kmigrations",
            "kmiddleware"
        ],
        "database": {
            "use_pooling": True,
            "max_connections": 20,
            "timeout": 30
        }
    },
    "networking": {
        "websocket": {
            "standalone_port": 5070,
            "scada_port": 5090,
            "ping_interval": 30,
            "ping_timeout": 10,
            "retry_attempts": 3,
            "retry_delay": 1000
        },
        "mesh": {
            "enabled": True,
            "sync_interval": 5000,
            "retry_attempts": 3
        }
    },
    "training": {
        "scada": {
            "enabled": True,
            "patterns": ["monitoring", "control", "alarming", "trending"],
            "priority_weights": {
                "monitoring": 0.3,
                "control": 0.3,
                "alarming": 0.2,
                "trending": 0.2
            }
        },
        "dependency_management": {
            "auto_resolve": True,
            "max_depth": 5,
            "cache_ttl": 3600
        }
    }
}

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent

def get_config() -> Dict[str, Any]:
    """Get the configuration with resolved paths."""
    config = CUBE_CONFIG.copy()
    config["paths"] = {
        "root": str(get_project_root()),
        "models": str(get_project_root() / "models"),
        "cache": str(get_project_root() / "cache"),
        "logs": str(get_project_root() / "logs")
    }
    return config
