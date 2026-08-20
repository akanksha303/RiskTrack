import unittest
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from db_models import User, Transaction, RiskEvaluation
from rules import evaluate_transaction, haversine_distance

class TestRiskEngineRules(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for unit testing
        self.engine = create_engine("sqlite:///:memory:")
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        Base.metadata.create_all(self.engine)

        # Create a test user
        self.test_user = User(
            id="USR9999",
            name="Test User",
            avg_amount=1000.0,
            std_dev_amount=200.0,
            last_location_lat=19.0,
            last_location_lon=72.0,
            last_transaction_time=datetime.utcnow() - timedelta(days=1),
            common_hours="9,10,11,12,13,14,15,16,17,18"
        )
        self.db.add(self.test_user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_standard_transaction(self):
        """A normal transaction within baseline parameters should be APPROVED with low score"""
        now = datetime.utcnow().replace(hour=12) # 12:00 PM is a common hour
        res = evaluate_transaction(
            db=self.db,
            user=self.test_user,
            amount=1000.0,      # Equal to average
            merchant="Merchant A",
            lat=19.001,         # Very close to last location
            lon=72.001,
            timestamp=now
        )
        
        # New merchant rule triggers (40 points) -> weight 10% = 4 points.
        # Velocity = 0, Amount = 0, Geo = 0, Hour = 0, Merchant = 40.
        # Weighted score: 40 * 0.1 = 4.0 -> rounded to 4.
        self.assertEqual(res["risk_score"], 4)
        self.assertEqual(res["decision"], "APPROVE")
        self.assertEqual(res["new_merchant_score"], 40)
        self.assertEqual(res["velocity_score"], 0)

    def test_amount_anomaly(self):
        """A transaction with a massive amount spike should trigger high amount anomaly score"""
        now = datetime.utcnow().replace(hour=12)
        
        # 4.5x average amount (exceeds avg + 3*std_dev = 1600.0)
        res = evaluate_transaction(
            db=self.db,
            user=self.test_user,
            amount=4500.0,
            merchant="Merchant A",
            lat=19.001,
            lon=72.001,
            timestamp=now
        )
        
        # Should flag amount anomaly critical (100 points)
        self.assertEqual(res["amount_anomaly_score"], 100)
        # Weighted score: Amount (100 * 0.25) + Merchant (40 * 0.1) = 25 + 4 = 29.
        self.assertEqual(res["risk_score"], 29)
        self.assertEqual(res["decision"], "APPROVE") # still approve because other scores are 0

    def test_impossible_travel(self):
        """A transaction from an impossible location within minutes should trigger geo mismatch score"""
        now = datetime.utcnow().replace(hour=12)
        
        # Log a transaction at 12:00 PM in Mumbai (19.0, 72.0)
        prev_tx = Transaction(
            id="TXN_PREV",
            user_id=self.test_user.id,
            amount=500.0,
            merchant="Merchant A",
            location_lat=19.0,
            location_lon=72.0,
            timestamp=now
        )
        self.db.add(prev_tx)
        self.db.commit()

        # Place current transaction at 12:05 PM in London (51.5, -0.1) -> 5 mins later, distance > 7000 km
        res = evaluate_transaction(
            db=self.db,
            user=self.test_user,
            amount=1000.0,
            merchant="Merchant B",
            lat=51.5,
            lon=-0.1,
            timestamp=now + timedelta(minutes=5)
        )
        
        # Should flag geo mismatch critical (100 points)
        self.assertEqual(res["geo_mismatch_score"], 100)
        # New merchant triggers (40 points)
        # Weighted score: Geo (100 * 0.25) + Merchant (40 * 0.1) = 25 + 4 = 29.
        self.assertEqual(res["risk_score"], 29)

    def test_velocity_check(self):
        """Multiple rapid-fire transactions should trigger high velocity score"""
        now = datetime.utcnow().replace(hour=12)
        
        # Seed 3 prior transactions in the last 5 minutes
        for i in range(3):
            tx = Transaction(
                id=f"TXN_VEL_{i}",
                user_id=self.test_user.id,
                amount=200.0,
                merchant="Merchant A",
                location_lat=19.0,
                location_lon=72.0,
                timestamp=now - timedelta(minutes=4-i)
            )
            self.db.add(tx)
        self.db.commit()

        # Current transaction at "now" (which represents the 4th transaction in 10 minutes)
        res = evaluate_transaction(
            db=self.db,
            user=self.test_user,
            amount=800.0,
            merchant="Merchant A",  # existing merchant (0 points)
            lat=19.0,
            lon=72.0,
            timestamp=now
        )
        
        # Velocity score should be critical (100 points for count > 3)
        self.assertEqual(res["velocity_score"], 100)
        # Weighted score: Velocity (100 * 0.3) = 30 points.
        self.assertEqual(res["risk_score"], 30)

    def test_unusual_hour(self):
        """A transaction at 3 AM today should trigger an unusual hour penalty"""
        # Set transaction time to 3:00 AM (unusual hour)
        unusual_time = datetime.utcnow().replace(hour=3, minute=0, second=0)
        
        res = evaluate_transaction(
            db=self.db,
            user=self.test_user,
            amount=1000.0,
            merchant="Merchant A",
            lat=19.001,
            lon=72.001,
            timestamp=unusual_time
        )
        
        self.assertEqual(res["unusual_hour_score"], 50) # 50 points for 3 AM late night
        # Weighted score: Hour (50 * 0.1) + Merchant (40 * 0.1) = 5 + 4 = 9.
        self.assertEqual(res["risk_score"], 9)

if __name__ == "__main__":
    unittest.main()
