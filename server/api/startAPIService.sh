#!/usr/bin/env bash
# This script starts the FastAPI server using uvicorn.

# Start the FastAPI server using uvicorn      
uvicorn main:app --host 127.0.01 --port 8000 --reload