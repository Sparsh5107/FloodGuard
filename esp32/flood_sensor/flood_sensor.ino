#include <HTTPClient.h>
#include <WiFi.h>

// TODO: Fill in your WiFi credentials before uploading
const char *ssid = "Airtel_spar_5120";
const char *password = "OneTwoThree4#";

// TODO: Fill in your backend server URL
const char *serverUrl = "http://192.168.1.7:8000/api/sensor-data/";

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
  long sum = 0;
  for (int i = 0; i < 10; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  float avg = sum / 10.0;
  float levelCm = map(avg, 0, 4095, 0, 100);
  return levelCm;
}

void sendSensorData(const char *deviceId, float levelCm) {
  for (int attempt = 0; attempt < 3; attempt++) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String jsonData = "{\"device_id\":\"" + String(deviceId) +
                      "\",\"level_cm\":" + String(levelCm) + "}";
    int httpResponseCode = http.POST(jsonData);
    http.end();

    if (httpResponseCode > 0) {
      Serial.print("Sent ");
      Serial.print(deviceId);
      Serial.print(": ");
      Serial.print(levelCm);
      Serial.println(" cm");
      return;
    }

    Serial.print("Retry ");
    Serial.print(attempt + 1);
    Serial.print("/3 for ");
    Serial.println(deviceId);
    delay(100);
  }
  Serial.println("Failed after 3 attempts: " + String(deviceId));
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
