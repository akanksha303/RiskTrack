import os
import random
import json
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, Base, get_db
import db_models
from db_models import User, Transaction, RiskEvaluation
import models
from rules import evaluate_transaction, haversine_distance
from seed import seed_db

# Initialize database tables and seed if empty
Base.metadata.create_all(bind=engine)
seed_db()

app = FastAPI(
    title="TransactionGuard API",
    description="Real-time financial transaction risk assessment engine API",
    version="1.0.0"
)

# CORS Configuration
# Allow local developer setups and Vercel domains to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_txn_id(db: Session) -> str:
    """Helper to generate sequential unique transaction IDs like TXN1006"""
    count = db.query(Transaction).count()
    # Add a random element or use count to prevent collision
    return f"TXN{1000 + count + random.randint(1, 99999):04d}"

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "TransactionGuard Risk Engine",
        "version": "1.0.0",
        "endpoints": {
            "evaluate": "POST /api/evaluate",
            "stats": "GET /api/stats",
            "transactions": "GET /api/transactions",
            "users": "GET /api/users",
            "simulate": "POST /api/simulate"
        }
    }

@app.get("/api/users", response_model=List[models.UserResponse])
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users

@app.get("/api/transactions", response_model=List[models.TransactionResponse])
def get_transactions(db: Session = Depends(get_db)):
    txs = db.query(Transaction).order_by(Transaction.timestamp.desc()).all()
    
    result = []
    for tx in txs:
        user_name = tx.user.name if tx.user else "Unknown User"
        eval_detail = None
        if tx.evaluation:
            eval_detail = models.RiskEvaluationDetail(
                velocity_score=tx.evaluation.velocity_score,
                amount_anomaly_score=tx.evaluation.amount_anomaly_score,
                geo_mismatch_score=tx.evaluation.geo_mismatch_score,
                unusual_hour_score=tx.evaluation.unusual_hour_score,
                new_merchant_score=tx.evaluation.new_merchant_score,
                reasons=json.loads(tx.evaluation.reasons),
                risk_score=tx.evaluation.risk_score,
                decision=tx.evaluation.decision,
                evaluated_at=tx.evaluation.evaluated_at
            )
        
        result.append(
            models.TransactionResponse(
                id=tx.id,
                user_id=tx.user_id,
                user_name=user_name,
                amount=tx.amount,
                currency=tx.currency,
                merchant=tx.merchant,
                location_lat=tx.location_lat,
                location_lon=tx.location_lon,
                timestamp=tx.timestamp,
                evaluation=eval_detail
            )
        )
    return result

@app.get("/api/transactions/{txn_id}", response_model=models.TransactionResponse)
def get_transaction_detail(txn_id: str, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    user_name = tx.user.name if tx.user else "Unknown User"
    eval_detail = None
    if tx.evaluation:
        eval_detail = models.RiskEvaluationDetail(
            velocity_score=tx.evaluation.velocity_score,
            amount_anomaly_score=tx.evaluation.amount_anomaly_score,
            geo_mismatch_score=tx.evaluation.geo_mismatch_score,
            unusual_hour_score=tx.evaluation.unusual_hour_score,
            new_merchant_score=tx.evaluation.new_merchant_score,
            reasons=json.loads(tx.evaluation.reasons),
            risk_score=tx.evaluation.risk_score,
            decision=tx.evaluation.decision,
            evaluated_at=tx.evaluation.evaluated_at
        )
        
    return models.TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        user_name=user_name,
        amount=tx.amount,
        currency=tx.currency,
        merchant=tx.merchant,
        location_lat=tx.location_lat,
        location_lon=tx.location_lon,
        timestamp=tx.timestamp,
        evaluation=eval_detail
    )

@app.post("/api/evaluate", response_model=models.TransactionResponse)
def evaluate_and_save_transaction(payload: models.TransactionCreate, db: Session = Depends(get_db)):
    # Verify user exists
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found")

    txn_timestamp = payload.timestamp or datetime.utcnow()
    txn_id = generate_txn_id(db)

    # Run the Risk Evaluation Engine rules
    evaluation_result = evaluate_transaction(
        db=db,
        user=user,
        amount=payload.amount,
        merchant=payload.merchant,
        lat=payload.location_lat,
        lon=payload.location_lon,
        timestamp=txn_timestamp
    )

    # Save transaction record
    new_txn = Transaction(
        id=txn_id,
        user_id=payload.user_id,
        amount=payload.amount,
        currency=payload.currency,
        merchant=payload.merchant,
        location_lat=payload.location_lat,
        location_lon=payload.location_lon,
        timestamp=txn_timestamp
    )
    db.add(new_txn)

    # Save risk evaluation report
    new_eval = RiskEvaluation(
        transaction_id=txn_id,
        risk_score=evaluation_result["risk_score"],
        decision=evaluation_result["decision"],
        velocity_score=evaluation_result["velocity_score"],
        amount_anomaly_score=evaluation_result["amount_anomaly_score"],
        geo_mismatch_score=evaluation_result["geo_mismatch_score"],
        unusual_hour_score=evaluation_result["unusual_hour_score"],
        new_merchant_score=evaluation_result["new_merchant_score"],
        reasons=json.dumps(evaluation_result["reasons"]),
        evaluated_at=datetime.utcnow()
    )
    db.add(new_eval)

    # Update User Profile Baseline stats
    user.last_location_lat = payload.location_lat
    user.last_location_lon = payload.location_lon
    user.last_transaction_time = txn_timestamp
    db.add(user)

    db.commit()
    db.refresh(new_txn)

    # Return structure
    eval_detail = models.RiskEvaluationDetail(
        velocity_score=new_eval.velocity_score,
        amount_anomaly_score=new_eval.amount_anomaly_score,
        geo_mismatch_score=new_eval.geo_mismatch_score,
        unusual_hour_score=new_eval.unusual_hour_score,
        new_merchant_score=new_eval.new_merchant_score,
        reasons=evaluation_result["reasons"],
        risk_score=new_eval.risk_score,
        decision=new_eval.decision,
        evaluated_at=new_eval.evaluated_at
    )

    return models.TransactionResponse(
        id=new_txn.id,
        user_id=new_txn.user_id,
        user_name=user.name,
        amount=new_txn.amount,
        currency=new_txn.currency,
        merchant=new_txn.merchant,
        location_lat=new_txn.location_lat,
        location_lon=new_txn.location_lon,
        timestamp=new_txn.timestamp,
        evaluation=eval_detail
    )

@app.get("/api/stats", response_model=models.DashboardStats)
def get_dashboard_statistics(db: Session = Depends(get_db)):
    # Basic counts
    total_txs = db.query(Transaction).count()
    if total_txs == 0:
        return models.DashboardStats(
            total_transactions=0,
            approved_count=0,
            review_count=0,
            blocked_count=0,
            approval_rate=100.0,
            risk_buckets=[0, 0, 0, 0, 0],
            hourly_trends=[],
            recent_transactions=[]
        )

    approved = db.query(RiskEvaluation).filter(RiskEvaluation.decision == "APPROVE").count()
    review = db.query(RiskEvaluation).filter(RiskEvaluation.decision == "REVIEW").count()
    blocked = db.query(RiskEvaluation).filter(RiskEvaluation.decision == "BLOCK").count()
    
    approval_rate = (approved / total_txs) * 100.0 if total_txs > 0 else 100.0

    # Risk score buckets (0-20, 21-40, 41-60, 61-80, 81-100)
    risk_buckets = [0, 0, 0, 0, 0]
    evals = db.query(RiskEvaluation.risk_score).all()
    for ev in evals:
        score = ev[0]
        if score <= 20:
            risk_buckets[0] += 1
        elif score <= 40:
            risk_buckets[1] += 1
        elif score <= 60:
            risk_buckets[2] += 1
        elif score <= 80:
            risk_buckets[3] += 1
        else:
            risk_buckets[4] += 1

    # Hourly risk trends
    # In SQLite, we can extract hour from timestamp using strftime. In Postgres we can use EXTRACT(HOUR FROM timestamp)
    # We will do this via python calculations to support both databases cleanly without DB-specific SQL dialacts
    hourly_data = {}
    for hour in range(24):
        hourly_data[hour] = {"sum": 0.0, "count": 0}
        
    all_evals = db.query(RiskEvaluation.risk_score, RiskEvaluation.evaluated_at).all()
    for score, timestamp in all_evals:
        if timestamp:
            hr = timestamp.hour
            hourly_data[hr]["sum"] += score
            hourly_data[hr]["count"] += 1
            
    hourly_trends = []
    for hr, data in hourly_data.items():
        avg_risk = data["sum"] / data["count"] if data["count"] > 0 else 0.0
        hourly_trends.append({
            "hour": hr,
            "avg_risk": round(avg_risk, 1),
            "count": data["count"]
        })

    # Recent transaction logs (limit 15)
    recent_txs = db.query(Transaction).order_by(Transaction.timestamp.desc()).limit(15).all()
    recent_responses = []
    for tx in recent_txs:
        user_name = tx.user.name if tx.user else "Unknown User"
        eval_detail = None
        if tx.evaluation:
            eval_detail = models.RiskEvaluationDetail(
                velocity_score=tx.evaluation.velocity_score,
                amount_anomaly_score=tx.evaluation.amount_anomaly_score,
                geo_mismatch_score=tx.evaluation.geo_mismatch_score,
                unusual_hour_score=tx.evaluation.unusual_hour_score,
                new_merchant_score=tx.evaluation.new_merchant_score,
                reasons=json.loads(tx.evaluation.reasons),
                risk_score=tx.evaluation.risk_score,
                decision=tx.evaluation.decision,
                evaluated_at=tx.evaluation.evaluated_at
            )
        recent_responses.append(
            models.TransactionResponse(
                id=tx.id,
                user_id=tx.user_id,
                user_name=user_name,
                amount=tx.amount,
                currency=tx.currency,
                merchant=tx.merchant,
                location_lat=tx.location_lat,
                location_lon=tx.location_lon,
                timestamp=tx.timestamp,
                evaluation=eval_detail
            )
        )

    return models.DashboardStats(
        total_transactions=total_txs,
        approved_count=approved,
        review_count=review,
        blocked_count=blocked,
        approval_rate=round(approval_rate, 2),
        risk_buckets=risk_buckets,
        hourly_trends=hourly_trends,
        recent_transactions=recent_responses
    )

@app.post("/api/simulate", response_model=models.TransactionResponse)
def simulate_scenario(scenario_type: str = Query(..., description="Scenario: standard, amount_anomaly, velocity_spike, impossible_travel, unusual_hour"), 
                      user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    
    # 1. Fetch user. If user_id is not specified, pick a random user from seeded database
    if not user_id:
        users = db.query(User).all()
        if not users:
            raise HTTPException(status_code=404, detail="No users found in database to simulate.")
        user = random.choice(users)
    else:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    now = datetime.utcnow()

    # 2. Preset Simulation Scenarios
    if scenario_type == "standard":
        # Safe transaction: matching user profile, near last location
        amount = round(random.uniform(user.avg_amount * 0.8, user.avg_amount * 1.2), 2)
        merchant = random.choice(["Star Coffee", "DMart Mall", "Amazon India", "Uber Cabs", "Supermarket"])
        
        # Micro offsets for coordinates
        lat_offset = random.uniform(-0.005, 0.005)
        lon_offset = random.uniform(-0.005, 0.005)
        lat = (user.last_location_lat or 19.0760) + lat_offset
        lon = (user.last_location_lon or 72.8777) + lon_offset
        
        # Time within common hour (pick one hour from user's common hours)
        common_hours = [int(h) for h in user.common_hours.split(",") if h.strip().isdigit()]
        target_hour = random.choice(common_hours) if common_hours else 12
        timestamp = now.replace(hour=target_hour, minute=random.randint(0, 59), second=random.randint(0, 59))
        if timestamp > now:
            timestamp = timestamp - timedelta(days=1)

    elif scenario_type == "amount_anomaly":
        # Transaction amount is 8x the average
        amount = round(user.avg_amount * 7.5 + random.uniform(100, 500), 2)
        merchant = "Luxury Watch Boutique"
        lat = user.last_location_lat or 19.0760
        lon = user.last_location_lon or 72.8777
        timestamp = now

    elif scenario_type == "velocity_spike":
        # Simulates a rapid consecutive transaction
        # To make it trigger, we can inject 3 transactions immediately.
        # This endpoint will inject 3 previous transactions in the last 2 minutes, then return the 4th evaluate transaction!
        # This guarantees the velocity rule will trigger for the caller!
        # Excellent logic for instant demonstrations.
        merchants = ["Electronics Store", "App Store", "Gaming Portal", "Food Delivery"]
        for i in range(3):
            sub_timestamp = now - timedelta(minutes=3 - i, seconds=30)
            sub_txn_id = generate_txn_id(db)
            sub_eval_res = evaluate_transaction(
                db=db, user=user, amount=120.0, merchant=merchants[i],
                lat=user.last_location_lat, lon=user.last_location_lon, timestamp=sub_timestamp
            )
            sub_txn = Transaction(
                id=sub_txn_id, user_id=user.id, amount=120.0, currency="INR",
                merchant=merchants[i], location_lat=user.last_location_lat, location_lon=user.last_location_lon,
                timestamp=sub_timestamp
            )
            db.add(sub_txn)
            sub_eval = RiskEvaluation(
                transaction_id=sub_txn_id, risk_score=sub_eval_res["risk_score"], decision=sub_eval_res["decision"],
                velocity_score=sub_eval_res["velocity_score"], amount_anomaly_score=sub_eval_res["amount_anomaly_score"],
                geo_mismatch_score=sub_eval_res["geo_mismatch_score"], unusual_hour_score=sub_eval_res["unusual_hour_score"],
                new_merchant_score=sub_eval_res["new_merchant_score"], reasons=json.dumps(sub_eval_res["reasons"]),
                evaluated_at=sub_timestamp
            )
            db.add(sub_eval)
        db.commit()

        # The final trigger transaction:
        amount = 180.0
        merchant = "Gift Card Portal"
        lat = user.last_location_lat
        lon = user.last_location_lon
        timestamp = now

    elif scenario_type == "impossible_travel":
        # London to Paris/New York coordinates depending on user's current baseline.
        # If user was in London (lat: 51.5, lon: -0.12), place current txn in Tokyo (lat: 35.6, lon: 139.7)
        # If user was in Mumbai/SF, place in New York (lat: 40.71, lon: -74.00)
        # Time difference is set to 2 minutes
        if user.last_location_lat and abs(user.last_location_lat - 51.5074) < 1.0:
            # Priya is in London, place transaction in Tokyo
            lat, lon = 35.6762, 139.6503
            merchant = "Tokyo Tech Emporium"
        else:
            # Rahul/Vikram in Mumbai/SF, place transaction in Paris
            lat, lon = 48.8566, 2.3522
            merchant = "Champs-Élysées Souvenirs"
            
        amount = round(random.uniform(500, 2000), 2)
        # Set last transaction time to 2 minutes ago
        user.last_transaction_time = now - timedelta(minutes=2)
        db.add(user)
        db.commit()
        
        timestamp = now

    elif scenario_type == "unusual_hour":
        # Force a late night outlier (e.g. 3:00 AM)
        amount = round(random.uniform(400, 1500), 2)
        merchant = "Midnight Online Casino"
        lat = user.last_location_lat or 19.0760
        lon = user.last_location_lon or 72.8777
        
        # Set timestamp to 3 AM today
        timestamp = now.replace(hour=3, minute=15, second=0)
        if timestamp > now:
            timestamp = timestamp - timedelta(days=1)
            
    else:
        raise HTTPException(status_code=400, detail=f"Unknown simulation scenario type: {scenario_type}")

    # 3. Build evaluation request body and evaluate
    create_payload = models.TransactionCreate(
        user_id=user.id,
        amount=amount,
        merchant=merchant,
        location_lat=lat,
        location_lon=lon,
        timestamp=timestamp
    )
    
    return evaluate_and_save_transaction(payload=create_payload, db=db)
