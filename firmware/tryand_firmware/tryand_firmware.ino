// Receives line-based commands from the Python vision side.
// Protocol is documented in the top-level README.

const long BAUD_RATE = 115200;
const uint8_t OUTPUT_PIN = 9;  // PWM-capable pin

String line;

void handleLine(const String &cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
  } else if (cmd.startsWith("SET ")) {
    int value = cmd.substring(4).toInt();
    if (value < 0 || value > 255) {
      Serial.println("ERR out_of_range");
      return;
    }
    analogWrite(OUTPUT_PIN, value);
    Serial.println("OK");
  } else {
    Serial.println("ERR unknown_command");
  }
}

void setup() {
  pinMode(OUTPUT_PIN, OUTPUT);
  Serial.begin(BAUD_RATE);
  line.reserve(32);
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      line.trim();
      if (line.length() > 0) handleLine(line);
      line = "";
    } else if (line.length() < 32) {
      line += c;
    }
  }
}
