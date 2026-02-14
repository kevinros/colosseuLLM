# Use a slim python image
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (needed for Bash commands in the Arena)
RUN apt-get update && apt-get install -y procps iproute2 curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"] 