"""Root backward-compatible shim for core.crypto.pqc_api"""
from core.crypto.pqc_api import *

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("core.crypto.pqc_api:app", host="0.0.0.0", port=8001, reload=True)
