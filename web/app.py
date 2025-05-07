import streamlit as st
import pandas as pd
import json
import os
import time
import plotly.graph_objects as go
from datetime import datetime
import pika
import uuid
import subprocess
from collections import defaultdict

# Set page configuration
st.set_page_config(
    page_title="Distributed Replication System",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Function to send write message to RabbitMQ
def send_write_message(line_number, content):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
        channel = connection.channel()
        
        # Declare exchange for broadcasting to all replicas
        channel.exchange_declare(exchange='replication_exchange', exchange_type='fanout')
        
        # Create the message
        message = f"{line_number} {content}"
        
        # Publish message to exchange
        channel.basic_publish(
            exchange='replication_exchange',
            routing_key='',
            body=message
        )
        
        # Log the operation
        log_client_operation("WRITE", message)
        
        connection.close()
        return True
    except Exception as e:
        st.error(f"Failed to send message: {str(e)}")
        return False

# Function to log client operation
def log_client_operation(operation_type, content):
    log_dir = "/app/replicas"
    log_file = f"{log_dir}/client_operations.log"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation_type,
        "content": content,
        "client": "web_ui"
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

# Function to request last line
def read_last_line():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
        channel = connection.channel()
        
        result = channel.queue_declare(queue='', exclusive=True)
        callback_queue = result.method.queue
        
        correlation_id = str(uuid.uuid4())
        
        responses = []
        
        def on_response(ch, method, props, body):
            if props.correlation_id == correlation_id:
                response = body.decode()
                responses.append((props.reply_to, response))
        
        channel.basic_consume(
            queue=callback_queue,
            on_message_callback=on_response,
            auto_ack=True
        )
        
        log_client_operation("READ_LAST", "Request sent to all replicas")
        
        # Send request to all replicas
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
        
        # Wait for responses with timeout
        timeout = 3.0
        start_time = time.time()
        
        while time.time() - start_time < timeout and len(responses) < 3:
            connection.process_data_events(time_limit=0.1)
        
        connection.close()
        return responses
    except Exception as e:
        st.error(f"Failed to read last line: {str(e)}")
        return []

# Function to request all lines with majority consensus
def read_all_lines():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
        channel = connection.channel()
        
        result = channel.queue_declare(queue='', exclusive=True)
        callback_queue = result.method.queue
        
        correlation_id = str(uuid.uuid4())
        
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
                
                if response == "__END__":
                    replica_completed[props.reply_to] = True
                else:
                    replica_data[props.reply_to].append(response)
        
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
        
        # Wait for responses with timeout
        timeout = 5.0
        start_time = time.time()
        
        while time.time() - start_time < timeout and not all(replica_completed.values()):
            connection.process_data_events(time_limit=0.1)
        
        # Determine majority consensus
        all_lines = set()
        for lines in replica_data.values():
            for line in lines:
                all_lines.add(line)
        
        line_counts = defaultdict(int)
        for replica, lines in replica_data.items():
            for line in lines:
                line_counts[line] += 1
        
        majority_lines = []
        for line, count in sorted(line_counts.items()):
            if count >= 2:  # Majority of 3
                majority_lines.append((line, count))
        
        connection.close()
        
        return {
            "replica_data": replica_data,
            "majority_lines": majority_lines
        }
    except Exception as e:
        st.error(f"Failed to read all lines: {str(e)}")
        return {
            "replica_data": {},
            "majority_lines": []
        }

# Function to check replica status
def check_replica_status():
    statuses = {}
    for replica_id in range(1, 4):
        container_name = f"distributed-replication-rabbitmq-replica{replica_id}-1"
        try:
            result = subprocess.run(
                f"docker inspect -f '{{{{.State.Running}}}}' {container_name}",
                shell=True, capture_output=True, text=True
            )
            statuses[f"replica{replica_id}"] = result.stdout.strip() == "true"
        except:
            statuses[f"replica{replica_id}"] = False
    return statuses

# Function to stop a replica
def stop_replica(replica_id):
    container_name = f"distributed-replication-rabbitmq-replica{replica_id}-1"
    try:
        subprocess.run(f"docker stop {container_name}", shell=True)
        return True
    except:
        return False

# Function to start a replica
def start_replica(replica_id):
    container_name = f"distributed-replication-rabbitmq-replica{replica_id}-1"
    try:
        subprocess.run(f"docker start {container_name}", shell=True)
        return True
    except:
        return False

# Define the Streamlit app layout
st.title("Distributed Replication System Dashboard")

# Create the sidebar
st.sidebar.header("Control Panel")

# Write Operation Section
st.sidebar.subheader("Write Operation")
line_number = st.sidebar.number_input("Line Number", min_value=1, value=1)
content = st.sidebar.text_input("Content", value="Sample text")

if st.sidebar.button("Write Data"):
    if send_write_message(line_number, content):
        st.sidebar.success(f"Successfully wrote: {line_number} {content}")
    else:
        st.sidebar.error("Failed to write data")

# Read Operation Section
st.sidebar.subheader("Read Operations")

if st.sidebar.button("Read Last Line"):
    with st.spinner("Reading last line from all replicas..."):
        responses = read_last_line()
        st.session_state.last_read_responses = responses

if st.sidebar.button("Read All Lines (Majority Consensus)"):
    with st.spinner("Reading all lines and computing majority consensus..."):
        results = read_all_lines()
        st.session_state.all_read_results = results

# Replica Control Section
st.sidebar.subheader("Replica Control (Simulate Failures)")
replica_to_control = st.sidebar.selectbox("Select Replica", ["replica1", "replica2", "replica3"])
replica_id = int(replica_to_control[-1])

col1, col2 = st.sidebar.columns(2)
if col1.button(f"Stop {replica_to_control}"):
    if stop_replica(replica_id):
        st.sidebar.success(f"Stopped {replica_to_control}")
    else:
        st.sidebar.error(f"Failed to stop {replica_to_control}")

if col2.button(f"Start {replica_to_control}"):
    if start_replica(replica_id):
        st.sidebar.success(f"Started {replica_to_control}")
    else:
        st.sidebar.error(f"Failed to start {replica_to_control}")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("System Visualization")
    
    # Get replica statuses and create a visualization
    statuses = check_replica_status()
    fig = go.Figure()
    
    # Add RabbitMQ node
    fig.add_trace(go.Scatter(
        x=[0], y=[0],
        mode='markers+text',
        marker=dict(size=40, color='lightskyblue', symbol='square'),
        text=['RabbitMQ'],
        textposition='bottom center',
        name='RabbitMQ'
    ))
    
    # Add replicas
    x_positions = [-1, 0, 1]
    for i, (replica, is_running) in enumerate(statuses.items()):
        color = 'green' if is_running else 'red'
        fig.add_trace(go.Scatter(
            x=[x_positions[i]], y=[-1.5],
            mode='markers+text',
            marker=dict(size=30, color=color),
            text=[replica],
            textposition='bottom center',
            name=replica
        ))
        
        # Add connection line to RabbitMQ
        fig.add_trace(go.Scatter(
            x=[x_positions[i], 0],
            y=[-1.5, 0],
            mode='lines',
            line=dict(color=color, width=2),
            showlegend=False
        ))
    
    # Add clients
    fig.add_trace(go.Scatter(
        x=[-1.5, 1.5],
        y=[1.5, 1.5],
        mode='markers+text',
        marker=dict(size=30, color='orange'),
        text=['Writer', 'Reader'],
        textposition='top center',
        name='Clients'
    ))
    
    # Add connection lines to RabbitMQ
    fig.add_trace(go.Scatter(
        x=[-1.5, 0],
        y=[1.5, 0],
        mode='lines',
        line=dict(color='orange', width=2),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[1.5, 0],
        y=[1.5, 0],
        mode='lines',
        line=dict(color='orange', width=2),
        showlegend=False
    ))
    
    # Update layout
    fig.update_layout(
        title='System Architecture',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        width=600,
        height=500
    )
    
    st.plotly_chart(fig)

with col2:
    st.header("System Status")
    
    # Display replica status
    for replica, is_running in statuses.items():
        status_text = "🟢 Running" if is_running else "🔴 Stopped"
        st.text(f"{replica}: {status_text}")
    
    # Display time since last operation
    client_logs = read_logs("/app/replicas/client_operations.log")
    if client_logs:
        last_op = client_logs[-1]
        last_time = datetime.fromisoformat(last_op["timestamp"])
        st.text(f"Last operation: {last_op['operation']}")
        st.text(f"Last content: {last_op['content']}")
        st.text(f"Time: {last_time.strftime('%H:%M:%S')}")

# Results section
st.header("Results")

tab1, tab2, tab3, tab4 = st.tabs(["Last Read Results", "Consensus Results", "Replica Content", "Operation Logs"])

with tab1:
    if hasattr(st.session_state, 'last_read_responses') and st.session_state.last_read_responses:
        responses = st.session_state.last_read_responses
        for replica_id, content in responses:
            st.success(f"{replica_id}: {content}")
    else:
        st.info("No read responses yet. Try reading the last line from the sidebar.")

with tab2:
    if hasattr(st.session_state, 'all_read_results') and st.session_state.all_read_results:
        results = st.session_state.all_read_results
        
        st.subheader("Majority Consensus")
        for line, count in results["majority_lines"]:
            st.success(f"{line} (found in {count}/3 replicas)")
        
        st.subheader("Raw Data from Each Replica")
        cols = st.columns(3)
        for i, (replica, lines) in enumerate(results["replica_data"].items()):
            with cols[i]:
                st.write(f"**{replica}**")
                for line in sorted(lines):
                    st.text(line)
    else:
        st.info("No consensus results yet. Try reading all lines from the sidebar.")

with tab3:
    # Show the content of each replica file
    cols = st.columns(3)
    for i in range(3):
        replica_id = i + 1
        with cols[i]:
            st.subheader(f"Replica {replica_id}")
            data = read_replica_data(replica_id)
            if data:
                for line in data:
                    st.text(line)
            else:
                st.info("No data available")

with tab4:
    # Get all logs
    all_logs = []
    client_logs = read_logs("/app/replicas/client_operations.log")
    all_logs.extend(client_logs)
    
    for i in range(3):
        replica_logs = read_logs(f"/app/replicas/replica{i+1}/operations.log")
        all_logs.extend(replica_logs)
    
    # Sort by timestamp
    all_logs.sort(key=lambda x: x.get("timestamp", ""))
    
    # Convert to DataFrame for display
    if all_logs:
        df = pd.DataFrame(all_logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp', ascending=False)
        
        # Format the DataFrame
        display_df = df[['timestamp', 'client' if 'client' in df.columns else 'replica', 'operation', 'content']]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No operation logs available yet")

# Auto-refresh the page
st.markdown(
    """
    <script>
        var timeout = setTimeout(function() {
            window.location.reload();
        }, 10000);
    </script>
    """,
    unsafe_allow_html=True
)