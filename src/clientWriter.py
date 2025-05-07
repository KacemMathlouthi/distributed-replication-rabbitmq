import pika
import sys
import time
import json
from datetime import datetime

def log_client_operation(operation_type, content):
    """Log client operations for the web UI"""
    log_dir = f"/app/replicas"
    log_file = f"{log_dir}/client_operations.log"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation_type,
        "content": content,
        "client": "client_writer"
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

def send_message(message):
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    
    # Declare exchange for broadcasting to all replicas
    channel.exchange_declare(exchange='replication_exchange', exchange_type='fanout')
    
    # Publish message to exchange
    channel.basic_publish(
        exchange='replication_exchange',
        routing_key='',
        body=message
    )
    
    print(f" [x] Sent: {message}")
    log_client_operation("WRITE", message)
    connection.close()

def connect_with_retry(max_retries=10, retry_interval=2):
    """Connect to RabbitMQ with retry logic"""
    retries = 0
    while retries < max_retries:
        try:
            return pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
        except pika.exceptions.AMQPConnectionError:
            retries += 1
            print(f"Connection attempt {retries} failed. Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
    
    raise Exception("Failed to connect to RabbitMQ after multiple attempts")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python client_writer.py <line_number> <text>")
        sys.exit(1)
    
    line_number = sys.argv[1]
    text = ' '.join(sys.argv[2:])
    message = f"{line_number} {text}"
    
    print("Connecting to RabbitMQ...")
    # Use with retry when running in docker
    send_message(message)