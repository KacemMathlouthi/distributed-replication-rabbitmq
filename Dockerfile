FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create replica directories if they don't exist
RUN mkdir -p replicas/replica1 replicas/replica2 replicas/replica3

CMD ["python", "-u", "src/replica.py", "1"]