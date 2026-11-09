# 🌩️ StormSense AI
### Historical Extreme-Weather Intelligence Through Hierarchical and Density-Based Clustering

<p align="center">
  <a href="https://stormsenseai-1.onrender.com"><strong>🚀 Live Demo</strong></a> •
  <a href="https://stormsenseai.onrender.com/docs"><strong>📘 API Documentation</strong></a> •
  <a href="https://github.com/Anisha-45/StormSenseAI"><strong>💻 GitHub Repository</strong></a>
</p>

**Smart India Hackathon (SIH) | Problem ID: SIH26078**

*Extreme Weather Event Grouping Through Hierarchical and Density-Based Clustering*

---

## 🌍 Overview

**StormSense AI** is a historical extreme-weather analysis and visualization platform that transforms NOAA Storm Events records into meaningful insights using machine learning and data analytics.

The platform uses **Hierarchical Agglomerative Clustering, DBSCAN, and HDBSCAN** to discover patterns and group similar storm events. It helps users explore historical weather events through interactive maps, seasonal analysis, impact comparisons, anomaly detection, and similar-event search.

Beyond historical analysis, StormSense AI also provides an operational layer with live National Weather Service alerts, route information, citizen incident reporting, resource management, and coordination tools.

> **Important:** Historical clustering is not weather forecasting. It identifies similarities and patterns in past records, not future weather conditions. Live weather alerts are sourced separately from the US National Weather Service.

## ✨ Key Features

### 1. Machine Learning and Clustering
- Hierarchical Agglomerative Clustering with Ward, Complete, Average, and Single linkage.
- DBSCAN for density-based event grouping.
- HDBSCAN for variable-density clustering.
- Adjustable clustering parameters.
- Dendrogram and linkage comparison.
- Cluster profiling and interpretation.

### 2. Data Analysis and Visualization
- Interactive geographical storm-event maps.
- Seasonal and temporal analysis.
- Storm impact and damage comparisons.
- Cluster distribution and PCA visualization.
- Similar historical event search.
- Multi-hazard analysis.

### 3. Model Evaluation
- Silhouette Score.
- Davies-Bouldin Index.
- Calinski-Harabasz Index.
- Adjusted Rand Index for clustering stability.
- Parameter sensitivity analysis.
- Reproducible clustering experiments.

### 4. Anomaly Detection and Intelligence
- Identification of unusual storm events.
- Similar-event exploration.
- Cluster-based statistical insights.
- Rule-based question assistant.
- PDF and CSV report generation.

### 5. Operational Features
- Live NWS weather alerts.
- Route information.
- Citizen incident reporting.
- Resource management and assignment.
- Role-based access control.
- Coordination and task management.

## 🧠 Machine Learning Algorithms

| Algorithm | Purpose |
|---|---|
| Hierarchical Agglomerative Clustering | Builds a hierarchy of similar storm events |
| DBSCAN | Identifies dense groups and noise points |
| HDBSCAN | Detects clusters with varying density |
| PCA | Reduces dimensions for visualization |
| Anomaly Detection | Identifies unusual event patterns |

### Model Evaluation Results

The following results are from a 5,000-event stratified sample using default features and random seed 42.

| Method | Clusters | Noise | Silhouette Score |
|---|---:|---:|---:|
| Hierarchical (Ward, k=6) | 6 | — | 0.301 |
| DBSCAN | 4 | 1.7% | 0.396 |
| HDBSCAN | 62 | 35.5% | 0.678 |

**Note:** A higher Silhouette Score does not automatically indicate a better clustering model. Noise percentage, cluster size, stability, and meaningful separation must also be considered.

## 📊 Dataset Information

StormSense AI uses historical storm-event records from the **NOAA Storm Events Database**.

The project works with three main datasets:

- `StormEvents_details` – Storm event descriptions, dates, locations, and impact information.
- `StormEvents_locations` – Geographical information associated with storm events.
- `StormEvents_fatalities` – Fatality-related records.

### Dataset Processing Summary

| Metric | Result |
|---|---:|
| Unique storm events | 32,671 |
| Events with coordinates | 25,251 |
| Events without coordinates | 7,420 |
| Events covered | February 2017 – September 2020 |

### Data Quality and Limitations

- The available details dataset does not cover the full 2010–2020 period.
- Some location records do not match events in the details dataset.
- Missing damage values are preserved as missing rather than incorrectly treated as zero.
- Events without geographical coordinates remain available for non-spatial analysis but are excluded from map-based analysis.

These limitations are considered during data processing and are documented in the application.

## 🏗️ System Architecture

```text
                 USER
                   |
                   v
          React Frontend
          (Vite + Tailwind)
                   |
                   v
           Nginx API Proxy
                   |
                   v
           FastAPI Backend
                   |
          +--------+--------+
          |        |        |
          v        v        v
       Data      Machine   Analytics
     Processing  Learning  & Reports
          |        |        |
          +--------+--------+
                   |
                   v
           Processed NOAA Data
                   |
                   v
             SQLite Database
```

The React frontend communicates with the FastAPI backend through API requests. The backend handles authentication, data processing, clustering, analytics, and report generation.

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Visualization | Recharts, Leaflet |
| Backend | Python, FastAPI |
| Machine Learning | Scikit-learn, HDBSCAN |
| Data Processing | Pandas, NumPy |
| Database | SQLite |
| Deployment | Render |
| Containerization | Docker, Docker Compose |
| External Services | NOAA, NWS, OSRM |

## 📁 Project Structure

```text
stormsense/
│
├── data/
│   ├── raw/
│   │   └── NOAA CSV datasets
│   └── processed/
│       ├── events.csv.gz
│       ├── events.parquet
│       └── manifest.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── ml/
│   │   └── core/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   └── nginx.conf
│
├── docs/
│   └── METHODOLOGY.md
│
├── docker-compose.yml
├── .env.example
├── run-backend.bat
├── run-frontend.bat
└── README.md
```

## ⚙️ Installation and Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm
- Git
- Docker Desktop (optional)

### 1. Clone the repository

```bash
git clone https://github.com/Anisha-45/StormSenseAI.git
```

```bash
cd StormSenseAI
```

### 2. Configure the backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Process the dataset

```bash
python -m app.cli process
```

This command processes the raw NOAA datasets and generates the processed event data.

### 4. Create an administrator account

```bash
python -m app.cli create-admin you@example.com "Your Name" "YourPassword"
```

Use your own email, name, and a strong password.

### 5. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

Backend API:

`http://localhost:8000`

Interactive API documentation:

`http://localhost:8000/docs`

### 6. Start the frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

`http://localhost:5173`

### 7. Run using Docker

From the project root:

```bash
docker compose up --build -d
```

Open the application:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000/docs`

To stop the containers:

```bash
docker compose down
```

**Security:** Configure `STORMSENSE_JWT_SECRET` with a long, random value. Keep your `.env` file and credentials private.

## 🔐 Authentication and Security

StormSense AI supports role-based access control with five roles:

- Administrator
- Coordinator
- Responder
- Researcher
- Citizen

Security features include:

- Password hashing.
- JWT-based authentication.
- Server-side role and permission checks.
- Input validation.
- Upload size and file-type validation.
- Per-user rate limiting.
- Duplicate incident-report detection.
- Audit logging for administrative actions.

## ☁️ Live Deployment

The application is deployed using **Render** with two separate services.

| Service | URL |
|---|---|
| Frontend | https://stormsenseai-1.onrender.com |
| Backend API | https://stormsenseai.onrender.com |
| API Documentation | https://stormsenseai.onrender.com/docs |

**For the complete application, open only the frontend link.** It communicates with the backend automatically.

## 🧪 Testing

The project includes automated tests covering:

- Dataset quality and preprocessing.
- Missing values and duplicate records.
- Hierarchical clustering, DBSCAN, and HDBSCAN.
- Clustering evaluation and stability.
- PCA and anomaly detection.
- Temporal and impact analytics.
- Authentication and authorization.
- Report generation.
- Incident reporting and resource-management rules.

The project test summary records **125 passing tests and 1 skipped test**. Live external-service integrations and the complete browser UI should be tested separately in the deployment environment.

## 🚧 Future Enhancements

- Integration of additional historical NOAA datasets.
- Improved geographical coverage for events without coordinates.
- Advanced weather prediction models using appropriate forecast data.
- Enhanced interactive risk visualization.
- Integration of additional official weather data sources.
- Improved scalability with PostgreSQL and larger datasets.

## 👩‍💻 Author

**Anisha Kumari**

B.Tech – Computer Science and Engineering  
Specialization: Artificial Intelligence and Machine Learning

GitHub: [Anisha-45](https://github.com/Anisha-45)

**Project:** StormSense AI  
**Problem ID:** SIH26078

---

⭐ If you find StormSense AI interesting, consider giving this repository a star!

**Disclaimer:** StormSense AI is a historical data analysis and decision-support platform. It does not replace official weather forecasts, emergency alerts, or guidance from relevant authorities.
