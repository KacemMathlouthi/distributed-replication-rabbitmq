import pika
import sys
import uuid
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
        "client": "client_reader"
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

def read_last_line():
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    
    # Create callback queue
    result = channel.queue_declare(queue='', exclusive=True)
    callback_queue = result.method.queue
    
    # Generate a unique correlation ID
    correlation_id = str(uuid.uuid4())
    
    # Set up consumer for response
    responses = []
    
    def on_response(ch, method, props, body):
        if props.correlation_id == correlation_id:
            response = body.decode()
            responses.append((props.reply_to, response))
            print(f"Received from {props.reply_to}: {response}")
    
    channel.basic_consume(
        queue=callback_queue,
        on_message_callback=on_response,
        auto_ack=True
    )
    
    log_client_operation("READ_LAST", "Request sent to all replicas")
    
    # Send request to all replicas via a direct communication to each
    for replica_id in range(1, 4):
        channel.basic_publish(
            exchange='',
            routing_key=f'replica{replica_id}',
            properties=pika.BasicProperties(
                reply_to=callback_queue,
                correlation_id=correlation_id,
            ),
            body='Read Last'
        )
    
    print(" [x] Sent 'Read Last' request to all replicas")
    
    # Wait for the first response or a timeout
    timeout = 3.0  # seconds
    start_time = time.time()
    
    while time.time() - start_time < timeout and not responses:
        connection.process_data_events()
        time.sleep(0.1)
    
    result = {
        "first_response": None,
        "all_responses": []
    }
    
    if responses:
        replica_id, content = responses[0]
        print(f"\nFirst response received from {replica_id}:")
        print(f"Content: {content}")
        result["first_response"] = {"replica": replica_id, "content": content}
        log_client_operation("RECEIVED_FIRST", f"{replica_id}: {content}")
    else:
        print("\nNo responses received within the timeout.")
        log_client_operation("TIMEOUT", "No responses received")
    
    # Wait a bit longer to see if other replicas respond
    time.sleep(1)
    connection.process_data_events()
    
    if len(responses) > 1:
        print("\nAll received responses:")
        for replica_id, content in responses:
            print(f"{replica_id}: {content}")
            result["all_responses"].append({"replica": replica_id, "content": content})
    
    connection.close()
    return result

if __name__ == "__main__":
    print("Connecting to RabbitMQ...")
    read_last_line()