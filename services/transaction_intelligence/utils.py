"""
Kavalx Transaction Intelligence Service - Feature Extraction Utilities
Implements velocity calculation, haversine geo-distance, amount statistics,
and composite risk scoring.
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger("kavalx.tis.utils")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance between two points on Earth
    using the Haversine formula.

    Args:
        lat1, lon1: Coordinates of point 1 in decimal degrees.
        lat2, lon2: Coordinates of point 2 in decimal degrees.

    Returns:
        Distance in kilometres.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def calculate_amount_log(amount_paise: int) -> float:
    """Convert paise to INR and return log10.  Returns 0 for non-positive amounts."""
    inr = amount_paise / 100.0
    if inr <= 0:
        return 0.0
    return round(math.log10(inr), 6)


def calculate_velocity(
    timestamps: list[datetime],
    now: datetime,
    window_seconds: int,
) -> int:
    """
    Count how many timestamps fall within [now - window, now].

    Args:
        timestamps: List of transaction timestamps (need not be sorted).
        now: Current reference time.
        window_seconds: Look-back window in seconds.

    Returns:
        Number of events within the window.
    """
    cutoff = now - timedelta(seconds=window_seconds)
    return sum(1 for ts in timestamps if cutoff <= ts <= now)


def count_unique_receivers(
    receiver_list: list[str],
) -> int:
    """Return the number of unique receivers."""
    return len(set(receiver_list))


def calculate_amount_stats(amounts_paise: list[int]) -> tuple[float, float]:
    """
    Compute mean and standard deviation of transaction amounts (in INR).

    Args:
        amounts_paise: List of amounts in paise.

    Returns:
        Tuple of (mean_inr, stddev_inr).
    """
    if not amounts_paise:
        return 0.0, 0.0

    inr_values = np.array(amounts_paise, dtype=np.float64) / 100.0
    mean_val = float(np.mean(inr_values))
    std_val = float(np.std(inr_values, ddof=0))
    return round(mean_val, 2), round(std_val, 2)


def compute_time_delta(
    last_timestamp: Optional[datetime],
    current_timestamp: datetime,
) -> float:
    """
    Seconds elapsed since the last transaction by the same account.

    Returns 86400 (24 hours) if no prior transaction exists.
    """
    if last_timestamp is None:
        return 86400.0
    delta = (current_timestamp - last_timestamp).total_seconds()
    return max(delta, 0.0)


def compute_device_age_days(
    first_seen: Optional[datetime],
    now: datetime,
) -> int:
    """Days since the device fingerprint was first observed."""
    if first_seen is None:
        return 0
    return max(int((now - first_seen).total_seconds() / 86400), 0)


def compute_risk_score(
    amount_log: float,
    time_delta: float,
    velocity_1h: int,
    velocity_24h: int,
    unique_receivers_1h: int,
    avg_amount_7d: float,
    stddev_amount_7d: float,
    is_new_receiver: bool,
    device_age_days: int,
    geo_distance_km: float,
) -> float:
    """
    Compute a heuristic risk score ∈ [0, 1] from the extracted feature vector.

    Uses a weighted logistic combination of normalized features.  In production
    this would be replaced by the TGN / XGBoost model output; this heuristic
    provides a reasonable baseline.

    Feature weights (tuned empirically):
        - High velocity (1h)        → +risk
        - Many unique receivers     → +risk
        - New receiver              → +risk
        - Low time delta            → +risk (burst)
        - Large deviation from avg  → +risk
        - Short device age          → +risk
        - Large geo distance        → +risk
    """
    signals: list[float] = []

    # Velocity risk: sigmoid of velocity_1h centered at 5
    vel_signal = 1.0 / (1.0 + math.exp(-(velocity_1h - 5) / 2.0))
    signals.append(vel_signal * 0.20)

    # Unique receivers risk
    recv_signal = min(unique_receivers_1h / 10.0, 1.0)
    signals.append(recv_signal * 0.10)

    # New receiver
    signals.append(0.10 if is_new_receiver else 0.0)

    # Time delta risk: < 30 seconds is suspicious
    if time_delta < 30:
        td_signal = 1.0 - (time_delta / 30.0)
    else:
        td_signal = 0.0
    signals.append(td_signal * 0.15)

    # Amount deviation risk
    current_inr = 10 ** amount_log if amount_log > 0 else 0
    if stddev_amount_7d > 0:
        z_score = abs(current_inr - avg_amount_7d) / stddev_amount_7d
        amount_signal = min(z_score / 3.0, 1.0)
    elif avg_amount_7d > 0:
        ratio = current_inr / avg_amount_7d
        amount_signal = min(max(ratio - 1.0, 0.0) / 5.0, 1.0)
    else:
        amount_signal = 0.3  # no history → moderate risk
    signals.append(amount_signal * 0.20)

    # Device age risk: new devices are riskier
    if device_age_days < 1:
        dev_signal = 1.0
    elif device_age_days < 7:
        dev_signal = 0.5
    elif device_age_days < 30:
        dev_signal = 0.2
    else:
        dev_signal = 0.0
    signals.append(dev_signal * 0.10)

    # Geo distance risk: > 100 km is unusual
    geo_signal = min(geo_distance_km / 500.0, 1.0) if geo_distance_km > 10 else 0.0
    signals.append(geo_signal * 0.15)

    raw_score = sum(signals)
    # Clamp to [0, 1]
    return round(min(max(raw_score, 0.0), 1.0), 4)


def build_feature_vector_from_history(
    event_id: str,
    src_account: str,
    amount_paise: int,
    current_ts: datetime,
    lat: Optional[float],
    lon: Optional[float],
    device_fingerprint: str,
    history_timestamps: list[datetime],
    history_amounts: list[int],
    history_receivers: list[str],
    dst_account: str,
    last_lat: Optional[float],
    last_lon: Optional[float],
    device_first_seen: Optional[datetime],
) -> dict:
    """
    Build a complete feature dict from raw event data and historical context.

    Returns a dict suitable for constructing a FeatureVector model.
    """
    amount_log = calculate_amount_log(amount_paise)
    velocity_1h = calculate_velocity(history_timestamps, current_ts, 3600)
    velocity_24h = calculate_velocity(history_timestamps, current_ts, 86400)
    unique_receivers_1h_count = count_unique_receivers(history_receivers)
    avg_7d, std_7d = calculate_amount_stats(history_amounts)
    time_delta = compute_time_delta(
        history_timestamps[-1] if history_timestamps else None,
        current_ts,
    )
    is_new = dst_account not in set(history_receivers)
    device_age = compute_device_age_days(device_first_seen, current_ts)

    geo_dist = 0.0
    if lat is not None and lon is not None and last_lat is not None and last_lon is not None:
        geo_dist = haversine_km(last_lat, last_lon, lat, lon)

    risk = compute_risk_score(
        amount_log=amount_log,
        time_delta=time_delta,
        velocity_1h=velocity_1h,
        velocity_24h=velocity_24h,
        unique_receivers_1h=unique_receivers_1h_count,
        avg_amount_7d=avg_7d,
        stddev_amount_7d=std_7d,
        is_new_receiver=is_new,
        device_age_days=device_age,
        geo_distance_km=geo_dist,
    )

    return {
        "event_id": event_id,
        "src_account": src_account,
        "amount_log": amount_log,
        "time_delta": time_delta,
        "velocity_1h": velocity_1h,
        "velocity_24h": velocity_24h,
        "unique_receivers_1h": unique_receivers_1h_count,
        "avg_amount_7d": avg_7d,
        "stddev_amount_7d": std_7d,
        "is_new_receiver": is_new,
        "device_age_days": device_age,
        "geo_distance_km": round(geo_dist, 2),
        "risk_score": risk,
    }
