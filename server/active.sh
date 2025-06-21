#!/usr/bin/env bash
# This script installs the necessary dependencies for the python server.
# Ensure Python is installed and set up on your system.

set -e
# Create a virtual environment for the project  
python3 -m venv 
# Activate the virtual environment  
source project_env/bin/activate