#include <Wire.h>

const int MPU = 0x68; // MPU6050 I2C address
int16_t AcX, AcY, AcZ;

void setup() {
  Wire.begin();
  Wire.beginTransmission(MPU);
  Wire.write(0x6B);  // PWR_MGMT_1 register
  Wire.write(0);     // wake up MPU6050
  Wire.endTransmission(true);

  Serial.begin(9600);
}

void loop() {
  // Request accelerometer data
  Wire.beginTransmission(MPU);
  Wire.write(0x3B);  // starting register for Accel readings
  Wire.endTransmission(false);
  Wire.requestFrom(MPU, 6, true);

  AcX = Wire.read() << 8 | Wire.read(); // Accel X
  AcY = Wire.read() << 8 | Wire.read(); // Accel Y
  AcZ = Wire.read() << 8 | Wire.read(); // Accel Z

  // Send data as comma-separated line
  Serial.print(AcX);
  Serial.print(",");
  Serial.print(AcY);
  Serial.print(",");
  Serial.println(AcZ);

  delay(50); // ~20 updates per second
}
