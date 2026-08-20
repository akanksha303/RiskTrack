# TransactionGuard (RiskTrack) 🛡️

TransactionGuard is a real-time financial transaction risk assessment engine and monitoring dashboard. Unlike black-box ML fraud detectors, this project implements a rule-based, fully explainable assessment flow based on user behavior indicators, calculating a score from 0 to 100, generating logical decisions (`APPROVE`, `REVIEW`, `BLOCK`), and tracking them in a queryable database audit log.

---

## Key Features
* **Explainable Risk Engine**: Evaluates transaction velocity, historical amount anomalies, geo-mismatches, hour of day, and merchant baseline familiarity.
* **Sleek Operational Dashboard**: A pure Vanilla CSS glassmorphic panel monitoring approval metrics, risk score distributions, hourly trend analytics, and transaction log feeds.
* **Interactive Simulator**: Inject standard purchases, geographical location anomalies, amount spikes, velocity attacks, and late-night transactions instantly.
* **Flexible Database layer**: Zero-config local SQLite file for development; transitions dynamically to high-performance PostgreSQL in production environments.

---

## Directory Structure

```text
RiskTrack/
├── backend/
│   ├── database.py       # SQLAlchemy engine & session configurations
│   ├── db_models.py      # Declarative SQL models (User, Transaction, RiskEvaluation)
│   ├── models.py         # Pydantic schemas for request/response validation
│   ├── rules.py          # The 5 Risk Evaluation rules engine code
│   ├── seed.py           # Populates demo users and baselines
│   ├── main.py           # FastAPI server with evaluation & stats routes
│   ├── test_rules.py     # Unit test assertions for the rules engine
│   ├── requirements.txt  # Python requirements list
│   └── Procfile          # Render web server instruction
└── frontend/
    ├── index.html        # Web app frame with SEO & semantic elements
    ├── style.css         # Custom dark-theme glassmorphism styling
    ├── app.js            # Live polling, modal, and custom SVG charts renderer
    └── vercel.json       # Vercel static asset routing
```

---

## Getting Started Locally

### 1. Run the Backend API

1. Navigate to the `backend/` folder:
   ```bash
   cd backend
   ```
2. Set up a Python virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On MacOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI development server:
   ```bash
   uvicorn main:app --reload
   ```
   *The database will be initialized automatically as `risktrack.db` and seeded with baseline users (Rahul Sharma in Mumbai, Priya Patel in London, Vikram Malhotra in San Francisco).*
   *API will be running locally at:* `http://localhost:8000`

5. Verify rules logic using unit tests:
   ```bash
   python -m unittest test_rules.py
   ```

### 2. Run the Frontend Dashboard

Since the frontend is a zero-dependency HTML5 application, you can serve it locally using any static web server:

**Using Python:**
```bash
cd frontend
python -m http.server 3000
```
Open your browser to `http://localhost:3000`.

**Using VS Code:**
Right-click on `frontend/index.html` and click **Open with Live Server**.

---

## Deployment Instructions

### 1. Backend on Render 🚀
1. Create a free account on [Render](https://render.com).
2. Connect your GitHub repository containing the project.
3. Click **New +** and select **Web Service**.
4. Set the **Root Directory** to `backend`.
5. Environment Settings:
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. (Optional) Spin up a free PostgreSQL database on Render. Under your Web Service **Environment variables**, add:
   * `DATABASE_URL` = *[Your Render Postgres Connection String]*
7. Copy the backend service domain URL once deployed (e.g., `https://my-backend.onrender.com`).

### 2. Frontend on Vercel ⚡
1. Create an account on [Vercel](https://vercel.com).
2. Click **Add New** -> **Project** and import your GitHub repository.
3. In the project setup, set the **Root Directory** to `frontend`.
4. Leave build settings as default.
5. In **app.js** on GitHub, ensure the `PRODUCTION_BACKEND_URL` constant matches your deployed Render URL:
   ```javascript
   const PRODUCTION_BACKEND_URL = "https://my-backend.onrender.com";
   ```
6. Click **Deploy**. Vercel will build and serve your monitoring dashboard statically.
