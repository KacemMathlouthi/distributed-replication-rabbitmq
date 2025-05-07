import streamlit as st
import time
import os
from datetime import datetime
import pika
import json
import sys

# Add the src directory to the Python path so we can import the client modules
sys.path.append('/app/src')

# Import client functions from existing scripts
from clientWriter import send_message as client_send_message
from clientReader import read_last_line as client_read_last_line
from clientReader_v2 import read_all_lines as client_read_all_lines

# Function to read log files
def read_logs(log_file):
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    logs.append(log_entry)
                except json.JSONDecodeError:
                    pass
    return logs

# Function to read replica data files
def read_replica_data(replica_id):
    file_path = f"/app/replicas/replica{replica_id}/data.txt"
    data = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = [line.strip() for line in f.readlines() if line.strip()]
    return data

# Function to send write message to RabbitMQ (using clientWriter)
def send_write_message(line_number, content):
    try:
        message = f"{line_number} {content}"
        client_send_message(message)
        return True
    except Exception as e:
        st.error(f"Failed to send message: {str(e)}")
        return False

# Function to request last line (using clientReader)
def read_last_line():
    try:
        result = client_read_last_line()
        return [(response["replica"], response["content"]) for response in result.get("all_responses", [])]
    except Exception as e:
        st.error(f"Failed to read last line: {str(e)}")
        return []

# Function to request all lines with majority consensus (using clientReader_v2)
def read_all_lines():
    try:
        results = client_read_all_lines()
        
        # Process results to match the expected format
        formatted_results = {
            "replica_data": {},
            "majority_lines": []
        }
        
        # Extract raw data
        for replica, lines in results.get("raw_data", {}).items():
            formatted_results["replica_data"][replica] = lines
        
        # Extract majority lines
        for line, count in results.get("majority_lines", []):
            formatted_results["majority_lines"].append((line, count))
            
        return formatted_results
    except Exception as e:
        st.error(f"Failed to read all lines: {str(e)}")
        return {
            "replica_data": {},
            "majority_lines": []
        }

# Function to check replica status by checking for recent log activity
def check_replica_status():
    statuses = {}
    for replica_id in range(1, 4):
        log_path = f"/app/replicas/replica{replica_id}/operations.log"
        
        # Check if replica directory exists with data file
        data_file_exists = os.path.exists(f"/app/replicas/replica{replica_id}/data.txt")
        
        # Check if log file exists and has recent entries
        log_exists = os.path.exists(log_path)
        recent_activity = False
        
        if log_exists:
            try:
                # Check if there are any logs in the last 5 minutes
                logs = read_logs(log_path)
                if logs:
                    last_log_time = datetime.fromisoformat(logs[-1].get("timestamp", ""))
                    recent_activity = (datetime.now() - last_log_time).total_seconds() < 300  # 5 minutes
            except:
                pass
        
        # Check if we can connect to replica service (as another way to check if it's running)
        network_active = False
        try:
            # Try to connect to RabbitMQ and check for replica's queue
            import pika
            connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq', connection_attempts=1, socket_timeout=2))
            channel = connection.channel()
            
            # Check if replica's queue exists
            try:
                channel.queue_declare(queue=f'replica{replica_id}', passive=True)
                network_active = True
            except:
                pass
            
            connection.close()
        except:
            pass
        
        # Consider a replica running if any of these conditions is true
        statuses[f"replica{replica_id}"] = data_file_exists or recent_activity or network_active
        
    return statuses

# Function to stop a replica by sending a SIGTERM signal via RabbitMQ
def stop_replica(replica_id):
    try:
        # Send a special control message to the replica to make it stop
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
        channel = connection.channel()
        
        channel.basic_publish(
            exchange='',
            routing_key=f'replica{replica_id}',
            properties=pika.BasicProperties(
                reply_to='web_control',
                correlation_id='shutdown'
            ),
            body='SHUTDOWN'
        )
        connection.close()
        
        # Give it a moment to process
        time.sleep(2)
        return True
    except Exception as e:
        st.error(f"Failed to stop replica: {str(e)}")
        return False

# Function to start a replica - we can't do this directly, so we'll show instructions
def start_replica(replica_id):
    st.info(f"""
    To restart replica{replica_id}, run this command from your host machine:
    ```
    docker-compose restart replica{replica_id}
    ```
    """)
    return True