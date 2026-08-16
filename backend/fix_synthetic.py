#!/usr/bin/env python
"""Regenerate synthetic_data.py with all enhancements."""

with open('D:\\FLoodGuard\\backend\\prediction\\services\\synthetic_data.py', 'r') as f:
    content = f.read()

# Fix _generate_heavy_rise - replace the whole function
import re

# Find and replace _generate_heavy_rise using regex
pattern = r'def _generate_heavy_rise\\(n=300\\)..*?return samples'
match = re.search(pattern, content, re.DOTALL)
if match:
    # Get the full function
    func_start = match.start()
    # Find the next def or end
    remaining = content[func_start:]
    next_def = remaining.find('\\n\\n\\n\\ndef ')
    if next_def == -1:
        next_def = len(remaining)
    old_func = remaining[:next_def].rstrip()
    
    new_func = '''def _generate_heavy_rise(n=600):
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
    return samples''')
    
    content = content.replace(old_func, new_func)
    print('Fixed _generate_heavy_rise')
else:
    print('Could not find _generate_heavy_rise with regex')

# Also fix generate_training_data sample counts
old_gen = '''all_samples.extend(_generate_dry_calm(300))
    all_samples.extend(_generate_light_rain(300))
    all_samples.extend(_generate_moderate_rise(300))
    all_samples.extend(_generate_heavy_rise(300))
    all_samples.extend(_generate_flash_flood(300))
    all_samples.extend(_generate_false_alarm(200))
    all_samples.extend(_generate_delayed_rise(300))
    all_samples.extend(_generate_falling(200))'''

new_gen = '''all_samples.extend(_generate_dry_calm(600))
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
    print('Updated generate_training_data sample counts')
else:
    print('Could not find old generate_training_data pattern')

# Also replace _generate_flash_flood n=300 to n=500
old_flash = '''def _generate_flash_flood(n=300):'''
new_flash = '''def _generate_flash_flood(n=500):'''

if old_flash in content:
    content = content.replace(old_flash, new_flash)
    print('Fixed _generate_flash_flood n parameter')
else:
    print('_generate_flash_flood n parameter not found')

# Write the enhanced file
with open('D:\\FLoodGuard\\backend\\prediction\\services\\synthetic_data.py', 'w') as f:
    f.write(content)

print('\\nRegeneration complete!')
"