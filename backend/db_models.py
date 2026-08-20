from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary key=True, index=True)
    name = Column(String, nullable=False)
    avg_amount = Column(Float, default=1000.0)
    std_dev_amount = Column(Float, default=200.0)
    last_location_lat = Column(Float, nullable=True)
    last_location_lon = Column(Float, nullable=True)
    last_transaction_time = Column(DateTime, nullable=True)
    common_hours = Column(String, default="9,10,11,12,13,14,15,16,17,18,19,20")  # comma separated hours

    transactions = relationship("Transaction", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    merchant = Column(String, nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lon = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    evaluation = relationship("RiskEvaluation", uselist=False, back_populates="transaction")

class RiskEvaluation(Base):
    __tablename__ = "risk_evaluations"

    id = Column(Integer, primary key=True, index=True, autoincrement=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    risk_score = Column(Integer, nullable=False)  # 0 to 100
    decision = Column(String, nullable=False)  # APPROVE, REVIEW, BLOCK
    
    # Individual rule scores
    velocity_score = Column(Integer, default=0)
    amount_anomaly_score = Column(Integer, default=0)
    geo_mismatch_score = Column(Integer, default=0)
    unusual_hour_score = Column(Integer, default=0)
    new_merchant_score = Column(Integer, default=0)
    
    # JSON list of reasoning statements
    reasons = Column(String, default="[]")
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow)

    transaction = relationship("Transaction", back_populates="evaluation")
