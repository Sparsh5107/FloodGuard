"""Shared utility functions for the prediction system."""


def std(values):
    """Standard deviation of a list."""
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


def weather_severity(code):
    """Map WMO weather code to severity 0-10."""
    severity_map = {
        0: 0, 1: 0, 2: 0, 3: 0,
        45: 1, 48: 1,
        51: 2, 53: 3, 55: 4,
        61: 3, 63: 5, 65: 8,
        71: 3, 73: 5, 75: 7,
        80: 3, 81: 5, 82: 8,
        85: 3, 86: 6,
        95: 10, 96: 10, 99: 10,
    }
    return severity_map.get(code, 0)
