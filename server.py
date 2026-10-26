"""Root backward-compatible shim for core.intelligence.server"""
from core.intelligence.server import *

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("core.intelligence.server:app", host="0.0.0.0", port=8000, reload=True)
