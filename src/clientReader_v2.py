import pika
import sys
import uuid
import time
import json
from collections import defaultdict
from datetime import datetime

def log_client_operation(operation_type, content):
    """Log client operations for the web UI"""
    log_dir = f"/app/replicas"
    log_file = f"{log_dir}/client_operations.log"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation_type,
        "content": content,
        "client": "client_reader_v2"
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

def read_all_lines():
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    
    # Create callback queue
    result = channel.queue_declare(queue='', exclusive=True)
    callback_queue = result.method.queue
    
    # Generate a unique correlation ID
    correlation_id = str(uuid.uuid4())
    
    # Store responses from each replica
    replica_data = {
        'replica1': [],
        'replica2': [],
        'replica3': []
    }
    
    replica_completed = {
        'replica1': False,
        'replica2': False,
        'replica3': False
    }
    
    def on_response(ch, method, props, body):
        if props.correlation_id == correlation_id:
            response = body.decode()
            
            # Check if this is an end marker
            if response == "__END__":
                replica_completed[props.reply_to] = True
                print(f"{props.reply_to} completed transmission")
            else:
                replica_data[props.reply_to].append(response)
                print(f"Received from {props.reply_to}: {response}")
    
    channel.basic_consume(
        queue=callback_queue,
        on_message_callback=on_response,
        auto_ack=True
    )
    
    log_client_operation("READ_ALL", "Requesting all data with majority consensus")
    
    # Send request to all replicas
    for replica_id in range(1, 4):
        channel.basic_publish(
            exchange='',
            routing_key=f'replica{replica_id}',
            properties=pika.BasicProperties(
                reply_to=callback_queue,
                correlation_id=correlation_id,
            ),
            body='Read All'
        )
    
    print(" [x] Sent 'Read All' request to all replicas")
    
    # Wait for responses with timeout
    timeout = 5.0  # seconds
    start_time = time.time()
    
    while time.time() - start_time < timeout and not all(replica_completed.values()):
        connection.process_data_events()
        time.sleep(0.1)
    
    # Now determine the majority content for each line
    all_lines = set()
    for lines in replica_data.values():
        for line in lines:
            all_lines.add(line)
    
    # Count occurrences of each line across replicas
    line_counts = defaultdict(int)
    for replica, lines in replica_data.items():
        for line in lines:
            line_counts[line] += 1
    
    # Get majority consensus
    majority_lines = []
    print("\n=== MAJORITY CONSENSUS DATA ===")
    for line, count in sorted(line_counts.items()):
        if count >= 2:  # At least 2 replicas agree (majority of 3)
            majority_lines.append((line, count))
            print(f"{line} (appeared in {count} replicas)")
    
    # Print raw data from each replica for comparison
    raw_data = {}
    print("\n=== RAW DATA FROM EACH REPLICA ===")
    for replica, lines in replica_data.items():
        raw_data[replica] = sorted(lines)
        print(f"\n{replica}:")
        for line in sorted(lines):
            print(f"  {line}")
    
    log_client_operation("CONSENSUS_RESULT", json.dumps({
        "majority_lines": majority_lines,
        "raw_data": raw_data
    }))
    