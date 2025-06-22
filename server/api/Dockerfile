FROM python:3.6-slim-buster AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py .
COPY exlib/pyc/image_processor.pyx exlib/pyc/image_processor.pyx

RUN mkdir -p exlib/pyc && touch exlib/__init__.py exlib/pyc/__init__.py

RUN python setup.py build_ext --inplace

FROM python:3.6-slim-buster AS runtime

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

COPY --from=builder /app/exlib/pyc /app/exlib/pyc

COPY exlib/py/image_processor.py exlib/py/image_processor.py

RUN mkdir -p exlib/py && touch exlib/__init__.py exlib/py/__init__.py

COPY . .

COPY .env.example .env

ENV APP_HOST="0.0.0.0"
ENV APP_PORT="8000"

EXPOSE 8000

CMD ["uvicorn", " "main:app", "--host", "$(APP_HOST)", "--port", "$(APP_PORT)"]