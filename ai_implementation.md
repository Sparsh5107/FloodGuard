# FloodGuard AI Prediction System — Complete Implementation Plan

> **Status**: Planning Complete — Ready for Phase-by-Phase Implementation
> **Date**: August 2026
> **Stack**: Django + Django Templates + SQLite + ESP32 + scikit-learn

---

## TABLE OF CONTENTS

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Proposed Architecture](#2-proposed-architecture)
3. [Weather Risk Engine Design](#3-weather-risk-engine-design)
4. [Full Flood Prediction Engine Design](#4-full-flood-prediction-engine-design)
5. [Anomaly Detection Design](#5-anomaly-detection-design)
6. [Water-Level Forecasting Design](#6-water-level-forecasting-design-time-to-flood)
7. [Data Strategy](#7-data-strategy)
8. [Weather API Recommendation](#8-weather-api-recommendation)
9. [ML Model Comparison](#9-ml-model-comparison)
10. [Recommended ML Architecture](#10-recommended-ml-architecture-summary)
11. [Feature Engineering Plan](#11-feature-engineering-plan)
12. [Database Changes](#12-database-changes)
13. [Django Module Structure](#13-django-module-structure)
14. [Prediction Data Flow](#14-prediction-data-flow)
15. [Explainable AI Design](#15-explainable-ai-design)
16. [Dashboard Plan](#16-dashboard-plan)
17. [What-If Simulator Plan](#17-what-if-flood-simulator-plan)
18. [Evaluation Strategy](#18-evaluation-strategy)
19. [Failure and Safety Handling](#19-failure-and-safety-handling)
20. [Hackathon MVP Priorities](#20-hackathon-mvp-priorities)
21. [Future Roadmap](#21-future-roadmap)
22. [Exact Implementation Phases](#22-exact-implementation-phases)

---

## 1. CURRENT ARCHITECTURE ANALYSIS

### Project Structure
```
backend/
├── floodguard/          # Django project (settings.py, urls.py, wsgi.py)
├── core/                # Domain app: models, views, weather, notifications
├── api/                 # REST app: DRF ViewSets, ESP32 endpoint
├── templates/           # base.html, dashboard.html, data.html, map.html, email template
├── static/css/          # style.css (1692 lines)
├── static/js/           # dashboard.js, data-charts.js, map.js
├── db.sqlite3
├── manage.py
└── requirements.txt
```

### Models (5 tables + 1 M2M)

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Sensor` | ESP32 device registry | `device_id` (unique), `name`, `location`, `latitude`, `longitude`, `is_active`, `last_seen` |
| `WaterLevel` | Time-series readings | `sensor` (FK), `level_cm`, `timestamp`, `is_alert` |
| `Alert` | Threshold breach events | `sensor` (FK), `water_level` (FK), `alert_type` (warning/danger/critical), `message`, `is_resolved` |
| `NotificationRecipient` | Email alert config | `name`, `email`, `alert_types` (JSON), `sensors` (M2M) |
| `NotificationLog` | Delivery audit trail | `alert` (FK), `channel`, `recipient`, `status`, `error_message` |

### ESP32 Data Flow (Verified)
```
ESP32 → POST /api/sensor-data/ {device_id, level_cm}
  → validate + lookup Sensor by device_id
  → update sensor.last_seen
  → smart logging: skip if <5cm change AND <5min elapsed
  → create WaterLevel record (is_alert if >=30cm)
  → if threshold breached: create Alert (warning>=30, danger>=50, critical>=70)
  → async email via ThreadPoolExecutor
  → return {status, reading_id}
```

### What Already Exists

- `core/weather.py::get_current_weather()` — fetches current conditions from Open-Meteo. **Defined but never called from any view.**
- `requirements.txt` — clean. Only Django, DRF, cors-headers, python-dotenv, requests.
- Alert thresholds: 30cm (warning), 50cm (danger), 70cm (critical) — hardcoded in `api/views.py`
- Offline detection: 2-second `last_seen` timeout
- Real-time polling: JS polls `/api/sensor-status/` every 2 seconds
- No authentication on API endpoints (AllowAny)
- No background task infrastructure (no Celery, no APScheduler)

---

## 2. PROPOSED ARCHITECTURE

### Design Philosophy

- **Two-layer prediction**: Weather Risk (early warning) + Full Flood Prediction (confirmed risk)
- **Separation of concerns**: ML logic lives in its own app, never in views.py
- **Incremental delivery**: Each component works independently
- **Failure-safe**: Missing data → low confidence, never false certainty

### New Django App: `prediction`

```
prediction/
├── __init__.py
├── apps.py
├── admin.py
├── models.py                    # DB tables for storing predictions
├── urls.py                      # /api/predictions/, /predictions/ page
├── views.py                     # API endpoints + web view
│
├── weather/
│   ├── __init__.py
│   ├── service.py               # Open-Meteo API client (forecast + hourly)
│   └── risk_engine.py           # Weather Risk scoring (rule-based)
│
├── ml/
│   ├── __init__.py
│   ├── features.py              # Feature engineering pipeline
│   ├── flood_model.py           # Full flood prediction (Random Forest)
│   ├── anomaly_detector.py      # Anomaly detection (Isolation Forest)
│   ├── water_level_predictor.py # Time-to-flood estimation (regression)
│   └── explainer.py             # SHAP-like feature importance explanations
│
├── services/
│   ├── __init__.py
│   ├── prediction_service.py    # Orchestrator: combines all engines
│   ├── model_loader.py          # Loads persisted .pkl models
│   └── train.py                 # Training pipeline (management command)
│
├── management/
│   └── commands/
│       └── train_models.py      # python manage.py train_models
│
├── ml_models/                   # Persisted model files
│   ├── flood_model.pkl
│   ├── anomaly_model.pkl
│   └── water_level_model.pkl
│
└── templates/
    └── predictions.html         # Dashboard page (extends base.html)

static/
├── js/predictions.js            # Fetch + render predictions
└── css/style.css                # Additions only (prediction cards, charts)
```

### Why a Separate App

| Reason | Explanation |
|--------|-------------|
| Clean boundaries | `core` handles sensor data, `prediction` handles AI logic |
| Independent testing | ML components can be tested without ESP32 |
| No risk to existing code | Zero changes to `api/views.py`, `core/models.py`, ESP32 flow |
| Easy removal | Delete one app if predictions aren't needed |

---

## 3. WEATHER RISK ENGINE DESIGN

### Purpose

> "Based on upcoming weather, could flood conditions develop?"

This is a **rule-based scoring system**, not ML. It works immediately with zero training data.

### Why Rule-Based (Not ML) for Weather Risk

| Factor | Rule-Based | ML |
|--------|-----------|-----|
| Training data needed | None | Thousands of labeled examples |
| Works on day 1 | Yes | No |
| Explainability | Perfect | Requires SHAP |
| Accuracy for weather-only | Excellent (deterministic thresholds) | Marginally better |
| Hackathon feasibility | 2 hours | 2+ days |

### Scoring Algorithm

```python
def calculate_weather_risk(weather_data: dict) -> dict:
    """
    Returns weather_risk (0-100), risk_level, and contributing factors.

    Inputs from Open-Meteo hourly forecast:
    - precipitation_probability (0-100%)
    - precipitation (mm/h)
    - rain (mm/h)
    - humidity (%)
    - cloud_cover (%)
    - weather_code (WMO code)
    """

    score = 0
    factors = []

    # 1. Precipitation probability (0-30 points)
    #    - <20%: 0 points
    #    - 20-50%: 10 points
    #    - 50-80%: 20 points
    #    - >80%: 30 points

    # 2. Expected rainfall intensity (0-30 points)
    #    - 0 mm/h: 0 points
    #    - 0-2 mm/h (light): 5 points
    #    - 2-7 mm/h (moderate): 15 points
    #    - 7-20 mm/h (heavy): 25 points
    #    - >20 mm/h (extreme): 30 points

    # 3. Rainfall accumulation 1h/3h/6h (0-20 points)
    #    - Weighted sum of forecast accumulation windows

    # 4. Weather condition severity (0-10 points)
    #    - Thunderstorm codes (95,96,99): 10 points
    #    - Heavy rain codes (65,82): 8 points
    #    - Moderate rain (63,81): 5 points
    #    - Light rain (61,80): 2 points

    # 5. Humidity and cloud cover (0-10 points)
    #    - humidity >90% AND cloud_cover >80%: 10 points (atmospheric saturation)

    return {
        "weather_risk": min(score, 100),
        "risk_level": classify_risk(score),
        "factors": factors,
        "data_quality": "good"  # or "partial" / "unavailable"
    }
```

### Risk Classification Thresholds

| Score | Level | Color | Meaning |
|-------|-------|-------|---------|
| 0-20 | LOW | Green | Dry conditions, no flood risk from weather |
| 20-40 | MODERATE | Yellow | Rain expected but not dangerous |
| 40-65 | ELEVATED | Orange | Significant rain expected, monitor closely |
| 65-85 | HIGH | Red | Heavy rain expected, flood conditions possible |
| 85-100 | CRITICAL | Dark Red | Extreme rainfall expected, flooding likely |

### Data Source: Open-Meteo (Already Integrated)

- **Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **API key required**: No
- **Rate limit**: 10,000 requests/day (free tier)
- **Variables needed**: `precipitation_probability`, `precipitation`, `rain`, `relative_humidity_2m`, `cloud_cover`, `weather_code`
- **Forecast horizon**: Up to 16 days hourly
- **Fallback**: If API fails, weather risk returns `data_quality: "unavailable"`

---

## 4. FULL FLOOD PREDICTION ENGINE DESIGN

### Purpose

> "Given weather + sensor data + history + anomalies, how likely is actual flooding?"

### Why Random Forest (Not Deep Learning)

| Factor | Random Forest | LSTM/GRU |
|--------|--------------|----------|
| Training data needed | ~100+ samples | ~10,000+ samples |
| Training time | Seconds | Minutes-hours |
| Overfitting risk | Low (ensemble averaging) | High with small data |
| Explainability | Built-in feature importance | Black box |
| Django integration | `joblib.dump/load` | Requires PyTorch/TensorFlow |
| Hackathon reliability | Very high | Unpredictable |

**Literature support**: Recent studies (Nature, 2026) show RF achieves AUC 0.96, XGBoost 0.97 for flood susceptibility. Random Forest is more robust to overfitting on small datasets.

### Model Architecture

```python
# Classification: Is this location going to flood?
# Input: feature vector (weather + sensor + history + anomaly)
# Output: flood_probability (0-100), risk_level

from sklearn.ensemble import RandomForestClassifier

model = RandomForestClassifier(
    n_estimators=100,        # 100 trees (fast, reliable)
    max_depth=10,            # Prevent overfitting
    min_samples_split=5,     # Need at least 5 samples to split
    min_samples_leaf=2,      # Leaf must have at least 2 samples
    class_weight='balanced', # Handle imbalanced classes (floods are rare)
    random_state=42
)
```

### Training Labels

Since we don't have historical flood labels, we generate them from existing data:

```python
def generate_labels(water_level_readings, thresholds):
    """
    Label each reading as:
    - 0: No risk (level < 30cm AND stable/falling)
    - 1: Low risk (level 30-50cm OR rising slowly)
    - 2: Moderate risk (level 50-70cm OR rising fast)
    - 3: High risk (level >70cm OR rising very fast)
    """
```

---

## 5. ANOMALY DETECTION DESIGN

### Purpose

> "Is the water-level behavior currently abnormal?"

### Recommended Approach: Rolling Z-Score (Statistical) — PRIMARY

**Why not Isolation Forest for MVP?**

| Factor | Rolling Z-Score | Isolation Forest |
|--------|----------------|-----------------|
| Setup complexity | Trivial (5 lines) | Moderate (sklearn import, fitting) |
| Real-time speed | O(1) per reading | O(n_estimators) per reading |
| Interpretability | "3.2 standard deviations above mean" | Anomaly score (-1 to 1) |
| Works with 10 readings | Yes | Unreliable |
| Works with 1000 readings | Yes | Yes |

**Recommendation**: Use rolling Z-score for MVP. Add Isolation Forest in Phase 2 when more data accumulates.

### Z-Score Algorithm

```python
def detect_anomaly(recent_readings: list[float], window: int = 20) -> dict:
    """
    recent_readings: last N water level readings (most recent last)
    window: how many readings to consider for "normal" baseline

    Returns:
        is_anomaly: bool
        anomaly_score: float (0-1, higher = more anomalous)
        z_score: float (standard deviations from mean)
        description: str
    """
    if len(recent_readings) < window:
        return {"is_anomaly": False, "anomaly_score": 0, "description": "Insufficient data"}

    recent = recent_readings[-window:]
    mean = np.mean(recent)
    std = np.std(recent) + 1e-6  # avoid division by zero

    current = recent_readings[-1]
    z_score = (current - mean) / std

    # Also check rate of change
    if len(recent_readings) >= 3:
        rate_1 = recent_readings[-1] - recent_readings[-2]
        rate_2 = recent_readings[-2] - recent_readings[-3]
        acceleration = rate_1 - rate_2
    else:
        acceleration = 0

    is_anomaly = abs(z_score) > 2.5 or acceleration > 5  # cm/read

    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": min(abs(z_score) / 5, 1.0),
        "z_score": round(z_score, 2),
        "rate_of_change": round(rate_1, 2),
        "acceleration": round(acceleration, 2),
        "description": describe_anomaly(z_score, rate_1, acceleration)
    }
```

### Anomaly Classification

| Z-Score | Rate (cm/reading) | Classification |
|---------|-------------------|----------------|
| < 2.5 | Any | NORMAL |
| > 2.5 | Positive | RAPID RISE |
| > 2.5 | Negative | RAPID DROP |
| Any | > 5 cm/step | SURGE ALERT |
| Any | acceleration > 3 | ACCELERATING |

---

## 6. WATER-LEVEL FORECASTING DESIGN (Time-to-Flood)

### Purpose

> "When will the water level reach critical threshold?"

### Recommended Approach: Linear Regression + Decay Model

**Why not LSTM/XGBoost for forecasting?**

| Factor | Linear Regression | LSTM |
|--------|------------------|------|
| Data needed | 10+ readings | 1000+ readings |
| Training time | Milliseconds | Minutes |
| Interpretability | "Rise rate = 1.8 cm/min" | Black box |
| Short-term accuracy | Excellent (5-30 min) | Better only at 1h+ |
| Hackathon reliability | Rock solid | Risky |

### Forecasting Algorithm

```python
def estimate_time_to_critical(
    current_level: float,
    rise_rate: float,           # cm per minute
    critical_threshold: float,  # 70 cm default
    max_forecast_minutes: int = 60
) -> dict:
    """
    Estimate when water level reaches critical threshold.

    Uses linear extrapolation with decay factor:
    - For next 15 minutes: assume current rate continues
    - For 15-60 minutes: apply 0.9 decay per 15-min block
    - Never predict beyond max_forecast_minutes
    """

    if rise_rate <= 0:
        return {"time_to_critical": None, "estimated_minutes": None, "confidence": "high"}

    distance = critical_threshold - current_level
    if distance <= 0:
        return {"time_to_critical": "ALREADY_EXCEEDED", "estimated_minutes": 0, "confidence": "high"}

    # Simple estimate
    simple_minutes = distance / rise_rate

    # Decay-adjusted estimate (rain intensity usually decreases)
    adjusted_minutes = simple_minutes * 1.2  # 20% safety margin

    if adjusted_minutes > max_forecast_minutes:
        confidence = "low"
    elif adjusted_minutes > 30:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "time_to_critical": format_time(adjusted_minutes),
        "estimated_minutes": round(adjusted_minutes, 1),
        "distance_to_critical": round(distance, 1),
        "current_rise_rate": round(rise_rate, 2),
        "confidence": confidence,
    }
```

### Multi-Horizon Forecast

```python
def forecast_water_levels(readings, timestamps, horizons=[5, 10, 15, 30, 60]):
    """
    Predict water level at future time points.

    Method: Linear regression on recent readings + decay
    Returns: {5: 42.3, 10: 44.1, 15: 45.8, 30: 48.2, 60: 51.0}
    """
    # Fit linear regression on last 20 readings
    # Extrapolate with time-decay factor
    # Return predicted levels at each horizon
```

---

## 7. DATA STRATEGY

### Current Data Assets

| Data Type | Source | Volume | Quality |
|-----------|--------|--------|---------|
| Water level readings | ESP32 → WaterLevel table | Grows with deployment | High (real sensor) |
| Sensor metadata | Sensor table | 2 sensors | High |
| Weather conditions | Open-Meteo (not stored) | On-demand | High |
| Historical flood events | None | 0 | N/A |

### Training Data Strategy

#### Phase 1: Synthetic Data Generation (MVP)

Generate realistic training scenarios programmatically:

```python
SYNTHETIC_SCENARIOS = [
    # (name, water_level_pattern, weather_pattern, label)
    ("dry_calm",      constant(20),      no_rain,           "low"),
    ("light_rain",    slow_rise(0.5),    light_rain,        "low"),
    ("moderate_rise", moderate_rise(1.5), moderate_rain,     "moderate"),
    ("heavy_rise",    fast_rise(3.0),    heavy_rain,        "high"),
    ("flash_flood",   surge(5.0),        extreme_rain,      "critical"),
    ("false_alarm",   stable(25),        heavy_rain,        "low"),  # rain but no rise
    ("delayed_rise",  delayed_rise(),    heavy_rain,        "moderate"),
    ("falling",       falling(-1.0),     no_rain,           "low"),
]
```

Each scenario generates 100-500 synthetic readings with realistic noise, creating ~2000-4000 training samples.

#### Phase 2: Augmented Real Data

Once ESP32 is deployed:
1. Collect real readings for 1-2 weeks
2. Label based on observed thresholds (level + rate)
3. Retrain model with mixed synthetic + real data (70/30 split)

#### Phase 3: Full Real Data

After 1-3 months of deployment:
1. Discard synthetic data
2. Train exclusively on real readings
3. Model-specific per sensor location

### What to Store vs Calculate Dynamically

| Store in DB | Calculate Dynamically |
|-------------|----------------------|
| Latest prediction per sensor | Weather risk (changes every API call) |
| Prediction history (for charts) | Feature vectors (computed on-demand) |
| Model metadata (version, accuracy) | Anomaly score (computed per reading) |
| Training run logs | Time-to-flood (depends on current rate) |

### Data Retention Policy

- `WaterLevel` readings: Keep all (SQLite handles millions of rows fine)
- `PredictionResult` history: Keep last 7 days, archive older
- Weather cache: 15-minute TTL (don't re-fetch same forecast)

---

## 8. WEATHER API RECOMMENDATION

### Primary: Open-Meteo (ALREADY INTEGRATED)

| Criteria | Rating | Notes |
|----------|--------|-------|
| Free tier | 10,000 req/day | More than enough |
| API key | None required | Zero setup |
| Precipitation probability | Yes (hourly) | Exactly what we need |
| Rainfall amount | Yes (mm/h hourly) | Direct use |
| Humidity | Yes | Direct use |
| Cloud cover | Yes | Direct use |
| Weather codes | Yes (WMO standard) | Maps to severity |
| Forecast duration | Up to 16 days | Exceeds requirements |
| Python integration | `requests.get()` | Already used in `weather.py` |
| Historical data | Yes (archive API, back to 1940) | For training data |

**Current state**: `get_current_weather()` exists but only fetches current conditions. We need to extend it to also fetch hourly forecasts.

### Fallback: WeatherAPI.com

- Free tier: 1,000,000 calls/month
- Requires API key (free signup)
- Has precipitation probability, hourly forecasts
- Use only if Open-Meteo is down

### Weather Service Architecture

```python
# weather/service.py
class WeatherService:
    """
    Separated from ML logic.
    Pure data retrieval and normalization.
    """

    def get_current(self, lat, lon) -> dict:
        """Current conditions (exists, needs minor update)"""

    def get_hourly_forecast(self, lat, lon, days=3) -> list[dict]:
        """Hourly forecast for next N days — NEW"""
        # Returns: [{time, precipitation_probability, precipitation,
        #            rain, humidity, cloud_cover, weather_code, ...}]

    def get_rainfall_summary(self, lat, lon) -> dict:
        """Aggregated rainfall metrics — NEW"""
        # Returns: {rain_1h, rain_3h, rain_6h, rain_24h,
        #           max_intensity, avg_probability}
```

---

## 9. ML MODEL COMPARISON

### For Flood Classification (Binary: flood / no-flood)

| Model | Pros | Cons | Hackathon Fit |
|-------|------|------|---------------|
| **Random Forest** | Fast, robust, explainable, handles small data | Slightly less accurate than XGBoost | ★★★★★ |
| XGBoost | Highest accuracy (AUC 0.97) | More hyperparameters, overfitting risk | ★★★★ |
| Logistic Regression | Simplest, fastest | Can't capture nonlinear patterns | ★★★ |
| SVM | Good for small datasets | Slow inference, no feature importance | ★★ |
| LSTM | Best for long sequences | Needs 10k+ samples, complex setup | ★ |

**Recommendation**: Random Forest for MVP. XGBoost as Phase 2 upgrade.

### For Anomaly Detection (Unsupervised)

| Model | Pros | Cons | Hackathon Fit |
|-------|------|------|---------------|
| **Rolling Z-Score** | Trivial, instant, explainable | Only catches point anomalies | ★★★★★ |
| Isolation Forest | Catches complex anomalies | Needs 50+ readings to stabilize | ★★★★ |
| Local Outlier Factor | Good for local patterns | O(n²) computation | ★★ |

**Recommendation**: Z-score for MVP. Isolation Forest in Phase 2.

### For Water Level Forecasting (Regression)

| Model | Pros | Cons | Hackathon Fit |
|-------|------|------|---------------|
| **Linear Regression** | Instant, interpretable, works with 10 readings | Can't capture nonlinear dynamics | ★★★★★ |
| Polynomial Regression | Captures acceleration | Overfits with few points | ★★★ |
| XGBoost Regressor | Best accuracy | Needs training data | ★★★ |
| LSTM | Best long-term | Needs massive data | ★ |

**Recommendation**: Linear regression with decay for MVP.

---

## 10. RECOMMENDED ML ARCHITECTURE SUMMARY

```
┌─────────────────────────────────────────────────────────┐
│                    INPUT LAYER                          │
│  Weather API    Sensor Readings    Historical Data      │
└────────┬──────────────┬────────────────┬───────────────┘
         │              │                │
         ▼              ▼                ▼
┌────────────┐  ┌──────────────┐  ┌──────────────┐
│  WEATHER   │  │   FEATURE    │  │   HISTORY    │
│  SERVICE   │  │  ENGINEERING │  │   LOOKUP     │
│ (API only) │  │              │  │              │
└─────┬──────┘  └──────┬───────┘  └──────┬───────┘
      │                │                 │
      ▼                │                 │
┌────────────┐         │                 │
│  WEATHER   │         │                 │
│  RISK      │         │                 │
│  ENGINE    │         │                 │
│ (Rule-based│         │                 │
│  scoring)  │         │                 │
└─────┬──────┘         │                 │
      │                ▼                 │
      │       ┌──────────────┐          │
      │       │   SENSOR     │          │
      │       │   ANALYSIS   │          │
      │       │ ┌──────────┐ │          │
      │       │ │ Trend    │ │          │
      │       │ │ Rate     │ │          │
      │       │ │ Anomaly  │ │          │
      │       │ └──────────┘ │          │
      │       └──────┬───────┘          │
      │              │                  │
      ▼              ▼                  ▼
┌─────────────────────────────────────────┐
│         RISK FUSION ENGINE             │
│                                         │
│  weather_risk (30%)                     │
│  + sensor_risk (40%)                    │
│  + anomaly_score (15%)                  │
│  + historical_risk (15%)                │
│  ─────────────────────                  │
│  = final_flood_probability             │
│                                         │
│  Uses: Random Forest (when trained)     │
│  Fallback: weighted sum                │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│         TIME-TO-FLOOD                   │
│         ESTIMATOR                       │
│                                         │
│  current_level + rise_rate              │
│  → time to 50cm: ~8 min               │
│  → time to 70cm: ~18 min              │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│         EXPLAINABILITY                  │
│                                         │
│  "Risk: 87% - CRITICAL"                │
│  "Factors: Heavy rain expected (32%),   │
│   Water rising +2.1cm/min (28%),        │
│   Anomaly detected (15%),               │
│   Close to threshold (12%)"             │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│         DJANGO TEMPLATE                 │
│         DASHBOARD                       │
└─────────────────────────────────────────┘
```

---

## 11. FEATURE ENGINEERING PLAN

### MVP Features (Must Have — Phase 1)

#### Weather Features (from Open-Meteo hourly forecast)

| Feature | Source | Computation |
|---------|--------|-------------|
| `precip_prob_current` | hourly.precipitation_probability | Current hour value |
| `precip_prob_1h` | hourly.precipitation_probability | Next 1 hour max |
| `precip_prob_3h` | hourly.precipitation_probability | Next 3 hours max |
| `rainfall_1h` | hourly.precipitation | Sum of next 1 hour |
| `rainfall_3h` | hourly.precipitation | Sum of next 3 hours |
| `rainfall_6h` | hourly.precipitation | Sum of next 6 hours |
| `rain_intensity` | hourly.precipitation | Max hourly rate in next 3h |
| `humidity` | hourly.relative_humidity_2m | Current value |
| `cloud_cover` | hourly.cloud_cover | Current value |
| `weather_severity` | hourly.weather_code | Mapped to 0-10 scale |

#### Sensor Features (from WaterLevel table)

| Feature | Computation |
|---------|-------------|
| `current_level` | Latest reading |
| `level_1m_ago` | Reading ~1 minute ago |
| `level_5m_ago` | Reading ~5 minutes ago |
| `level_10m_ago` | Reading ~10 minutes ago |
| `level_15m_ago` | Reading ~15 minutes ago |
| `rise_rate` | (current - 5m_ago) / 5 |
| `acceleration` | rise_rate_now - rise_rate_5m_ago |
| `rolling_avg_10` | Mean of last 10 readings |
| `rolling_std_10` | Std of last 10 readings |
| `recent_max` | Max of last 20 readings |
| `recent_min` | Min of last 20 readings |
| `distance_to_warning` | 30 - current_level |
| `distance_to_critical` | 70 - current_level |

#### Anomaly Features

| Feature | Computation |
|---------|-------------|
| `anomaly_score` | From anomaly detector (0-1) |
| `z_score` | Standard deviations from rolling mean |
| `is_anomaly` | Boolean |

### Phase 2 Features (Useful Later)

| Feature | Source |
|---------|--------|
| `historical_flood_frequency` | Count of past alerts at this sensor |
| `historical_max_level` | Max water level ever recorded |
| `time_of_day` | Cyclical encoding (hour sin/cos) |
| `day_of_week` | Cyclical encoding |
| `rainfall_last_24h` | Accumulated rain from weather history |
| `soil_moisture` | Open-Meteo soil moisture (if available) |

### Phase 3 Features (Future)

| Feature | Source |
|---------|--------|
| `elevation` | Sensor GPS + DEM data |
| `drainage_density` | GIS data |
| `upstream_rainfall` | Upstream weather stations |
| `river_discharge` | GloFAS API (could re-add) |

### Data Leakage Prevention

| Risk | Mitigation |
|------|------------|
| Using future sensor readings | Only use readings with `timestamp <= now` |
| Using future weather data | Only use forecast from `now` onward |
| Using target as feature | Never include `is_alert` or `alert_type` in features |
| Look-ahead bias | Features must be computable at prediction time |

---

## 12. DATABASE CHANGES

### New Model: `PredictionResult`

```python
class PredictionResult(models.Model):
    """Stores the latest prediction for each sensor."""
    sensor = models.OneToOneField('core.Sensor', on_delete=models.CASCADE, related_name='prediction')

    # Weather Risk Layer
    weather_risk = models.FloatField(default=0)           # 0-100
    weather_risk_level = models.CharField(max_length=20, default='LOW')
    weather_factors = models.JSONField(default=dict)       # contributing factors

    # Full Flood Prediction
    flood_probability = models.FloatField(default=0)      # 0-100
    flood_risk_level = models.CharField(max_length=20, default='LOW')
    flood_factors = models.JSONField(default=dict)         # contributing factors

    # Anomaly
    anomaly_score = models.FloatField(default=0)          # 0-1
    is_anomaly = models.BooleanField(default=False)
    anomaly_description = models.CharField(max_length=200, blank=True)

    # Time-to-Flood
    time_to_warning = models.CharField(max_length=20, blank=True)   # e.g. "~25 min"
    time_to_critical = models.CharField(max_length=20, blank=True)  # e.g. "~15 min"
    distance_to_critical = models.FloatField(null=True, blank=True) # cm

    # Sensor state
    current_level = models.FloatField(default=0)
    rise_rate = models.FloatField(default=0)              # cm/min

    # Metadata
    confidence = models.CharField(max_length=10, default='low')  # low/medium/high
    data_quality = models.CharField(max_length=20, default='insufficient')  # good/partial/unavailable
    model_version = models.CharField(max_length=20, default='v0.1')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
```

### New Model: `PredictionHistory` (for charts)

```python
class PredictionHistory(models.Model):
    """Stores prediction snapshots for historical charts."""
    sensor = models.ForeignKey('core.Sensor', on_delete=models.CASCADE)
    flood_probability = models.FloatField()
    weather_risk = models.FloatField()
    current_level = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['sensor', 'timestamp']),
        ]
```

### What We Store vs Calculate

| Store | Why |
|-------|-----|
| `PredictionResult` (latest per sensor) | Dashboard needs instant access |
| `PredictionHistory` | Charts need historical predictions |
| `PredictionHistory.timestamp` | X-axis for time-series charts |

| Calculate Dynamically | Why |
|----------------------|-----|
| Weather risk | Changes every API call (15-min cache) |
| Feature vectors | Computed from raw readings on-demand |
| Anomaly score | Computed per reading |
| Time-to-flood | Depends on current rate (changes constantly) |

### No Changes to Existing Models

- `Sensor` — unchanged
- `WaterLevel` — unchanged
- `Alert` — unchanged
- `NotificationRecipient` — unchanged
- `NotificationLog` — unchanged

---

## 13. DJANGO MODULE STRUCTURE

### Module Responsibilities

| Module | Responsibility | Reads | Writes |
|--------|---------------|-------|--------|
| `weather/service.py` | API client, data normalization | Open-Meteo API | Nothing (pure function) |
| `weather/risk_engine.py` | Weather risk scoring | Weather data dict | Risk score dict |
| `ml/features.py` | Feature vector construction | WaterLevel, Sensor, weather | Feature numpy array |
| `ml/flood_model.py` | Flood classification | Feature vector | Probability + factors |
| `ml/anomaly_detector.py` | Anomaly detection | Recent readings list | Anomaly score |
| `ml/water_level_predictor.py` | Time-to-flood estimation | Current level + rate | Time estimates |
| `ml/explainer.py` | Generate human-readable explanations | Prediction factors | Explanation text |
| `services/prediction_service.py` | Orchestrator (calls all engines) | All of the above | PredictionResult |
| `services/model_loader.py` | Load persisted .pkl files | ml_models/*.pkl | Model objects |
| `services/train.py` | Training pipeline | WaterLevel + synthetic | Updated .pkl files |
| `views.py` | HTTP interface | PredictionResult | JSON / template context |
| `urls.py` | Route registration | — | — |

### Data Flow Through Modules

```python
# services/prediction_service.py — the orchestrator

def generate_prediction(sensor_id: int) -> dict:
    """Complete prediction pipeline for one sensor."""

    # 1. Get sensor + recent readings
    sensor = Sensor.objects.get(id=sensor_id)
    readings = WaterLevel.objects.filter(sensor=sensor)[:50]

    # 2. Get weather forecast
    weather = WeatherService().get_hourly_forecast(sensor.latitude, sensor.longitude)
    weather_risk = WeatherRiskEngine().calculate(weather)

    # 3. Build features
    features = FeatureBuilder().build(sensor, readings, weather)

    # 4. Detect anomalies
    anomaly = AnomalyDetector().detect(readings)

    # 5. Get ML prediction (if model exists, else fallback)
    ml_prediction = FloodModel().predict(features)

    # 6. Estimate time-to-flood
    time_estimate = WaterLevelPredictor().estimate(readings)

    # 7. Fuse all signals
    final = RiskFusion().fuse(
        weather_risk=weather_risk,
        sensor_risk=ml_prediction,
        anomaly=anomaly,
        historical=sensor.history_summary()
    )

    # 8. Generate explanation
    explanation = Explainer().explain(final, features)

    # 9. Store result
    PredictionResult.objects.update_or_create(
        sensor=sensor,
        defaults={**final, **explanation}
    )

    return final
```

---

## 14. PREDICTION DATA FLOW

### Request Flow (Dashboard Load)

```
User visits /predictions/
    │
    ▼
views.predictions_view(request)
    │
    ├─ For each active sensor:
    │   │
    │   ├─ prediction_service.generate_prediction(sensor)
    │   │       │
    │   │       ├─ weather/service.py → Open-Meteo API
    │   │       ├─ weather/risk_engine.py → weather_risk score
    │   │       ├─ ml/features.py → feature vector
    │   │       ├─ ml/anomaly_detector.py → anomaly score
    │   │       ├─ ml/flood_model.py → flood probability
    │   │       ├─ ml/water_level_predictor.py → time estimates
    │   │       └─ ml/explainer.py → explanation text
    │   │
    │   └─ Returns prediction dict
    │
    └─ Passes predictions to template

    ▼

predictions.html renders dashboard
    │
    ▼
predictions.js polls /api/predictions/ every 30s
    │
    ▼
views.predictions_api(request) returns JSON
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/predictions/` | GET | Render predictions HTML page |
| `/api/predictions/` | GET | JSON: all sensor predictions |
| `/api/predictions/<device_id>/` | GET | JSON: single sensor prediction |
| `/api/predictions/<device_id>/history/` | GET | JSON: prediction history for charts |
| `/api/predictions/<device_id>/whatif/` | POST | JSON: what-if simulation |

### Caching Strategy

| Data | Cache Duration | Method |
|------|---------------|--------|
| Weather forecast | 15 minutes | In-memory dict (keyed by lat/lon) |
| Prediction result | 30 seconds | Database (PredictionResult table) |
| Feature vector | No cache | Computed fresh each request |
| Historical predictions | No cache | DB query (indexed) |

---

## 15. EXPLAINABLE AI DESIGN

### Why Explainability Matters

- Users need to trust the prediction
- Debugging requires understanding model decisions
- "Black box says 87% flood" is useless without context

### Approach: Feature Contribution Scoring

Instead of SHAP (which requires model-specific integration), use a **rule-based explanation system** that works with any model:

```python
class Explainer:
    def explain(self, prediction: dict, features: dict) -> dict:
        """Generate human-readable explanation of prediction."""

        factors = []

        # Weather contributions
        if features['precip_prob_3h'] > 70:
            factors.append({
                "icon": "rain",
                "text": f"{features['precip_prob_3h']}% rain probability in 3 hours",
                "impact": "high",
                "contribution_pct": self._calc_contribution('weather', features)
            })

        # Sensor contributions
        if features['rise_rate'] > 1.5:
            factors.append({
                "icon": "rising",
                "text": f"Water level rising at {features['rise_rate']} cm/min",
                "impact": "high",
                "contribution_pct": self._calc_contribution('sensor', features)
            })

        # Anomaly
        if features['is_anomaly']:
            factors.append({
                "icon": "warning",
                "text": f"Abnormal surge detected (z-score: {features['z_score']})",
                "impact": "high",
                "contribution_pct": 15
            })

        # Proximity to threshold
        distance = 70 - features['current_level']
        if distance < 20:
            factors.append({
                "icon": "target",
                "text": f"Only {distance}cm to critical threshold",
                "impact": "high",
                "contribution_pct": 12
            })

        # Sort by contribution
        factors.sort(key=lambda x: x['contribution_pct'], reverse=True)

        return {
            "explanation": factors,
            "summary": self._generate_summary(prediction, factors)
        }

    def _generate_summary(self, prediction, factors):
        """One-line summary."""
        level = prediction['flood_risk_level']
        top_factor = factors[0]['text'] if factors else "No significant factors"
        return f"{level} risk — primarily driven by: {top_factor}"
```

### Explanation Output Format

```json
{
    "flood_probability": 87,
    "flood_risk_level": "CRITICAL",
    "explanation": {
        "summary": "CRITICAL risk — primarily driven by: Heavy rain expected (42mm in 3h)",
        "factors": [
            {"icon": "rain", "text": "88% rain probability, 42mm expected in 3 hours", "contribution_pct": 32},
            {"icon": "rising", "text": "Water rising at 2.1 cm/min", "contribution_pct": 28},
            {"icon": "warning", "text": "Abnormal surge detected", "contribution_pct": 18},
            {"icon": "target", "text": "Only 28cm to critical threshold (70cm)", "contribution_pct": 14},
            {"icon": "chart", "text": "Historical flood frequency: HIGH", "contribution_pct": 8}
        ]
    }
}
```

---

## 16. DASHBOARD PLAN

### Layout (Extends base.html)

```
┌─────────────────────────────────────────────────────────────┐
│  NAVBAR: Overview | Data | Map | Predictions (active)       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LIVE STATS BAR (dark gradient)                     │    │
│  │  [Weather Risk] [Flood Risk] [Active Sensors]       │    │
│  │  [Avg Level] [Anomalies] [Last Updated]             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │  SENSOR CARDS         │  │  PREDICTION DETAIL       │    │
│  │  ┌──────┐ ┌──────┐   │  │                          │    │
│  │  │Sens A│ │Sens B│   │  │  Weather Risk: 82% ████  │    │
│  │  │ 72cm │ │ 45cm │   │  │  Flood Risk: 87% █████  │    │
│  │  │ RED  │ │ YEL  │   │  │  Anomaly: DETECTED       │    │
│  │  └──────┘ └──────┘   │  │  Time to Critical: ~15m  │    │
│  │                       │  │                          │    │
│  │  [Select sensor]      │  │  ┌────────────────────┐  │    │
│  │                       │  │  │ Water Level Chart  │  │    │
│  │                       │  │  │ + Predicted Trend  │  │    │
│  │                       │  │  └────────────────────┘  │    │
│  │                       │  │                          │    │
│  │                       │  │  EXPLANATION:            │    │
│  │                       │  │  * 88% rain expected     │    │
│  │                       │  │  * Rising 2.1 cm/min     │    │
│  │                       │  │  * Anomaly detected      │    │
│  └──────────────────────┘  └──────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  RISK HISTORY CHART (last 24h)                      │    │
│  │  [Weather Risk line] [Flood Risk line] [Level line]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  WHAT-IF SIMULATOR (Phase 3)                        │    │
│  │  Rainfall: [slider] Duration: [slider]              │    │
│  │  → Estimated risk: 62%                              │    │
│  │  → Time to critical: ~25 min                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Visual Design Principles

| Element | Treatment |
|---------|-----------|
| Weather Risk | Blue gradient card, cloud/rain icon |
| Flood Risk | Red gradient card, water/warning icon |
| Risk levels | Color-coded badges (green/yellow/orange/red) |
| Time-to-flood | Countdown-style display with urgency colors |
| Explanation | Collapsible card with icon + text factors |
| Charts | Chart.js with threshold lines (30/50/70 cm) |
| Anomaly | Yellow warning banner when detected |

---

## 17. WHAT-IF FLOOD SIMULATOR PLAN

### Purpose

> "What if it rains 40mm in the next 3 hours?"

### Implementation (Rule-Based, No ML Required)

```python
class WhatIfSimulator:
    def simulate(
        self,
        current_level: float,
        rainfall_mm: float,        # user input
        duration_hours: float,     # user input
        rise_rate: float,          # current measured rate
    ) -> dict:
        """
        Estimate flood risk under hypothetical rainfall.

        Uses a simplified rainfall-to-water-level model:
        - Empirical: 1mm rain ≈ 0.1-0.3 cm water rise (depends on drainage)
        - Adjusted by current rise rate
        """

        # Rainfall impact factor (calibrated per location)
        IMPACT_FACTOR = 0.2  # 1mm rain → 0.2cm rise (adjustable)

        expected_rise = rainfall_mm * IMPACT_FACTOR
        projected_level = current_level + expected_rise

        # Adjust for ongoing rise rate
        additional_rise = rise_rate * duration_hours * 60  # rate is per minute
        projected_level += additional_rise * 0.3  # 30% of ongoing rise

        # Calculate risk
        if projected_level >= 70:
            risk = 90 + min((projected_level - 70) / 10, 10)
        elif projected_level >= 50:
            risk = 60 + (projected_level - 50) * 1.5
        elif projected_level >= 30:
            risk = 20 + (projected_level - 30) * 2
        else:
            risk = projected_level * 0.67

        return {
            "projected_level": round(projected_level, 1),
            "flood_risk": round(min(risk, 100), 1),
            "time_to_critical": self._estimate_time(projected_level, rise_rate),
            "would_exceed_warning": projected_level >= 30,
            "would_exceed_critical": projected_level >= 70,
        }
```

### UI Interaction

```
Rainfall amount: [====|============] 42 mm
Duration:        [========|========] 3 hours

Current level: 72 cm
Rise rate: +2.1 cm/min

RESULT:
  Projected level: 84 cm
  Flood risk: 94%
  Time to critical: ~4 minutes
  WARNING: Would exceed danger threshold
```

---

## 18. EVALUATION STRATEGY

### Classification Metrics (Flood Prediction)

| Metric | Why | Target |
|--------|-----|--------|
| **Recall** | Must catch floods (minimize false negatives) | > 0.90 |
| Precision | Avoid false alarms | > 0.70 |
| F1-Score | Balance precision/recall | > 0.80 |
| ROC-AUC | Overall discriminative ability | > 0.85 |

### Why False Negatives Are Critical

| Error Type | Consequence | Cost |
|------------|-------------|------|
| **False Negative** (missed flood) | People don't evacuate, property destroyed, potential deaths | CATASTROPHIC |
| False Positive (false alarm) | Unnecessary panic, "boy who cried wolf" fatigue | Annoying but safe |

**Design principle**: Optimize for recall first, then improve precision. It's better to over-warn than under-warn.

### Regression Metrics (Water Level Prediction)

| Metric | Purpose | Target |
|--------|---------|--------|
| MAE | Average prediction error in cm | < 3 cm |
| RMSE | Penalize large errors | < 5 cm |
| MAPE | Percentage error | < 15% |

### Flood-Warning-Specific Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| False negative rate | % of actual floods missed | < 10% |
| False positive rate | % of false alarms | < 30% |
| Average early-warning time | How far ahead warnings are issued | > 10 minutes |

### Evaluation Plan

1. **Offline evaluation**: Split synthetic+real data 80/20, compute all metrics
2. **Backtesting**: Replay historical readings through the model
3. **Live A/B**: Run prediction alongside existing threshold alerts, compare
4. **User feedback**: Add "Was this prediction accurate?" button on dashboard

---

## 19. FAILURE AND SAFETY HANDLING

### Failure Modes and Responses

| Failure | Detection | Response |
|---------|-----------|----------|
| Weather API down | HTTP error / timeout | `weather_risk = null`, `data_quality = "partial"`, reduce confidence |
| ESP32 disconnected | `last_seen` > 2s old | `sensor_risk = null`, `confidence = "low"` |
| Sensor readings stopped | No new readings for 10min | `data_quality = "stale"`, show warning banner |
| Impossible values | level < 0 or > 500 cm | Reject reading, log error, don't predict |
| Weather data stale | Last fetch > 30 min ago | Refetch or mark as stale |
| Insufficient history | < 10 readings for sensor | `confidence = "low"`, use weather-only risk |
| Model not trained | No .pkl file exists | Fall back to rule-based weighted scoring |
| Low model confidence | Prediction variance > threshold | `confidence = "low"`, show "uncertain" |

### Fallback Hierarchy

```python
def get_flood_prediction(sensor, readings, weather):
    """Prediction with graceful degradation."""

    # Level 1: Full ML prediction (best)
    if model_is_trained() and has_enough_data(readings) and weather_available:
        return full_ml_prediction(sensor, readings, weather)

    # Level 2: Weather + sensor rules (good)
    if weather_available and has_recent_readings(readings):
        return rule_based_prediction(sensor, readings, weather)

    # Level 3: Weather only (basic)
    if weather_available:
        return weather_only_prediction(weather)

    # Level 4: Threshold-based (minimal)
    return threshold_based_prediction(readings)
```

### Staleness Rules

| Data Age | Quality Rating | Confidence Cap |
|----------|---------------|----------------|
| < 5 min | good | high |
| 5-15 min | ok | medium |
| 15-30 min | stale | low |
| > 30 min | unavailable | very_low |

---

## 20. HACKATHON MVP PRIORITIES

### MUST HAVE (Demo-Ready)

| Feature | Effort | Impact |
|---------|--------|--------|
| Weather Risk Engine (rule-based) | 2-3 hours | Core differentiator |
| Sensor trend analysis (rise rate) | 1-2 hours | Shows real-time intelligence |
| Time-to-flood estimation | 1-2 hours | Major "wow" factor |
| Predictions HTML page | 2-3 hours | Where users see everything |
| API endpoints for predictions | 1-2 hours | Frontend-backend bridge |
| Basic explanations | 1-2 hours | Builds trust |
| Weather forecast integration | 1 hour | Extends existing weather.py |

**Total MVP: ~10-15 hours**

### SHOULD HAVE (Polish)

| Feature | Effort | Impact |
|---------|--------|--------|
| Anomaly detection (Z-score) | 1-2 hours | Detects unusual behavior |
| Risk fusion (weighted sum) | 2-3 hours | Combines all signals |
| Prediction history charts | 2-3 hours | Shows trends over time |
| What-if simulator | 2-3 hours | Interactive demo feature |
| Synthetic training data | 2-3 hours | ML model bootstrap |
| Random Forest training | 2-3 hours | More accurate predictions |

**Total Should-Have: ~11-17 hours**

### NICE TO HAVE (Time Permitting)

| Feature | Effort | Impact |
|---------|--------|--------|
| Isolation Forest anomaly detection | 2-3 hours | Better anomaly detection |
| Model retraining pipeline | 3-4 hours | Adapts to real data |
| SHAP explanations | 3-4 hours | Deeper explainability |
| Alert integration (prediction → alert) | 2-3 hours | Automated warnings |
| Email notifications for predictions | 2-3 hours | Proactive alerts |

### DO NOT ATTEMPT (Future)

| Feature | Why Not |
|---------|---------|
| LSTM/GRU models | Needs 10k+ samples, complex setup |
| Real-time model retraining | Needs background task infrastructure |
| Multi-sensor spatial analysis | Needs GIS integration |
| Mobile app | Out of scope |
| Historical data import from external sources | Out of scope |

---

## 21. FUTURE ROADMAP

### Post-Hackathon Phase 1 (Month 1-2)

- Collect real sensor data
- Retrain Random Forest with real + synthetic data (70/30)
- Add Isolation Forest for anomaly detection
- Implement background prediction refresh (APScheduler)
- Add prediction-triggered alerts

### Post-Hackathon Phase 2 (Month 3-4)

- XGBoost upgrade for flood classification
- Location-specific model calibration
- Historical weather data import (Open-Meteo archive API)
- Soil moisture and terrain features
- Model performance dashboard (accuracy tracking)

### Post-Hackathon Phase 3 (Month 5-6)

- LSTM for multi-hour water level forecasting
- Multi-sensor correlation analysis
- GIS-based spatial flood modeling
- Automated model retraining pipeline
- Integration with external flood databases

---

## 22. EXACT IMPLEMENTATION PHASES

### Phase 1: Foundation (Day 1, ~6 hours)

**Goal**: Weather Risk Engine working end-to-end

| Step | Task | Files Created/Modified |
|------|------|----------------------|
| 1.1 | Create `prediction` app | `prediction/__init__.py`, `apps.py`, `models.py` |
| 1.2 | Add to INSTALLED_APPS | `floodguard/settings.py` |
| 1.3 | Create DB models | `prediction/models.py`, run migrate |
| 1.4 | Extend weather service | `prediction/weather/service.py` (add hourly forecast) |
| 1.5 | Weather Risk Engine | `prediction/weather/risk_engine.py` |
| 1.6 | Prediction views | `prediction/views.py` |
| 1.7 | Prediction URLs | `prediction/urls.py`, wire into `floodguard/urls.py` |
| 1.8 | Basic template | `predictions.html` |
| 1.9 | Nav link | `templates/base.html` |
| 1.10 | Test weather risk | Visit /predictions/, verify weather risk displays |

### Phase 2: Sensor Intelligence (Day 2, ~6 hours)

**Goal**: Sensor features + time-to-flood working

| Step | Task | Files |
|------|------|-------|
| 2.1 | Feature engineering | `prediction/ml/features.py` |
| 2.2 | Trend analysis | Part of features.py (rise_rate, acceleration) |
| 2.3 | Anomaly detection (Z-score) | `prediction/ml/anomaly_detector.py` |
| 2.4 | Time-to-flood estimator | `prediction/ml/water_level_predictor.py` |
| 2.5 | Risk fusion (weighted sum) | `prediction/services/prediction_service.py` |
| 2.6 | Explanation generator | `prediction/ml/explainer.py` |
| 2.7 | Update template | Add sensor cards, risk display, explanations |
| 2.8 | Update JS | `predictions.js` (polling, rendering) |
| 2.9 | CSS additions | Prediction-specific styles |
| 2.10 | End-to-end test | Full flow: weather + sensor → prediction → dashboard |

### Phase 3: ML Model (Day 3, ~6 hours)

**Goal**: Random Forest trained and making predictions

| Step | Task | Files |
|------|------|-------|
| 3.1 | Synthetic data generator | `prediction/services/synthetic_data.py` |
| 3.2 | Training pipeline | `prediction/services/train.py` |
| 3.3 | Management command | `prediction/management/commands/train_models.py` |
| 3.4 | Model loader | `prediction/services/model_loader.py` |
| 3.5 | Flood model integration | `prediction/ml/flood_model.py` |
| 3.6 | Run training | `python manage.py train_models` |
| 3.7 | Integrate into prediction service | Update prediction_service.py |
| 3.8 | Model fallback logic | If no model → rule-based scoring |
| 3.9 | Prediction history | Store snapshots for charts |
| 3.10 | Test ML pipeline | Verify predictions improve with model |

### Phase 4: Dashboard Polish (Day 4, ~6 hours)

**Goal**: Professional, visually impressive dashboard

| Step | Task | Files |
|------|------|-------|
| 4.1 | Risk history charts | Chart.js integration in predictions.js |
| 4.2 | What-if simulator | UI + backend |
| 4.3 | Prediction explanation cards | Enhanced template |
| 4.4 | Responsive design | Mobile-friendly layout |
| 4.5 | Color-coded risk badges | CSS refinements |
| 4.6 | Loading states | Skeleton screens, spinners |
| 4.7 | Error states | "Weather unavailable", "Sensor offline" |
| 4.8 | Auto-refresh | 30-second polling with visual indicator |
| 4.9 | Demo scenario preparation | Pre-populate with good demo data |
| 4.10 | Final testing | Full walkthrough |

### Dependencies to Add

```
# requirements.txt additions
scikit-learn>=1.3,<2.0    # Random Forest, Isolation Forest
numpy>=1.24,<2.0           # Numerical operations (scikit-learn dependency)
joblib>=1.3,<2.0           # Model persistence (scikit-learn dependency)
```

### Files NOT Modified

| File | Reason |
|------|--------|
| `core/models.py` | Existing models are sufficient |
| `core/views.py` | No changes needed |
| `api/views.py` | ESP32 flow untouched |
| `api/urls.py` | Existing API routes untouched |
| `templates/base.html` | Only add one nav link |
| `static/css/style.css` | Only add new styles (append) |
| ESP32 code | Never touch |

---

## QUICK REFERENCE: KEY DECISIONS

| Decision | Choice | Why |
|----------|--------|-----|
| Weather Risk Engine | Rule-based scoring | Works with zero training data |
| Flood Prediction Model | Random Forest | Robust, fast, explainable, handles small data |
| Anomaly Detection | Rolling Z-score | Trivial, instant, works with 10 readings |
| Water Level Forecasting | Linear regression + decay | Fast, interpretable, reliable short-term |
| Weather API | Open-Meteo | Free, no key, already integrated |
| Model Persistence | joblib (.pkl files) | Standard scikit-learn approach |
| Prediction Storage | OneToOne latest + history table | Fast dashboard + chart data |
| Risk Fusion | Weighted sum (30/40/15/15) | Tunable, explainable, no training needed |
| Risk Thresholds | 20/40/65/85 (LOW/MODERATE/ELEVATED/HIGH/CRITICAL) | Conservative for flood warning |
| Explainability | Rule-based factor contributions | Works with any model, no SHAP dependency |

---

*This document serves as the complete technical specification for the FloodGuard AI Prediction System. After plan approval, implementation proceeds phase-by-phase starting with Phase 1.*
