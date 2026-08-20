from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TransactionCreate(BaseModel):
    user_id: str
    amount: float
    currency: str = "INR"
    merchant: str
    location_lat: float
    location_lon: float
    timestamp: Optional[datetime] = None

class RiskEvaluationDetail(BaseModel):
    velocity_score: int
    amount_anomaly_score: int
    geo_mismatch_score: int
    unusual_hour_score: int
    new_merchant_score: int
    reasons: List[str]
    risk_score: int
    decision: str
    evaluated_at: datetime

class TransactionResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    amount: float
    currency: str
    merchant: str
    location_lat: float
    location_lon: float
    timestamp: datetime
    evaluation: Optional[RiskEvaluationDetail] = None

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str
    name: str
    avg_amount: float
    std_dev_amount: float
    last_location_lat: Optional[float] = None
    last_location_lon: Optional[float] = None
    last_transaction_time: Optional[datetime] = None
    common_hours: str

    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    total_transactions: int
    approved_count: int
    review_count: int
    blocked_count: int
    approval_rate: float
    risk_buckets: List[int]  # [0-20, 21-40, 41-60, 61-80, 81-100]
    hourly_trends: List[dict]  # list of {"hour": int, "avg_risk": float, "count": int}
    recent_transactions: List[TransactionResponse]
