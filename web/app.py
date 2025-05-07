import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.utils import *

# Set page configuration
st.set_page_config(
    page_title="Distributed Replication System",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("System Visualization")
    st.plotly_chart(draw_system_architecture(), use_container_width=True)

with col2:
    st.header("System Status")
    
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