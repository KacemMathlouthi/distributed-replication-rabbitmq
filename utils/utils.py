import streamlit as st
import os
import json
import sys
import plotly.graph_objects as go

# Add the src directory to the Python path so we can import the client modules
sys.path.append("/app/src")

# Import client functions from existing scripts
from clientWriter import send_message as client_send_message
from clientReader import read_last_line as client_read_last_line
from clientReader_v2 import read_all_lines as client_read_all_lines


# Function to read log files
def read_logs(log_file):
    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
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
        with open(file_path, "r") as f:
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
        return [
            (response["replica"], response["content"])
            for response in result.get("all_responses", [])
        ]
    except Exception as e:
        st.error(f"Failed to read last line: {str(e)}")
        return []


# Function to request all lines with majority consensus (using clientReader_v2)
def read_all_lines():
    try:
        results = client_read_all_lines()

        # Process results to match the expected format
        formatted_results = {"replica_data": {}, "majority_lines": []}

        # Extract raw data
        for replica, lines in results.get("raw_data", {}).items():
            formatted_results["replica_data"][replica] = lines

        # Extract majority lines
        for line, count in results.get("majority_lines", []):
            formatted_results["majority_lines"].append((line, count))

        return formatted_results
    except Exception as e:
        st.error(f"Failed to read all lines: {str(e)}")
        return {"replica_data": {}, "majority_lines": []}


def draw_system_architecture():
    fig = go.Figure()

    # Define node positions - improved layout with more spacing
    nodes = {
        "RabbitMQ": (0, 0),
        "replica1": (-3, -3),
        "replica2": (0, -3.5),
        "replica3": (3, -3),
        "Writer": (-3, 3),
        "Reader": (3, 3),
    }

    # Enhanced color palette with gradient effects
    node_colors = {
        "RabbitMQ": "#4287f5",  # vibrant blue
        "replica1": "#2ecc71",  # emerald green
        "replica2": "#27ae60",  # darker green
        "replica3": "#16a085",  # teal green
        "Writer": "#e67e22",  # deep orange
        "Reader": "#f39c12",  # golden yellow
    }

    # More descriptive icons and labels
    node_icons = {
        "RabbitMQ": "📦 Message Queue",
        "replica1": "💾 Replica 1",
        "replica2": "💾 Replica 2",
        "replica3": "💾 Replica 3",
        "Writer": "✏️ Writer Service",
        "Reader": "🔎 Reader Service",
    }

    # Add nodes with gradient effect
    for name, (x, y) in nodes.items():
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                marker=dict(
                    size=60,
                    color=node_colors[name],
                    line=dict(width=2, color="white"),
                    opacity=0.9,
                    symbol="circle",
                ),
                text=[node_icons[name]],
                textposition="middle center",
                textfont=dict(size=14, color="white", family="Arial Bold"),
                hoverinfo="text",
                hovertext=f"<b>{name}</b>",
                showlegend=False,
            )
        )

    # Define edges with data flow indicators
    edges = [
        ("Writer", "RabbitMQ", "Write Operations"),
        ("Reader", "RabbitMQ", "Read Queries"),
        ("RabbitMQ", "replica1", "Replication"),
        ("RabbitMQ", "replica2", "Replication"),
        ("RabbitMQ", "replica3", "Replication"),
    ]

    # Add beautified arrows with labels
    for start, end, label in edges:
        x0, y0 = nodes[start]
        x1, y1 = nodes[end]

        # Calculate midpoint for label
        mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2

        # Add the arrow
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.5,
            arrowwidth=3,
            arrowcolor="white",
            standoff=15,  # Space between arrow and node
            startstandoff=15,
        )

        # Add flow labels
        fig.add_annotation(
            x=mid_x,
            y=mid_y,
            text=label,
            showarrow=False,
            font=dict(size=12, color="#444444"),
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="#cccccc",
            borderwidth=1,
            borderpad=3,
            opacity=0.8,
        )

    # Add a subtle grid pattern background
    fig.update_layout(
        title={
            "text": "Distributed Replication System",
            "font": {"size": 24, "color": "#2c3e50", "family": "Arial Black"},
            "y": 0.95,
        },
        xaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False, range=[-4.5, 4.5]
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False, range=[-4.5, 4.5]
        ),
        width=900,
        height=650,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=80, b=40),
        shapes=[
            # Add a light grid pattern
            dict(
                type="rect",
                xref="paper",
                yref="paper",
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line=dict(color="rgba(200, 210, 220, 0.2)", width=1),
                layer="below",
            )
        ],
    )

    # Add container box styling
    fig.update_layout(
        shapes=[
            # Main container
            dict(
                type="rect",
                xref="paper",
                yref="paper",
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line=dict(color="#cccccc", width=2),
                fillcolor="rgba(0, 0, 0, 0)",
                layer="below",
            ),
            # Subtle separator between sections
            dict(
                type="line",
                xref="x",
                yref="y",
                x0=-4.5,
                y0=0,
                x1=4.5,
                y1=0,
                line=dict(color="rgba(200, 210, 220, 0.7)", width=1, dash="dot"),
                layer="below",
            ),
        ],
        annotations=[
            # Add title annotations for sections
            dict(
                xref="x",
                yref="y",
                x=-4.5,
                y=4,
                text="Client Services",
                showarrow=False,
                font=dict(size=16, color="#555555"),
                align="left",
            ),
            dict(
                xref="x",
                yref="y",
                x=-4.5,
                y=-4.5,
                text="Storage Layer",
                showarrow=False,
                font=dict(size=16, color="#555555"),
                align="left",
            ),
        ],
    )

    # Add subtitle
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.02,
        text="Real-time message-based data replication system",
        showarrow=False,
        font=dict(size=14, color="#666666"),
        align="center",
        opacity=0.8,
    )

    return fig
