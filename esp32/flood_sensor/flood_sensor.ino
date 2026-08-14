#include <HTTPClient.h>
#include <WiFi.h>

// TODO: Fill in your WiFi credentials before uploading
const char *ssid = "YOUR_WIFI_SSID";
const char *password = "YOUR_WIFI_PASSWORD";

// TODO: Fill in your backend server URL
const char *serverUrl = "http://YOUR_SERVER_IP:8000/api/sensor-data/";

struct SensorConfig {
  const char *deviceId;
  const char *location;
  int pin;
};

SensorConfig sensors[] = {{"esp32-001", "Location A", 34},
                          {"esp32-002", "Location B", 35}};

const int NUM_SENSORS = 2;
const int SEND_INTERVAL = 1000;

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(sensors[i].pin, INPUT);
  }
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
}

float readWaterLevel(int pin) {
  int rawValue = analogRead(pin);
  float levelCm = map(rawValue, 0, 4095, 0, 100);
  return levelCm;
}

void sendSensorData(const char *deviceId, float levelCm) {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");

  String jsonData = "{\"device_id\":\"" + String(deviceId) +
                    "\",\"level_cm\":" + String(levelCm) + "}";
  int httpResponseCode = http.POST(jsonData);

  if (httpResponseCode > 0) {
    Serial.print("Sent ");
    Serial.print(deviceId);
    Serial.print(": ");
    Serial.print(levelCm);
    Serial.println(" cm");
  } else {
    Serial.print("Error: ");
    Serial.println(deviceId);
  }

  http.end();
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    for (int i = 0; i < NUM_SENSORS; i++) {
      float level = readWaterLevel(sensors[i].pin);
      sendSensorData(sensors[i].deviceId, level);
    }
  } else {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.begin(ssid, password);
  }

  delay(SEND_INTERVAL);
}
