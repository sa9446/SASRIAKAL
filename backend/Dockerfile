FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV, ffmpeg, MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create models directory
RUN mkdir -p models

EXPOSE 8000

ENV SASRIAKAL_HOST=0.0.0.0
ENV SASRIAKAL_PORT=8000
ENV SASRIAKAL_RELOAD=false
ENV SASRIAKAL_LOG_LEVEL=INFO

CMD ["python", "main.py"]
