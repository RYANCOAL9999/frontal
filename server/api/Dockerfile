# Dockerfile for FastAPI Application
FROM python:3.6-slim-buster AS builder

# Set working directory inside the container
WORKDIR /app

# Install build dependencies required for psycopg2-binary and Cython
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .

# Install Python dependencies, including Cython and psycopg2-binary
RUN pip install --no-cache-dir -r requirements.txt

# Copy Cython source and setup.py
COPY setup.py .
COPY exlib/pyc/image_processor.pyx exlib/pyc/image_processor.pyx

# Ensure the necessary __init__.py files are present for Python to recognize packages
RUN mkdir -p exlib/pyc && touch exlib/__init__.py exlib/pyc/__init__.py

# Compile the Cython module
RUN python setup.py build_ext --inplace

# --- Stage 2: Runtime Environment ---
FROM python:3.6-slim-buster AS runtime

# Set working directory inside the container
WORKDIR /app

# Install runtime dependencies for psycopg2-binary (libpq)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy only the necessary Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.6/site-packages /usr/local/lib/python3.6/site-packages

# Copy the compiled Cython module from the builder stage
COPY --from=builder /app/exlib/pyc /app/exlib/pyc

# Copy the pure Python fallback if it exists (for dev/debugging without recompilation)
COPY exlib/py/image_processor.py exlib/py/image_processor.py

# Re-create the __init__.py files as they are not copied with the specific file copies above
RUN mkdir -p exlib/py && touch exlib/__init__.py exlib/py/__init__.py

# Copy remaining application files
COPY . .

# Copy and prepare .env file
COPY .env.example .env

# Default host and port for the FastAPI application
ENV APP_HOST="0.0.0.0"
ENV APP_PORT="8000"

# Expose the port Uvicorn will run on
EXPOSE 8000

# Start the FastAPI application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "$(APP_HOST)", "--port", "$(APP_PORT)"]