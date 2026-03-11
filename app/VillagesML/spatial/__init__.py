"""Spatial analysis API module"""
from .hotspots import router as hotspots_router
from .integration import router as integration_router

# Combine routers
routers = [hotspots_router, integration_router]

__all__ = ["routers"]
