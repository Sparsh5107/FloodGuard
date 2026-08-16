# FloodGuard AI — Phase-by-Phase Explanation

## Phase 1: Weather Risk (DONE)

**What it does:** Checks upcoming weather and tells you how risky conditions are.

**How it works:**
- Fetches 3-day hourly weather forecast from Open-Meteo (free, no API key)
- Scores risk from 0-100% based on 5 factors:
  1. Rain probability (0-30 pts)
  2. Rainfall intensity (0-30 pts)
  3. Rainfall accumulation over 3h/6h (0-20 pts)
  4. Weather severity — thunderstorm vs light rain (0-10 pts)
  5. Humidity + cloud cover (0-10 pts)

**What you see:**
- Sensor cards with weather risk score and color badge
- Contributing factors (why the score is what it is)

**What it does NOT do yet:**
- Does not look at actual water level data
- Does not predict floods
- Does not detect anomalies
- Does not estimate time-to-flood

---

## Phase 2: Sensor Intelligence

**What it adds:** Analyzes real water level data from ESP32 sensors.

**New features:**

### 1. Feature Engineering
Pulls useful numbers from raw sensor readings:
- Current water level
- Water level 1min, 5min, 10min, 15min ago
- Rise rate (cm per minute)
- Is water level accelerating?
- Rolling average and standard deviation
- Distance to warning (30cm) and critical (70cm) thresholds

### 2. Anomaly Detection (Z-Score)
Detects unusual water level behavior:
- Compares current reading to recent average
- If current is 2.5+ standard deviations away from mean → anomaly
- Also checks if water is rising faster than expected
- Classifies as: NORMAL, RAPID RISE, RAPID DROP, SURGE ALERT, or ACCELERATING

### 3. Time-to-Flood Estimator
Estimates when water will hit critical threshold (70cm):
- Calculates rise rate from recent readings
- Projects forward: "at current rate, water reaches 70cm in ~15 minutes"
- Adds 20% safety margin
- Confidence: HIGH (<30min), MEDIUM (30-60min), LOW (>60min)

### 4. Risk Fusion
Combines all signals into one flood probability:
- Weather risk: 30% weight
- Sensor risk: 40% weight
- Anomaly score: 15% weight
- Historical risk: 15% weight

### 5. Explainability
Generates plain-English explanations:
- "CRITICAL risk — primarily driven by: Heavy rain expected (42mm in 3h)"
- Shows each factor with its contribution percentage

**What you see on the dashboard:**
- Same sensor cards, now with more data
- Risk fusion score combining weather + sensor + anomaly
- Time-to-flood countdown
- Explanation section with factor breakdown
- Anomaly warning banner when detected

---

## Phase 3: ML Model

**What it adds:** A trained Random Forest machine learning model.

### How it works:

1. **Synthetic Data Generation**
   - Since we don't have historical flood data yet, we create realistic fake scenarios
   - 8 scenarios: dry calm, light rain, moderate rise, heavy rise, flash flood, false alarm, delayed rise, falling
   - Each generates 100-500 readings with realistic noise
   - Creates ~2000-4000 training samples

2. **Training**
   - Random Forest Classifier (100 trees, max depth 10)
   - Input: feature vector (weather + sensor + anomaly + history)
   - Output: flood probability (0-100%) and risk level
   - Trained with `python manage.py train_models`

3. **Integration**
   - Model loaded from `.pkl` file
   - Replaces the weighted-sum fallback from Phase 2
   - Still falls back to rules if model not trained yet

**What you see:**
- Same dashboard, but predictions are smarter
- Confidence level shown (low/medium/high)
- Model version displayed
- Better accuracy over time as real data replaces synthetic data

---

## Phase 4: Dashboard Polish

**What it adds:** Professional UI, charts, and interactive features.

### New features:

1. **Risk History Charts**
   - Chart.js line chart showing weather risk, flood risk, and water level over time
   - Threshold lines at 30/50/70 cm
   - Updates every 30 seconds

2. **What-If Simulator**
   - Sliders to adjust rainfall amount and duration
   - Shows projected water level and flood risk
   - Example: "What if it rains 40mm in 3 hours?"
   - Backend estimates impact using empirical formula

3. **Enhanced Explanation Cards**
   - Icons for each factor type
   - Contribution percentage bars
   - Collapsible sections

4. **Loading & Error States**
   - Skeleton screens while data loads
   - "Weather unavailable" message when API fails
   - "Sensor offline" badge for disconnected sensors

5. **Auto-Refresh**
   - 30-second polling with visual indicator
   - Smooth transitions when data updates

**What you see:**
- Polished, professional dashboard
- Interactive charts
- What-if simulator at bottom
- Better visual feedback

---

## Summary

| Phase | What It Does | Data Source | Accuracy |
|-------|-------------|-------------|----------|
| 1 | Weather risk only | Open-Meteo API | Good early warning |
| 2 | + Sensor analysis + anomaly + time-to-flood | ESP32 sensors | Better, real-time |
| 3 | + ML model predictions | Trained on synthetic data | Smart, improves with real data |
| 4 | + Charts + what-if + polished UI | All of above | Production-ready |

Each phase builds on the previous. You can stop at any phase and have a working system.



