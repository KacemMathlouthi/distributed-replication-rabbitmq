import pika
import sys
import os
import time
import json
from datetime import datetime

def ensure_replica_dir(replica_id):
    """Ensure the replica directory exists"""
    directory = f"/app/replicas/replica{replica_id}"
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def write_to_file(directory, message):
    """Write message to the replica's file"""
    file_path = f"{directory}/data.txt"
    
    # Extract line number and content
    parts = message.split(' ', 1)
    if len(parts) != 2:
        print(f"Invalid message format: {message}")
        return False
    
    line_number = int(parts[0])
    content = parts[1]
    
    # Read existing lines
    existing_lines = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            existing_lines = file.readlines()
    
    # Remove newlines and parse line numbers
    processed_lines = []
    line_numbers = []
    for line in existing_lines:
        line = line.strip()
        if line:
            parts = line.split(' ', 1)
            if len(parts) == 2:
                try:
                    num = int(parts[0])
                    line_numbers.append(num)
                    processed_lines.append((num, line))
                except ValueError:
                    processed_lines.append((-1, line))  # Invalid format
    
    # Add new line if it doesn't exist
    if line_number not in line_numbers:
        processed_lines.append((line_number, f"{line_number} {content}"))
    
    # Sort by line number
    processed_lines.sort(key=lambda x: x[0])
    
    # Write all lines back to file
    with open(file_path, 'w') as file:
        for _, line in processed_lines:
            file.write(f"{line}\n")
    
    # Also log the operation for the web UI
    log_operation(replica_id, "WRITE", f"{line_number} {content}")
    
    print(f"Written to {file_path}: {line_number} {content}")
    return True

def log_operation(replica_id, operation_type, content):
    """Log operations for the web UI"""
    log_dir = f"/app/replicas/replica{replica_id}"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = f"{log_dir}/operations.log"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation_type,
        "content": content,
        "replica": f"replica{replica_id}"
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

def handle_read_last_request(replica_id, correlation_id, reply_to):
    """Handle a request to read the last line of the file"""
    directory = ensure_replica_dir(replica_id)
    file_path = f"{directory}/data.txt"
    
    last_line = ""
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            lines = file.readlines()
            if lines:
                last_line = lines[-1].strip()
    
    # Log the read operation
    log_operation(replica_id, "READ_LAST", last_line if last_line else "No data")
    
    # Send response back to the client
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    
    channel.basic_publish(
        exchange='',
        routing_key=reply_to,
        properties=pika.BasicProperties(
            correlation_id=correlation_id,
            reply_to=f'replica{replica_id}'
        ),
        body=last_line
    )
    connection.close()
    print(f"Replica {replica_id} responded with last line: {last_line}")

def handle_read_all_request(replica_id, correlation_id, reply_to):
    """Handle a request to read all lines of the file"""
    directory = ensure_replica_dir(replica_id)
    file_path = f"{directory}/data.txt"
    
    # Log the read operation
    log_operation(replica_id, "READ_ALL", "Full file request")
    
    # Send each line back to the client
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            lines = file.readlines()
            
            for line in lines:
                line = line.strip()
                if line:
                    channel.basic_publish(
                        exchange='',
                        routing_key=reply_to,
                        properties=pika.BasicProperties(
                            correlation_id=correlation_id,
                            reply_to=f'replica{replica_id}'
                        ),
                        body=line
                    )
    
    # Send an end marker
    channel.basic_publish(
        exchange='',
        routing_key=reply_to,
        properties=pika.BasicProperties(
            correlation_id=correlation_id,
            reply_to=f'replica{replica_id}'
        ),
        body="__END__"
    )
    
    connection.close()
    print(f"Replica {replica_id} sent all lines from file")

def callback(ch, method, properties, body):
    """Callback function for message processing"""
    message = body.decode()
    print(f" [x] Replica {replica_id} received {message}")
    
    if properties.reply_to:
        # This is a read request
        if message == 'Read Last':
            handle_read_last_request(replica_id, properties.correlation_id, properties.reply_to)
        elif message == 'Read All':
            handle_read_all_request(replica_id, properties.correlation_id, properties.reply_to)
    else:
        # This is a write operation
        directory = ensure_replica_dir(replica_id)
        write_to_file(directory, message)
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

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
    if len(sys.argv) != 2:
        print("Usage: python replica.py <replica_id>")
        sys.exit(1)
    
    replica_id = sys.argv[1]
    log_operation(replica_id, "STARTUP", f"Replica {replica_id} started")
    
    # Connect to RabbitMQ with retry
    print(f"Replica {replica_id} connecting to RabbitMQ...")
    connection = connect_with_retry()
    channel = connection.channel()
    
    # Set up exchange for broadcasts
    channel.exchange_declare(exchange='replication_exchange', exchange_type='fanout')
    
    # Create a queue for this replica to receive broadcast messages
    result = channel.queue_declare(queue=f'replica{replica_id}_queue', exclusive=False)
    queue_name = result.method.queue
    
    # Bind to the exchange
    channel.queue_bind(exchange='replication_exchange', queue=queue_name)
    
    # Create a queue for direct messages to this replica
    channel.queue_declare(queue=f'replica{replica_id}', exclusive=False)
    
    # Set up consumer for both queues
    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    channel.basic_consume(queue=f'replica{replica_id}', on_message_callback=callback)
    
    print(f" [*] Replica {replica_id} waiting for messages. To exit press CTRL+C")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print(f"Shutting down Replica {replica_id}")
        log_operation(replica_id, "SHUTDOWN", f"Replica {replica_id} shutdown gracefully")
        channel.close()
        connection.close()