#!/usr/bin/env bash
# This script installs the necessary dependencies for the python server.
# Ensure Python is installed and set up on your system.

set -e
# Create a virtual environment for the project  
virtualenv env
# Activate the virtual environment  
source env/bin/activate