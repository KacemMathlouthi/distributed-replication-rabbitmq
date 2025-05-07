# 🌀 Distributed Replication System

A real-time, containerised distributed replication system built with RabbitMQ, Docker, and Streamlit. It simulates fault-tolerant replica coordination and showcases how message queues can manage data consistency across multiple nodes in a distributed environment.

## 🚀 Features

- 🐇 **RabbitMQ-based message coordination**  
- 💾 **Three replica nodes** storing and serving data independently  
- ✏️ **Writer service** to broadcast messages to all replicas  
- 🔎 **Reader services**:
  - Read from the first available replica
  - Perform majority consensus across all replicas  
- 📈 **Streamlit dashboard** to visualise the system and view logs, data, and operations  
- ♻️ **Live logging and health checks** with auto-refresh

---

## 🧱 Architecture

```

Client (Streamlit)
|
|──✏️ Write: Send to RabbitMQ → Broadcast to Replicas
|
└──🔎 Read: Request from RabbitMQ → Get data from Replicas

````

Each replica persists data in local storage and responds to reads either directly or through consensus logic.

---

## 📦 Getting Started

### Prerequisites

- Docker & Docker Compose

### Setup Instructions

1. **Clone the repo**:

   ```bash
   git clone https://github.com/KacemMathlouthi/distributed-replication-rabbitmq.git
   cd distributed-replication-rabbitmq
   ```

2. **Build and start the system**:
   ```bash
   docker-compose up --build
   ```

3. **Access the dashboard**:

   Open your browser at:
   [http://localhost:8501](http://localhost:8501)

---

## 🛠️ System Components

| Service    | Description                               |
| ---------- | ----------------------------------------- |
| `rabbitmq` | Message queue for all communication       |
| `replica1` | First storage node                        |
| `replica2` | Second storage node                       |
| `replica3` | Third storage node                        |
| `web`      | Streamlit-based dashboard for interaction |

---

## 📊 Dashboard Highlights

* **Write Panel**: Enter a line number and content, broadcast to all replicas.
* **Read Panel**:

  * *Read Last Line*: Fetch from first responding replica.
  * *Read All (Consensus)*: Compare all replicas and show majority-agreed lines.
* **System Visualisation**: Interactive Plotly-based diagram with transparent background.
* **Logs & Data Viewer**: See raw replica data and detailed operation logs.

---

## 📁 Directory Structure

```
.
├── replicas/               # Local data and logs for each replica
├── src/                    # Source logic for reader, writer, replica nodes
├── web/app.py              # Streamlit web interface
├── utils/utils.py          # Shared utilities and visualisation code
├── Dockerfile              # App container build
├── docker-compose.yml      # Service orchestration
└── requirements.txt        # Python dependencies
```

---

## ✅ Health Checks

RabbitMQ has a built-in health check. Other services wait until RabbitMQ is fully operational before starting.

---

## 📜 License

MIT License — free to use, modify, and share.
