#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

// ===== WiFi Info =====
const char* ssid = "iot";
const char* password = "12345678";

// ===== POST URL =====
const char* postServerURL = "http://iotcloud22.in/4560/post_value.php";   // <-- CHANGE YOUR FINAL POST API

LiquidCrystal_I2C lcd(0x27, 16, 2);

// Ultrasonic pins (GPIO)
#define TRIG 14   // D5
#define ECHO 12   // D6
#define BUZZER 13 // D7

WiFiClient client;
HTTPClient http;

// ===== Distance Function =====
int getDistance() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  long duration = pulseIn(ECHO, HIGH, 30000);  
  int distance = duration * 0.034 / 2;
  return distance;
}

// ===== POST FUNCTION =====
void postValues(int distance) {
  String postData = "value1=" + String(distance);
  Serial.println("Posting: " + postData);

  if (WiFi.status() == WL_CONNECTED) {
    http.begin(client, postServerURL);
    http.addHeader("Content-Type", "application/x-www-form-urlencoded");
    int httpCode = http.POST(postData);
    Serial.print("POST code: "); Serial.println(httpCode);
    http.end();
  } else {
    Serial.println("WiFi not connected — skipping POST");
  }
}

void setup() {
  Serial.begin(115200);

  lcd.init();
  lcd.backlight();

  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  pinMode(BUZZER, OUTPUT);

  // ===== WiFi Connect =====
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Handwash System");
}

void loop() {

  int distance = getDistance();
  Serial.println(distance);

  if (distance > 0 && distance < 20) {
    digitalWrite(BUZZER, HIGH);
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("HANDWASH");
    lcd.setCursor(0, 1);
    lcd.print("COMPLETED");
  } 
  else {
    digitalWrite(BUZZER, LOW);
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("DETECTING");
    lcd.setCursor(0, 1);
    lcd.print("WAIT FOR HAND");
  }

  postValues(distance);

  delay(300);
}
