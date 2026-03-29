# 🦟 PRISM-H Dengue Surveillance Dashboard

A simplified public health surveillance system inspired by PRISM-H.
Built with Flask (Python) + SQLite + Leaflet.js + Chart.js.

---

## 📁 Project Structure

```
dengue-dashboard/
├── backend/
│   ├── app.py          ← Flask server
│   ├── requirements.txt
│   └── database.db     ← Auto-created on first run
├── frontend/
│   └── index.html      ← Full dashboard UI
└── README.md
```

---

## 🚀 How to Run (VS Code)

### Step 1 — Open project in VS Code
```
File → Open Folder → select dengue-dashboard/
```

### Step 2 — Open the integrated terminal
```
Terminal → New Terminal   (or Ctrl + ` )
```

### Step 3 — Go to backend folder
```bash
cd backend
```

### Step 4 — Create a virtual environment
```bash
python -m venv venv
```

### Step 5 — Activate the virtual environment

**Windows:**
```bash
venv\Scripts\activate
```

**Mac / Linux:**
```bash
source venv/bin/activate
```

### Step 6 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 7 — Run the Flask server
```bash
python app.py
```

You should see:
```
🦟 PRISM-H Dengue Dashboard
   Running at → http://localhost:5000
```

### Step 8 — Open the dashboard
Open your browser and go to: **http://localhost:5000**

> Or use VS Code Live Server on `frontend/index.html` — both work!

---

## 🌱 Load Sample Data

On first run, click **"Report Case" → "Seed 30 Days of Sample Data"**
to populate the dashboard with demo Bengaluru data.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cases` | Get all cases (supports filters) |
| POST | `/api/cases` | Add a single case |
| DELETE | `/api/cases/<id>` | Delete a case |
| GET | `/api/stats` | Summary stats + hotspots + trend |
| POST | `/api/cases/bulk` | Bulk import (JSON array) |
| POST | `/api/seed` | Seed sample data |

### Filter examples:
```
GET /api/cases?area=Koramangala
GET /api/cases?severity=severe
GET /api/cases?from=2024-01-01&to=2024-01-31
```

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, Flask |
| Database | SQLite |
| Maps | Leaflet.js + CartoDB dark tiles |
| Charts | Chart.js |
| Heatmap | Leaflet.heat plugin |

---

## 💡 Features

- ✅ Add/delete dengue cases
- ✅ SQLite persistent storage
- ✅ Stats (total, severe, zones, today)
- ✅ Interactive Leaflet map with hotspot markers
- ✅ Toggle heatmap visualization
- ✅ Filter records by area, severity, date range
- ✅ Daily trend chart (7/14/30 day)
- ✅ Severity breakdown doughnut chart
- ✅ Weekly comparison bar chart
- ✅ Area-wise distribution chart
- ✅ Age demographics chart
- ✅ ML outbreak prediction (linear extrapolation)
- ✅ Automatic outbreak alert banner
- ✅ CSV bulk upload
- ✅ CSV export
- ✅ Auto-refresh every 30 seconds

---

## 🗣 Viva Answer

> "This is a simplified public health surveillance system inspired by WHO's PRISM-H.
> It enables real-time dengue case reporting, geospatial hotspot visualization using Leaflet.js,
> trend analytics via Chart.js, and basic outbreak prediction using linear regression on a
> 30-day rolling window. The backend is built with Flask and SQLite, following a RESTful API design."
