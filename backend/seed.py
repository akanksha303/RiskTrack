import json
from datetime import datetime, timedelta
from database import engine, SessionLocal, Base
from db_models import User, Transaction, RiskEvaluation

def seed_db():
    # Recreate tables (or ensure they exist)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if database is already seeded
    if db.query(User).count() > 0:
        print("Database already seeded.")
        db.close()
        return

    print("Seeding database with mock data...")

    # Define User Baselines
    users = [
        User(
            id="USR1001",
            name="Rahul Sharma",
            avg_amount=1500.0,
            std_dev_amount=300.0,
            last_location_lat=19.0760,  # Mumbai
            last_location_lon=72.8777,
            last_transaction_time=datetime.utcnow() - timedelta(hours=6),
            common_hours="9,10,11,12,13,14,15,16,17,18,19,20,21"
        ),
        User(
            id="USR1002",
            name="Priya Patel",
            avg_amount=8500.0,
            std_dev_amount=1500.0,
            last_location_lat=51.5074,  # London
            last_location_lon=-0.1278,
            last_transaction_time=datetime.utcnow() - timedelta(hours=12),
            common_hours="10,11,12,13,14,15,16,17,18,19,20,21,22"
        ),
        User(
            id="USR1003",
            name="Vikram Malhotra",
            avg_amount=45000.0,
            std_dev_amount=8000.0,
            last_location_lat=37.7749,  # San Francisco
            last_location_lon=-122.4194,
            last_transaction_time=datetime.utcnow() - timedelta(days=1),
            common_hours="8,9,10,11,12,13,14,15,16,17,18"
        )
    ]

    for user in users:
        db.add(user)
    db.commit()

    # Seed Historical Transactions for USR1001 (Rahul Sharma - Mumbai)
    # This sets up historical averages and locations
    t_base = datetime.utcnow() - timedelta(days=5)
    
    txs_rahul = [
        Transaction(
            id="TXN1001",
            user_id="USR1001",
            amount=1420.0,
            currency="INR",
            merchant="Star Coffee",
            location_lat=19.0770,
            location_lon=72.8780,
            timestamp=t_base
        ),
        Transaction(
            id="TXN1002",
            user_id="USR1001",
            amount=1650.0,
            currency="INR",
            merchant="DMart Mall",
            location_lat=19.0820,
            location_lon=72.8820,
            timestamp=t_base + timedelta(days=1, hours=2)
        ),
        Transaction(
            id="TXN1003",
            user_id="USR1001",
            amount=1200.0,
            currency="INR",
            merchant="Amazon India",
            location_lat=19.0760,
            location_lon=72.8777,
            timestamp=t_base + timedelta(days=2, hours=5)
        ),
        Transaction(
            id="TXN1004",
            user_id="USR1001",
            amount=1550.0,
            currency="INR",
            merchant="Star Coffee",
            location_lat=19.0770,
            location_lon=72.8780,
            timestamp=t_base + timedelta(days=3, hours=1)
        ),
        Transaction(
            id="TXN1005",
            user_id="USR1001",
            amount=1480.0,
            currency="INR",
            merchant="Ola Cabs",
            location_lat=19.0750,
            location_lon=72.8710,
            timestamp=t_base + timedelta(days=4, hours=4)
        )
    ]

    # Seed Historical Transactions for USR1002 (Priya Patel - London)
    txs_priya = [
        Transaction(
            id="TXN2001",
            user_id="USR1002",
            amount=7800.0,
            currency="INR",
            merchant="Tesco Express",
            location_lat=51.5080,
            location_lon=-0.1290,
            timestamp=t_base
        ),
        Transaction(
            id="TXN2002",
            user_id="USR1002",
            amount=9200.0,
            currency="INR",
            merchant="Zara London",
            location_lat=51.5120,
            location_lon=-0.1410,
            timestamp=t_base + timedelta(days=1, hours=3)
        ),
        Transaction(
            id="TXN2003",
            user_id="USR1002",
            amount=8500.0,
            currency="INR",
            merchant="Marks & Spencer",
            location_lat=51.5074,
            location_lon=-0.1278,
            timestamp=t_base + timedelta(days=2, hours=6)
        ),
        Transaction(
            id="TXN2004",
            user_id="USR1002",
            amount=22000.0,  # High, but let's check it as a historical outlier
            currency="INR",
            merchant="British Airways",
            location_lat=51.4700, # Heathrow
            location_lon=-0.4543,
            timestamp=t_base + timedelta(days=3, hours=2)
        )
    ]

    # Seed Historical Transactions for USR1003 (Vikram Malhotra - SF)
    txs_vikram = [
        Transaction(
            id="TXN3001",
            user_id="USR1003",
            amount=42000.0,
            currency="INR",
            merchant="Apple Store SF",
            location_lat=37.7850,
            location_lon=-122.4080,
            timestamp=t_base
        ),
        Transaction(
            id="TXN3002",
            user_id="USR1003",
            amount=48000.0,
            currency="INR",
            merchant="AWS Cloud Billing",
            location_lat=37.7749,
            location_lon=-122.4194,
            timestamp=t_base + timedelta(days=2, hours=4)
        )
    ]

    all_txs = txs_rahul + txs_priya + txs_vikram
    for tx in all_txs:
        db.add(tx)
    db.commit()

    # Pre-evaluate and seed evaluations for all seeded historical transactions so the dashboard has historical logs
    print("Evaluating historical transactions...")
    from rules import evaluate_transaction as eval_txn
    
    for tx in all_txs:
        # Retrieve user record
        user_rec = db.query(User).filter(User.id == tx.user_id).first()
        # Compute risk
        eval_res = eval_txn(
            db=db,
            user=user_rec,
            amount=tx.amount,
            merchant=tx.merchant,
            lat=tx.location_lat,
            lon=tx.location_lon,
            timestamp=tx.timestamp
        )
        
        evaluation = RiskEvaluation(
            transaction_id=tx.id,
            risk_score=eval_res["risk_score"],
            decision=eval_res["decision"],
            velocity_score=eval_res["velocity_score"],
            amount_anomaly_score=eval_res["amount_anomaly_score"],
            geo_mismatch_score=eval_res["geo_mismatch_score"],
            unusual_hour_score=eval_res["unusual_hour_score"],
            new_merchant_score=eval_res["new_merchant_score"],
            reasons=json.dumps(eval_res["reasons"]),
            evaluated_at=tx.timestamp
        )
        db.add(evaluation)
        
        # Update user's last known location and time
        user_rec.last_location_lat = tx.location_lat
        user_rec.last_location_lon = tx.location_lon
        user_rec.last_transaction_time = tx.timestamp
        db.add(user_rec)

    db.commit()
    print("Database seeding completed successfully.")
    db.close()

if __name__ == "__main__":
    seed_db()
