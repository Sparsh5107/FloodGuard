"""Synthetic training data generator for flood prediction model.

Creates realistic flood scenarios with labeled data for training
the Random Forest classifier.
"""

import random
from prediction.constants import RISK_LABELS, WEATHER_CODES
from prediction.utils import std as _std, weather_severity

# Feature names matching the feature engineering pipeline
FEATURE_NAMES = [
    # Sensor features
    "current_level", "level_1m_ago", "level_5m_ago", "level_10m_ago", "level_15m_ago",
    "rise_rate", "acceleration", "rolling_avg_10", "rolling_std_10",
    "recent_max", "recent_min", "distance_to_warning", "distance_to_critical",
    # Weather features
    "precip_prob_current", "precip_prob_1h", "precip_prob_3h",
    "rainfall_1h", "rainfall_3h", "rainfall_6h", "rain_intensity",
    "humidity", "cloud_cover", "weather_severity",
    # Anomaly features
    "anomaly_score", "z_score", "is_anomaly",
]


def _add_noise(value, noise_pct=0.05, sensor_noise=False):
    """Add realistic noise to a value."""
    if sensor_noise:
        # ESP32 analog read noise: ~0.5-2cm typical, plus percentage
        noise = value * random.uniform(-noise_pct, noise_pct) + random.uniform(-1.5, 1.5)
    else:
        noise = value * random.uniform(-noise_pct, noise_pct)
    return round(value + noise, 3)


def _generate_dry_calm(n=600):
    """Scenario: dry conditions, stable low water level."""
    samples = []
    for i in range(n):
        base_level = random.uniform(10, 40)
        level = _add_noise(base_level, 0.02, sensor_noise=True)
        features = _build_features(
            levels=[level] * 20,
            precip_prob=random.uniform(0, 15),
            rainfall=0,
            humidity=random.uniform(40, 65),
            cloud_cover=random.uniform(10, 40),
            weather_code=random.choice([0, 1, 2]),
        )
        samples.append((features, 0))  # LOW
    return samples


def _generate_light_rain(n=600):
    """Scenario: light rain, slow water rise."""
    samples = []
    for i in range(n):
        rise = random.uniform(0.1, 0.8)
        base_level = random.uniform(15, 30)
        level = base_level + rise * i * 0.1
        level = min(level, 35)
        features = _build_features(
            levels=[level - rise * j * 0.1 for j in range(20)],
            precip_prob=random.uniform(20, 50),
            rainfall=random.uniform(0.5, 2),
            humidity=random.uniform(60, 80),
            cloud_cover=random.uniform(40, 70),
            weather_code=random.choice([51, 53, 61, 80]),
        )
        samples.append((features, 0))  # LOW
    return samples


def _generate_moderate_rise(n=600):
    """Scenario: moderate rain, noticeable water rise."""
    samples = []
    for i in range(n):
        rise = random.uniform(1.0, 2.5)
        base_level = random.uniform(18, 35)
        level = base_level + rise * i * 0.1
        level = min(level, 60)
        label = 1 if level < 45 else 2  # MODERATE or HIGH
        features = _build_features(
            levels=[level - rise * j * 0.1 for j in range(20)],
            precip_prob=random.uniform(40, 70),
            rainfall=random.uniform(2, 7),
            humidity=random.uniform(70, 90),
            cloud_cover=random.uniform(60, 85),
            weather_code=random.choice([63, 81]),
        )
        samples.append((features, label))
    return samples


def _generate_heavy_rise(n=600):
    """Scenario: heavy rain, fast water rise."""
    samples = []
    for i in range(n):
        rise = random.uniform(2.0, 5.0)
        base_level = random.uniform(20, 40)
        level = base_level + rise * i * 0.1
        level = min(level, 80)
        if level >= 65:
            label = 3  # CRITICAL
        elif level >= 45:
            label = 2  # HIGH
        else:
            label = 1  # MODERATE
        features = _build_features(
            levels=[level - rise * j * 0.1 for j in range(20)],
            precip_prob=random.uniform(60, 95),
            rainfall=random.uniform(7, 25),
            humidity=random.uniform(80, 98),
            cloud_cover=random.uniform(70, 95),
            weather_code=random.choice([65, 82]),
        )
        samples.append((features, label))
    return samples


def _generate_flash_flood(n=500):
    """Scenario: extreme rain, surge, rapid flooding."""
    samples = []
    for i in range(n):
        surge = random.uniform(3.0, 6.0)
        base_level = random.uniform(20, 30)
        level = base_level + surge * i * 0.1
        level = min(level, 90)
        features = _build_features(
            levels=[level - surge * j * 0.1 for j in range(20)],
            precip_prob=random.uniform(80, 100),
            rainfall=random.uniform(15, 40),
            humidity=random.uniform(85, 100),
            cloud_cover=random.uniform(80, 100),
            weather_code=random.choice([95, 96, 99]),
            anomaly_score=random.uniform(0.5, 1.0),
        )
        if level >= 60:
            label = 3  # CRITICAL
        elif level >= 40:
            label = 2  # HIGH
        else:
            label = 1  # MODERATE
        samples.append((features, label))
    return samples


def _generate_false_alarm(n=600):
    """Scenario: heavy rain but water level stays stable (drainage working)."""
    samples = []
    for i in range(n):
        base_level = random.uniform(12, 30)
        level = _add_noise(base_level, 0.03, sensor_noise=True)
        features = _build_features(
            levels=[level] * 20,
            precip_prob=random.uniform(50, 80),
            rainfall=random.uniform(5, 15),
            humidity=random.uniform(75, 95),
            cloud_cover=random.uniform(60, 90),
            weather_code=random.choice([63, 65, 81]),
        )
        samples.append((features, 0))  # LOW
    return samples


def _generate_delayed_rise(n=600):
    """Scenario: flat then sudden rise after delay."""
    samples = []
    for i in range(n):
        if i < n // 2:
            level = _add_noise(base_level := random.uniform(18, 25), 0.02, sensor_noise=True)
        else:
            rise = random.uniform(1.5, 3.5)
            level = base_level + rise * (i - n // 2) * 0.1
            level = min(level, 65)
        features = _build_features(
            levels=[level - 0.1 * j for j in range(20)],
            precip_prob=random.uniform(40, 80),
            rainfall=random.uniform(3, 12),
            humidity=random.uniform(70, 92),
            cloud_cover=random.uniform(55, 88),
            weather_code=random.choice([61, 63, 81]),
        )
        label = 1 if level < 40 else 2  # MODERATE or HIGH
        samples.append((features, label))
    return samples


def _generate_falling(n=600):
    """Scenario: water level dropping after rain."""
    samples = []
    for i in range(n):
        base_level = random.uniform(30, 55)
        level = base_level - random.uniform(0.3, 1.0) * i * 0.1
        level = max(level, 5)
        features = _build_features(
            levels=[level + 0.3 * j for j in range(20)],
            precip_prob=random.uniform(0, 25),
            rainfall=0,
            humidity=random.uniform(40, 75),
            cloud_cover=random.uniform(15, 55),
            weather_code=random.choice([0, 1, 2]),
        )
        samples.append((features, 0))  # LOW
    return samples


def _generate_sensor_malfunction(n=300):
    """Scenario: sensor malfunction producing erratic readings."""
    samples = []
    for i in range(n):
        # Erratic levels: random walk with large jumps
        if i == 0:
            level = random.uniform(20, 30)
        else:
            prev_level = samples[i-1][0][0] if samples else random.uniform(20, 30)
            # 50% chance of normal change, 50% chance of big jump
            if random.random() < 0.5:
                level = prev_level + random.uniform(-0.5, 0.5)
            else:
                level = random.uniform(5, 80)
            level = max(0, min(100, level))
        
        features = _build_features(
            levels=[level] * 20,
            precip_prob=random.uniform(20, 60),
            rainfall=random.uniform(1, 10),
            humidity=random.uniform(50, 90),
            cloud_cover=random.uniform(30, 80),
            weather_code=random.choice([0, 1, 2, 3, 45, 51]),
            anomaly_score=random.uniform(0.3, 1.0),
        )
        # Malfunction data: label as LOW since we can't trust the reading,
        # but the anomaly will be detected
        samples.append((features, 0))  # LOW (unreliable reading)
    return samples


def _generate_transient_spike(n=300):
    """Scenario: transient water level spike (sensor glitch or brief event)."""
    samples = []
    for i in range(n):
        base_level = random.uniform(20, 25)
        # Spike in last few readings
        if i < n - 5:
            level = _add_noise(base_level, 0.02, sensor_noise=True)
        else:
            # Sudden spike
            spike_mag = random.uniform(10, 30)
            level = base_level + spike_mag
            level = min(level, 80)
        
        # Calculate rise rate for last readings
        recent_levels = [level] * 20
        
        features = _build_features(
            levels=recent_levels,
            precip_prob=random.uniform(10, 80),
            rainfall=random.uniform(0, 15),
            humidity=random.uniform(50, 95),
            cloud_cover=random.uniform(20, 90),
            weather_code=random.choice([0, 1, 2, 51, 61, 95]),
            anomaly_score=random.uniform(0.1, 1.0),
        )
        # Spike events can be either low or high risk depending on context
        if level >= 50:
            label = random.choice([2, 3])  # HIGH or CRITICAL
        else:
            label = random.choice([0, 1])  # LOW or MODERATE
        samples.append((features, label))
    return samples


def _build_features(levels, precip_prob, rainfall, humidity, cloud_cover,
                    weather_code, anomaly_score=0):
    """Build a feature vector from scenario parameters."""
    levels = list(reversed(levels))  # newest last
    current = levels[-1]

    # Sensor features
    rise_rate = (levels[-1] - levels[-5]) / 5.0 if len(levels) >= 5 else 0
    acceleration = 0
    if len(levels) >= 5:
        rate1 = (levels[-1] - levels[-2])
        rate2 = (levels[-2] - levels[-3])
        acceleration = rate1 - rate2

    rolling_avg = sum(levels[-10:]) / min(len(levels), 10)
    rolling_std = _std(levels[-10:])
    recent_max = max(levels[-20:])
    recent_min = min(levels[-20:])

    # Weather features
    z_score = (current - rolling_avg) / max(rolling_std, 0.001)
    is_anomaly = 1 if abs(z_score) > 2.5 or acceleration > 5 else 0

    return [
        # Sensor features
        round(current, 2),
        round(levels[-2] if len(levels) >= 2 else current, 2),
        round(levels[-6] if len(levels) >= 6 else current, 2),
        round(levels[-11] if len(levels) >= 11 else current, 2),
        round(levels[-16] if len(levels) >= 16 else current, 2),
        round(rise_rate, 3),
        round(acceleration, 3),
        round(rolling_avg, 2),
        round(rolling_std, 3),
        round(recent_max, 2),
        round(recent_min, 2),
        round(30 - current, 1),
        round(70 - current, 1),
        # Weather features
        round(precip_prob, 1),
        round(precip_prob * 0.9, 1),
        round(precip_prob * 1.1, 1),
        round(rainfall, 2),
        round(rainfall * 2.5, 2),
        round(rainfall * 5, 2),
        round(rainfall * 1.2, 2),
        round(humidity, 1),
        round(cloud_cover, 1),
        weather_severity(weather_code),
        # Anomaly features
        round(anomaly_score, 3),
        round(z_score, 2),
        is_anomaly,
    ]


def generate_training_data():
    """Generate all synthetic training data.

    Returns:
        X: list of feature vectors
        y: list of labels (0=LOW, 1=MODERATE, 2=HIGH, 3=CRITICAL)
    """
    all_samples = []
    all_samples.extend(_generate_dry_calm(600))
    all_samples.extend(_generate_light_rain(600))
    all_samples.extend(_generate_moderate_rise(600))
    all_samples.extend(_generate_heavy_rise(600))
    all_samples.extend(_generate_flash_flood(500))
    all_samples.extend(_generate_false_alarm(600))
    all_samples.extend(_generate_delayed_rise(600))
    all_samples.extend(_generate_falling(600))
    all_samples.extend(_generate_sensor_malfunction(300))
    all_samples.extend(_generate_transient_spike(300))

    random.shuffle(all_samples)

    X = [s[0] for s in all_samples]
    y = [s[1] for s in all_samples]

    return X, y


def get_feature_names():
    """Return list of feature names."""
    return FEATURE_NAMES.copy()


def get_label_names():
    """Return label name mapping."""
    return RISK_LABELS.copy()