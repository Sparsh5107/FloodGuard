# Backend → Mobile Integration Plan

All changes needed to connect the Django backend to FloodGuardMobile.
No implementations here — just what to change, where, and why.

---

## Prerequisite: Run remove.md cleanup first

Execute everything in `plannings/remove.md` before starting these changes.

---

## Change 1 — Backend: Create `/api/system-stats/` endpoint

**Why:** DashboardScreen and SettingsScreen both call `GET /api/system-stats/`. Currently returns 404. Without this, DashboardScreen stat cards are blank and SettingsScreen system info is hidden.

**File:** `backend/api/views.py`

Add new function `system_stats_api`:

```python
@api_view(['GET'])
def system_stats_api(request):
    """System-wide statistics for mobile app."""
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    sensors = Sensor.objects.all()
    total_sensors = sensors.count()
    online_sensors = sensors.filter(
        last_seen__gte=now - timedelta(seconds=2)
    ).count()

    total_readings = WaterLevel.objects.count()
    readings_today = WaterLevel.objects.filter(
        timestamp__gte=today_start
    ).count()

    total_alerts = Alert.objects.count()
    unresolved_alerts = Alert.objects.filter(is_resolved=False).count()

    return Response({
        'total_sensors': total_sensors,
        'active_sensors': online_sensors,
        'online_sensors': online_sensors,
        'unresolved_alerts': unresolved_alerts,
        'total_readings': total_readings,
        'total_alerts': total_alerts,
        'readings_today': readings_today,
    })
```

**File:** `backend/api/urls.py`

Add to urlpatterns:
```python
path('system-stats/', views.system_stats_api, name='system-stats'),
```

---

## Change 2 — Backend: Fix `dashboard_data_api` alert response

**Why:** Mobile AlertCard needs `alert.id` for key extraction and acknowledge action, and `alert.is_resolved` for filtering and resolved badge display. Currently neither field is returned.

**File:** `backend/api/views.py` — `dashboard_data_api` function (~line 196)

Current alerts comprehension:
```python
alerts_data = [{
    'sensor_name': a.sensor.name,
    'location': a.sensor.location,
    'alert_type': a.alert_type,
    'message': a.message,
    'created_at': a.created_at.strftime('%b %d, %H:%M:%S'),
} for a in alerts]
```

Change to:
```python
alerts_data = [{
    'id': a.id,
    'sensor_name': a.sensor.name,
    'location': a.sensor.location,
    'alert_type': a.alert_type,
    'message': a.message,
    'is_resolved': a.is_resolved,
    'created_at': a.created_at.strftime('%b %d, %H:%M:%S'),
} for a in alerts]
```

---

## Change 3 — Backend: Create `/api/alerts/<id>/acknowledge/` endpoint

**Why:** Mobile AlertsScreen has swipe-to-acknowledge. It POSTs to `/api/alerts/<id>/acknowledge/` which currently returns 404.

**File:** `backend/api/views.py`

Option A — Add as DRF action on AlertViewSet:

```python
from rest_framework.decorators import action
from rest_framework.response import Response

class AlertViewSet(viewsets.ModelViewSet):
    # ... existing code ...

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.is_resolved = True
        alert.save(update_fields=['is_resolved'])
        return Response({'status': 'ok'})
```

Option B — Standalone view:

```python
@api_view(['POST'])
def acknowledge_alert(request, alert_id):
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)
    alert.is_resolved = True
    alert.save(update_fields=['is_resolved'])
    return Response({'status': 'ok'})
```

**File:** `backend/api/urls.py`

If using Option A: No URL change needed (DRF router auto-generates `alerts/{pk}/acknowledge/`).

If using Option B: Add to urlpatterns:
```python
path('alerts/<int:alert_id>/acknowledge/', views.acknowledge_alert, name='acknowledge-alert'),
```

---

## Change 4 — Backend: Support `hours` parameter in sensor-history

**Why:** Mobile SensorDetailScreen has time selector (6/12/24/48/72 hours) but backend hardcodes 24h. The selector UI is currently non-functional.

**File:** `backend/api/views.py` — `sensor_history_api` function (~line 162)

Current:
```python
since = timezone.now() - timedelta(hours=24)
```

Change to:
```python
hours = int(request.query_params.get('hours', 24))
hours = min(max(hours, 1), 72)
since = timezone.now() - timedelta(hours=hours)
```

---

## Change 5 — Mobile: Remove PredictionsScreen

**Why:** All 3 tabs (Predictions, Weather, River) call non-existent endpoints. Every API call returns 404.

**File to delete:** `FloodGuardMobile/src/screens/PredictionsScreen.js`

**File:** `FloodGuardMobile/App.js`

Remove:
- Line 11: `import PredictionsScreen from './src/screens/PredictionsScreen';`
- Line 23: `Predictions: { active: 'trending-up', inactive: 'trending-up-outline' },` (in TAB_ICONS)
- Inside Tab.Navigator: `<Tab.Screen name="Predictions" component={PredictionsScreen} />`

---

## Change 6 — Mobile: Remove dead API groups from api.js

**Why:** `weatherAPI`, `floodAPI`, `predictionAPI` call non-existent endpoints. `bulkAcknowledge` is never used.

**File:** `FloodGuardMobile/src/services/api.js`

Delete these blocks:
- Lines 41-42: `bulkAcknowledge` from alertAPI
- Lines 44-46: entire `weatherAPI` export
- Lines 48-50: entire `floodAPI` export
- Lines 52-55: entire `predictionAPI` export

---

## Change 7 — Mobile: Clean up SensorDetailScreen.js

**Why:** References predictionAPI (non-existent endpoint), and fields that don't exist in backend models (battery_pct, wifi_rssi, water_temperature, battery_voltage).

**File:** `FloodGuardMobile/src/screens/SensorDetailScreen.js`

Changes:
- Line 8: Change `import { sensorAPI, predictionAPI }` → `import { sensorAPI }`
- Line 17: Delete `const [prediction, setPrediction] = useState(null);`
- Lines 25-28: Remove predictionAPI call from fetchData, keep only history fetch
- Lines 167-188: Delete entire `{prediction?.predictions && (...)}` block
- Lines 200-205: Delete `water_temperature` and `battery_voltage` references
- Lines 217-218: Delete `battery_pct` and `wifi_rssi` from info grid
- Lines 301-313: Delete `predSection`, `predRow`, `predDot`, `predLabel`, `predTime`, `predBar`, `predFill`, `predProb` styles
- Delete `readingTemp` and `readingBattery` styles

---

## Change 8 — Mobile: Delete SplashScreen.js

**Why:** 214-line component that is never imported or used anywhere.

**File to delete:** `FloodGuardMobile/src/components/SplashScreen.js`

---

## Summary: What each mobile screen will show after all changes

| Screen | Shows | Data Source |
|---|---|---|
| Dashboard | Sensor cards (name, location, level, status), stats grid (total, active, alerts, readings today) | `/api/sensor-status/` + `/api/system-stats/` |
| Map | Color-coded markers at GPS coordinates, sidebar sensor list, legend | `/api/sensor-status/` |
| Alerts | Filterable alert list (all/active/critical/danger/warning), swipe-to-acknowledge, resolved badges | `/api/dashboard-data/` + `/api/alerts/{id}/acknowledge/` |
| Sensor Detail | Water gauge, sparkline (6/12/24/48/72h), recent readings, sensor info (device, location, coords, last ping) | `/api/sensor-history/{id}/` + route params |
| Settings | Server URL config, poll interval, system stats (total sensors, online, readings, alerts), connection test | `/api/system-stats/` |

---

## Implementation order

1. Changes 1-4 (backend) — add/fix endpoints
2. Changes 5-8 (mobile) — remove dead code per remove.md
3. Test: start backend on 0.0.0.0:8000, start Expo, configure IP in Settings
