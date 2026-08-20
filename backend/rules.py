import math
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db_models import User, Transaction

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    R = 6371.0  # Earth radius in kilometers

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def evaluate_transaction(db: Session, user: User, amount: float, merchant: str, lat: float, lon: float, timestamp: datetime):
    reasons = []
    
    # 1. Velocity Check (Transactions in the last 10 minutes)
    ten_minutes_ago = timestamp - timedelta(minutes=10)
    recent_txs_count = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.timestamp >= ten_minutes_ago,
        Transaction.timestamp < timestamp
    ).count()

    velocity_score = 0
    if recent_txs_count == 2:
        velocity_score = 30
        reasons.append(f"Velocity warning: 2 transactions in the last 10 minutes.")
    elif recent_txs_count == 3:
        velocity_score = 70
        reasons.append(f"High velocity: 3 transactions in the last 10 minutes.")
    elif recent_txs_count > 3:
        velocity_score = 100
        reasons.append(f"Critical velocity: {recent_txs_count} transactions in the last 10 minutes.")
    else:
        reasons.append("Velocity check: Normal transaction frequency.")

    # 2. Amount Anomaly Check
    amount_ratio = amount / user.avg_amount if user.avg_amount > 0 else 1.0
    amount_anomaly_score = 0
    
    # Check by absolute standard deviation if possible, otherwise use ratio
    if user.std_dev_amount > 0:
        z_score = (amount - user.avg_amount) / user.std_dev_amount
        if z_score > 3.0:
            amount_anomaly_score = 100
            reasons.append(f"Critical amount anomaly: Amount ₹{amount:,.2f} is {z_score:.1f} standard deviations above average (User Avg: ₹{user.avg_amount:,.2f}).")
        elif z_score > 2.0:
            amount_anomaly_score = 70
            reasons.append(f"High amount anomaly: Amount ₹{amount:,.2f} is {z_score:.1f} standard deviations above average (User Avg: ₹{user.avg_amount:,.2f}).")
        elif z_score > 1.5:
            amount_anomaly_score = 30
            reasons.append(f"Moderate amount anomaly: Amount ₹{amount:,.2f} is {z_score:.1f} standard deviations above average (User Avg: ₹{user.avg_amount:,.2f}).")
        else:
            reasons.append(f"Amount check: Value ₹{amount:,.2f} is within normal parameters (User Avg: ₹{user.avg_amount:,.2f}).")
    else:
        # Fallback to ratio
        if amount_ratio > 4.0:
            amount_anomaly_score = 100
            reasons.append(f"Critical amount anomaly: Amount ₹{amount:,.2f} is {amount_ratio:.1f}x higher than user's average (User Avg: ₹{user.avg_amount:,.2f}).")
        elif amount_ratio > 2.5:
            amount_anomaly_score = 70
            reasons.append(f"High amount anomaly: Amount ₹{amount:,.2f} is {amount_ratio:.1f}x higher than user's average (User Avg: ₹{user.avg_amount:,.2f}).")
        elif amount_ratio > 1.5:
            amount_anomaly_score = 30
            reasons.append(f"Moderate amount anomaly: Amount ₹{amount:,.2f} is {amount_ratio:.1f}x higher than user's average (User Avg: ₹{user.avg_amount:,.2f}).")
        else:
            reasons.append(f"Amount check: Value ₹{amount:,.2f} is within normal parameters (User Avg: ₹{user.avg_amount:,.2f}).")

    # 3. Geo Mismatch Check
    geo_mismatch_score = 0
    
    # Query user's last transaction
    last_tx = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.timestamp < timestamp
    ).order_by(Transaction.timestamp.desc()).first()

    # Fallback to User baseline location if no transaction in database yet
    last_lat = last_tx.location_lat if last_tx else user.last_location_lat
    last_lon = last_tx.location_lon if last_tx else user.last_location_lon
    last_time = last_tx.timestamp if last_tx else user.last_transaction_time

    if last_lat is not None and last_lon is not None:
        distance = haversine_distance(last_lat, last_lon, lat, lon)
        
        if last_time:
            time_diff_hours = (timestamp - last_time).total_seconds() / 3600.0
        else:
            time_diff_hours = 24.0  # assume long time ago if no timestamp

        # Guard against zero division
        if time_diff_hours <= 0.001:
            time_diff_hours = 0.001

        implied_speed = distance / time_diff_hours

        # Impossible travel velocity threshold
        if distance > 1.0:  # only check speed if distance is > 1km
            if implied_speed > 800.0:
                geo_mismatch_score = 100
                reasons.append(f"Impossible Travel: Distance of {distance:.1f} km since last transaction would require an implied speed of {implied_speed:.1f} km/h (Limit: 800 km/h).")
            elif implied_speed > 150.0:
                geo_mismatch_score = 70
                reasons.append(f"Unusual Geo Speed: Distance of {distance:.1f} km since last transaction implies travel speed of {implied_speed:.1f} km/h.")
            elif implied_speed > 80.0:
                geo_mismatch_score = 30
                reasons.append(f"Moderate Geo Speed: Distance of {distance:.1f} km since last transaction implies travel speed of {implied_speed:.1f} km/h.")
            else:
                reasons.append(f"Geo check: Location is {distance:.1f} km from last known position (Speed: {implied_speed:.1f} km/h - within normal range).")
        else:
            reasons.append("Geo check: Position matches last known location.")
    else:
        reasons.append("Geo check: No previous location data available. Setting as new baseline.")

    # 4. Unusual Hour Check
    unusual_hour_score = 0
    current_hour = timestamp.hour
    
    # Parse common hours list
    common_hours_list = []
    if user.common_hours:
        try:
            common_hours_list = [int(h.strip()) for h in user.common_hours.split(",") if h.strip().isdigit()]
        except Exception:
            common_hours_list = list(range(9, 21)) # default 9am-8pm
            
    if current_hour not in common_hours_list:
        # Check if it's late-night (1 AM to 5 AM) which is inherently suspicious if not common
        if 1 <= current_hour <= 5:
            unusual_hour_score = 50
            reasons.append(f"Late Night Outlier: Transaction at {current_hour}:00 AM is outside user's common active window ({user.common_hours}).")
        else:
            unusual_hour_score = 25
            reasons.append(f"Unusual Hour: Transaction at {current_hour}:00 is outside user's usual profile window ({user.common_hours}).")
    else:
        reasons.append(f"Time check: Transaction at {current_hour}:00 is within user's usual profile window.")

    # 5. New Merchant Check
    new_merchant_score = 0
    merchant_count = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.merchant.ilike(merchant)
    ).count()

    if merchant_count == 0:
        new_merchant_score = 40
        reasons.append(f"New Merchant: User has no previous transaction history with '{merchant}'.")
    else:
        reasons.append(f"Merchant check: User has completed {merchant_count} prior transactions with '{merchant}'.")

    # Weighted Score calculation
    weighted_score = (
        velocity_score * 0.30 +
        amount_anomaly_score * 0.25 +
        geo_mismatch_score * 0.25 +
        unusual_hour_score * 0.10 +
        new_merchant_score * 0.10
    )
    
    risk_score = min(100, max(0, int(round(weighted_score))))

    # Decision Matrix
    if risk_score >= 70:
        decision = "BLOCK"
    elif risk_score >= 35:
        decision = "REVIEW"
    else:
        decision = "APPROVE"

    return {
        "risk_score": risk_score,
        "decision": decision,
        "velocity_score": velocity_score,
        "amount_anomaly_score": amount_anomaly_score,
        "geo_mismatch_score": geo_mismatch_score,
        "unusual_hour_score": unusual_hour_score,
        "new_merchant_score": new_merchant_score,
        "reasons": reasons
    }
