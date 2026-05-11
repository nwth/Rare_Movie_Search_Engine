"""CineSeeker - Rare Movie Search Engine

Entry point for the application.

Usage:
    # Development
    python main.py

    # Production
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import uvicorn
from loguru import logger

from api.server import create_app

app = create_app()

if __name__ == "__main__":
    import sys

    # Configure loguru
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level="DEBUG" if app.debug else "INFO",
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
