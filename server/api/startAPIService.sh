#!/usr/bin/env bash
# This script starts the FastAPI server using uvicorn.
      
uvicorn main:app --host 127.0.0.1 --port 8000 --reload