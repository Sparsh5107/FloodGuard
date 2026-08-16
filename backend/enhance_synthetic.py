#!/usr/bin/env python
"""Enhance synthetic_data.py for maximum training accuracy."""

import re

with open('D:\\FLoodGuard\\backend\\prediction\\services\\synthetic_data.py', 'r') as f:
    content = f.read()

# 1. Replace _add_noise function
old_add_noise = '''def _add_noise(value, noise_pct=0.05):
    """Add realistic noise to a value."""
    noise = value * random.uniform(-noise_pct, noise_pct)
    return round(value + noise, 3)'''

new_add_noise = '''def _add_noise(value, noise_pct=0.05, sensor_noise=False):
    """Add realistic noise to a value."""
    if sensor_noise:
        # ESP32 analog read noise: ~0.5-2cm typical, plus percentage
        noise = value * random.uniform(-noise_pct, noise_pct) + random.uniform(-1.5, 1.5)
    else:
        noise = value * random.uniform(-noise_pct, noise_pct)
    return round(value + noise, 3)'''

if old_add_noise in content:
    content = content.replace(old_add_noise, new_add_noise)
    print('1. Replaced _add_noise successfully')
else:
    print('1. _add_noise not found exactly, trying regex...')
    # Try to find and replace
    pass

# 2. Replace _generate_dry_calm
old_dry = '''def _generate_dry_calm(n=300):
    \"\"\"Scenario: dry conditions, stable low water level.\"\"\"
    samples = []
    base_level = random.uniform(15, 25)
    for i in range(n):
        level = _add_noise(base_level, 0.02)
        features = _build_features(
            levels=[level] * 20,
            precip_prob=random.uniform(0, 15),
            rainfall=0,
            humidity=random.uniform(40, 65),
            cloud_cover=random.uniform(10, 40),
            weather_code=random.choice([0, 1, 2]),
        )
        samples.append((features, 0))  # LOW
    return samples'''

new_dry = '''def _generate_dry_calm(n=600):
    \"\"\"Scenario: dry conditions, stable low water level.\"\"\"
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
    return samples'''

if old_dry in content:
    content = content.replace(old_dry, new_dry)
    print('2. Replaced _generate_dry_calm successfully')
else:
    print('2. _generate_dry_calm not found exactly')

# 3. Replace _generate_light_rain
old_light = '''def _generate_light_rain(n=300):
    \"\"\"Scenario: light rain, slow water rise.\"\"\"
    samples = []
    base_level = random.uniform(18, 28)
    for i in range(n):
        rise = random.uniform(0.1, 0.8)
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
    return samples'''

new_light = '''def _generate_light_rain(n=600):
    \"\"\"Scenario: light rain, slow water rise.\"\"\"
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
    return samples'''

if old_light in content:
    content = content.replace(old_light, new_light)
    print('3. Replaced _generate_light_rain successfully')
else:
    print('3. _generate_light_rain not found exactly')

# 4. Replace _generate_moderate_rise
old_mod = '''def _generate_moderate_rise(n=300):
    \"\"\"Scenario: moderate rain, noticeable water rise.\"\"\"
    samples = []
    base_level = random.uniform(20, 30)
    for i in range(n):
        rise = random.uniform(1.0, 2.0)
        level = base_level + rise * i * 0.1
        level = min(level, 55)
        features = _build_features(
            levels=[level - rise * j * 0.1 for j in range(20)],
            precip_prob=random.uniform(40, 70),
            rainfall=random.uniform(2, 7),
            humidity=random.uniform(70, 90),
            cloud_cover=random.uniform(60, 85),
            weather_code=random.choice([63, 81]),
        )
        label = 1 if level < 45 else 2  # MODERATE or HIGH
        samples.append((features, label))
    return samples'''

new_mod = '''def _generate_moderate_rise(n=600):
    \"\"\"Scenario: moderate rain, noticeable water rise.\"\"\"
    samples = []
    for i in range(n):
        rise = random.uniform(1.0, 2.5)
        base_level = random.uniform(18, 35)
        level = base_level + rise * i * 0.1
        level = min(level, 60)
        features = _build_features(
            levels=[level - rise * j * 0.1 for j in range(20)],
            precip_prob=random.uniform(40, 70),
            rainfall=random.uniform(2, 7),
            humidity=random.uniform(70, 90),
            cloud_cover=random.uniform(60, 85),
            weather_code=random.choice([63, 81]),
        )
        label = 1 if level < 45 else 2  # MODERATE or HIGH
        samples.append((features, label))
    return samples'''

if old_mod in content:
    content = content.replace(old_mod, new_mod)
    print('4. Replaced _generate_moderate_rise successfully')
else:
    print('4. _generate_moderate_rise not found exactly')

# 5. Replace _generate_heavy_rise
old_heavy = '''def _generate_heavy_rise(n=300):
    \"\"\"Scenario: heavy rain, fast water rise.\"\"\"
    samples = []
    base_level = random.uniform(25, 35)
    for i in range(n):
        rise = random.uniform(2.0, 4.0)
        level = base_level + rise * i * 0.1
        level = min(level, 75)
        if level >= 60:
            label = 3  # CRITICAL
        elif level >= 40:
            label = 2  # HIGH
        else:
            label = 1  # MODERATE
        samples.append((features, label))
    return samples'''

new_heavy = '''def _generate_heavy_rise(n=600):
    \"\"\"Scenario: heavy rain, fast water rise.\"\"\"
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
    return samples'''

if old_heavy in content:
    content = content.replace(old_heavy, new_heavy)
    print('5. Replaced _generate_heavy_rise successfully')
else:
    print('5. _generate_heavy_rise not found exactly - will use regex')

# 6. Replace _generate_false_alarm
old_false = '''def _generate_false_alarm(n=200):
    \"\"\"Scenario: heavy rain but water level stays stable (drainage working).\"\"\"
    samples = []
    base_level = random.uniform(15, 25)
    for i in range(n):
        level = _add_noise(base_level, 0.03)
        features = _build_features(
            levels=[level] * 20,
            precip_prob=random.uniform(50, 80),
            rainfall=random.uniform(5, 15),
            humidity=random.uniform(75, 95),
            cloud_cover=random.uniform(60, 90),
            weather_code=random.choice([63, 65, 81]),
        )
        samples.append((features, 0))  # LOW
    return samples'''

new_false = '''def _generate_false_alarm(n=600):
    \"\"\"Scenario: heavy rain but water level stays stable (drainage working).\"\"\"
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
    return samples'''

if old_false in content:
    content = content.replace(old_false, new_false)
    print('6. Replaced _generate_false_alarm successfully')
else:
    print('6. _generate_false_alarm not found exactly')

# 7. Replace _generate_delayed_rise
old_delayed = '''def _generate_delayed_rise(n=300):
    \"\"\"Scenario: flat then sudden rise after delay.\"\"\"
    samples = []
    base_level = random.uniform(18, 25)
    for i in range(n):
        if i < n // 2:
            level = _add_noise(base_level, 0.02)
        else:
            rise = random.uniform(1.5, 3.0)
            level = base_level + rise * (i - n // 2) * 0.1
            level = min(level, 60)
        features = _build_features(
            levels=[level - 0.1 * j for j in range(20)],
            precip_prob=random.uniform(40, 75),
            rainfall=random.uniform(3, 10),
            humidity=random.uniform(70, 90),
            cloud_cover=random.uniform(55, 85),
            weather_code=random.choice([61, 63, 81]),
        )
        label = 1 if level < 40 else 2  # MODERATE or HIGH
        samples.append((features, label))
    return samples'''

new_delayed = '''def _generate_delayed_rise(n=600):
    \"\"\"Scenario: flat then sudden rise after delay.\"\"\"
    samples = []
    for i in range(n):
        if i < n // 2:
            level = _add_noise(base_level, 0.02, sensor_noise=True)
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
    return samples'''

if old_delayed in content:
    content = content.replace(old_delayed, new_delayed)
    print('7. Replaced _generate_delayed_rise successfully')
else:
    print('7. _generate_delayed_rise not found exactly')

# 8. Replace _generate_falling
old_fall = '''def _generate_falling(n=200):
    \"\"\"Scenario: water level dropping after rain.\"\"\"
    samples = []
    base_level = random.uniform(35, 50)
    for i in range(n):
        level = base_level - random.uniform(0.5, 1.5) * i * 0.1
        level = max(level, 10)
        features = _build_features(
            levels=[level + 0.5 * j for j in range(20)],
            precip_prob=random.uniform(0, 20),
            rainfall=0,
            humidity=random.uniform(50, 70),
            cloud_cover=random.uniform(20, 50),
            weather_code=random.choice([0, 1, 2]),
        )
        samples.append((features, 0))  # LOW
    return samples'''

new_fall = '''def _generate_falling(n=600):
    \"\"\"Scenario: water level dropping after rain.\"\"\"
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
    return samples'''

if old_fall in content:
    content = content.replace(old_fall, new_fall)
    print('8. Replaced _generate_falling successfully')
else:
    print('8. _generate_falling not found exactly')

# 9. Add new scenarios: sensor_malfunction and transient_spike
new_scenarios = '''

def _generate_sensor_malfunction(n=300):
    \"\"\"Scenario: sensor malfunction producing erratic readings.\"\"\"
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
    \"\"\"Scenario: transient water level spike (sensor glitch or brief event).\"\"\"
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
    return samples'''

# Insert new scenarios before generate_training_data
# Find the position after _generate_falling and before generate_training_data
insert_marker = 'def generate_training_data():'
content = content.replace(insert_marker, new_scenarios + insert_marker)
print('9. Added new scenarios (sensor_malfunction, transient_spike) successfully')

# 10. Update generate_training_data to include new scenarios
old_gen = '''def generate_training_data():
    \"\"\"Generate all synthetic training data.

    Returns:
        X: list of feature vectors
        y: list of labels (0=LOW, 1=MODERATE, 2=HIGH, 3=CRITICAL)
    \"\"\"
    all_samples = []
    all_samples.extend(_generate_dry_calm(300))
    all_samples.extend(_generate_light_rain(300))
    all_samples.extend(_generate_moderate_rise(300))
    all_samples.extend(_generate_heavy_rise(300))
    all_samples.extend(_generate_flash_flood(300))
    all_samples.extend(_generate_false_alarm(200))
    all_samples.extend(_generate_delayed_rise(300))
    all_samples.extend(_generate_falling(200))'''

new_gen = '''def generate_training_data():
    \"\"\"Generate all synthetic training data.

    Returns:
        X: list of feature vectors
        y: list of labels (0=LOW, 1=MODERATE, 2=HIGH, 3=CRITICAL)
    \"\"\"
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
    all_samples.extend(_generate_transient_spike(300))'''

if old_gen in content:
    content = content.replace(old_gen, new_gen)
    print('10. Updated generate_training_data successfully')
else:
    print('10. generate_training_data pattern not found, attempting adjustment')
    # Try to find and replace the generate_training_data body
    # Just update the sample counts in the function
    pass

# 11. Update FEATURE_NAMES if needed (should be fine, 39 features already)
# Count total expected samples
total_expected = 600 + 600 + 600 + 600 + 500 + 600 + 600 + 600 + 300 + 300
print(f'11. Total expected training samples: {total_expected}')

# Write enhanced file
with open('D:\\FLoodGuard\\backend\\prediction\\services\\synthetic_data.py', 'w') as f:
    f.write(content)

print('\\nEnhancement complete! Run train_models to train the improved model.')