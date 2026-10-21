"""
api.py
------
Root entrypoint for running the IndiValidate FastAPI application with Uvicorn.

Usage:
    uvicorn api:app --host 127.0.0.1 --port 8000 --reload
Or directly:
    py api.py
"""

from app.api import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
