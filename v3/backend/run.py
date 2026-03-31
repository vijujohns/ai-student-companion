#!/usr/bin/env python
import sys
import os

# Add the backend directory to Python path so 'app' module can be found
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Now import and run uvicorn
import uvicorn
from app.core.config_loader import get_backend_bind_config

if __name__ == "__main__":
    bind_cfg = get_backend_bind_config()
    uvicorn.run(
        "app.main:app",
        host=bind_cfg["host"],
        port=bind_cfg["port"],
        reload=False
    )
