import uvicorn
import signal
import sys
import asyncio
from app.api import app
from app.utils.logger import logger

def handle_sigterm(signum, frame):
    """Graceful shutdown handler for SIGTERM"""
    logger.info("Received SIGTERM, initiating graceful shutdown...")
    # Add any cleanup logic here
    sys.exit(0)

# Register SIGTERM handler
signal.signal(signal.SIGTERM, handle_sigterm)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
