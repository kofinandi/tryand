// Drives the sorting mechanism from line-based commands sent by the laptop.
// Protocol is documented in the top-level README.
//
//   Upper trapdoor : two servos mounted mirrored, 0..90 deg, OPEN / CLOSE
//   Lower chute    : one servo, -45..+45 deg, LEFT / RIGHT
//
// Wiring (signal pins; servo power comes from the external 5 V supply, and its
// ground must be shared with the Arduino GND):
//   D9  -> trapdoor servo A signal
//   D10 -> trapdoor servo B signal
//   D11 -> chute servo signal

#include <Servo.h>

const long BAUD_RATE = 115200;

const uint8_t TRAP_A_PIN = 9;
const uint8_t TRAP_B_PIN = 10;
const uint8_t CHUTE_PIN = 11;

// ---- Calibration (servo angles, 0..180) -----------------------------------
// Trapdoor B is mirrored relative to A, so it travels the opposite way.
// If a door moves the wrong way, swap its CLOSED/OPEN values.
const int TRAP_A_CLOSED = 0;
const int TRAP_A_OPEN = 90;
const int TRAP_B_CLOSED = 90;
const int TRAP_B_OPEN = 0;

// Chute servo angles: centre is 45, left is 0, right is 90.
// If LEFT/RIGHT are swapped on the real hardware, swap those two values.
const int CHUTE_CENTER = 45;
const int CHUTE_LEFT = 0;
const int CHUTE_RIGHT = 90;

// ---- Motion ----------------------------------------------------------------
// Servos are moved in small steps so we do not slam the mechanism or pull a
// big current spike. Degrees per tick; one tick every TICK_MS.
const unsigned long TICK_MS = 10;
const int TRAP_STEP = 3;   // ~300 deg/s
const int CHUTE_STEP = 3;

struct Axis {
  Servo servo;
  int current;
  int target;
  int stepDeg;
};

Axis trapA, trapB, chute;

// Name of the command waiting to be reported as DONE ("" = none pending).
const char *trapPending = "";
const char *chutePending = "";

String line;

void initAxis(Axis &axis, uint8_t pin, int startAngle, int stepDeg) {
  axis.current = startAngle;
  axis.target = startAngle;
  axis.stepDeg = stepDeg;
  axis.servo.attach(pin);
  axis.servo.write(startAngle);
}

// Moves one axis a single step toward its target. Returns true when it arrives.
bool stepAxis(Axis &axis) {
  if (axis.current == axis.target) return true;
  int delta = axis.target - axis.current;
  if (abs(delta) <= axis.stepDeg) {
    axis.current = axis.target;
  } else {
    axis.current += (delta > 0) ? axis.stepDeg : -axis.stepDeg;
  }
  axis.servo.write(axis.current);
  return axis.current == axis.target;
}

void updateMotion() {
  static unsigned long lastTick = 0;
  unsigned long now = millis();
  if (now - lastTick < TICK_MS) return;
  lastTick = now;

  bool aDone = stepAxis(trapA);
  bool bDone = stepAxis(trapB);
  if (aDone && bDone && trapPending[0] != '\0') {
    Serial.print("DONE ");
    Serial.println(trapPending);
    trapPending = "";
  }

  if (stepAxis(chute) && chutePending[0] != '\0') {
    Serial.print("DONE ");
    Serial.println(chutePending);
    chutePending = "";
  }
}

void moveTrapdoors(int aTarget, int bTarget, const char *name) {
  trapA.target = aTarget;
  trapB.target = bTarget;
  trapPending = name;
}

void moveChute(int target, const char *name) {
  chute.target = target;
  chutePending = name;
}

void handleLine(const String &cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
  } else if (cmd == "OPEN") {
    moveTrapdoors(TRAP_A_OPEN, TRAP_B_OPEN, "OPEN");
    Serial.println("OK");
  } else if (cmd == "CLOSE") {
    moveTrapdoors(TRAP_A_CLOSED, TRAP_B_CLOSED, "CLOSE");
    Serial.println("OK");
  } else if (cmd == "LEFT") {
    moveChute(CHUTE_LEFT, "LEFT");
    Serial.println("OK");
  } else if (cmd == "RIGHT") {
    moveChute(CHUTE_RIGHT, "RIGHT");
    Serial.println("OK");
  } else {
    Serial.println("ERR unknown_command");
  }
}

void setup() {
  Serial.begin(BAUD_RATE);
  line.reserve(32);

  // Start with the trapdoors closed and the chute centred.
  initAxis(trapA, TRAP_A_PIN, TRAP_A_CLOSED, TRAP_STEP);
  initAxis(trapB, TRAP_B_PIN, TRAP_B_CLOSED, TRAP_STEP);
  initAxis(chute, CHUTE_PIN, CHUTE_CENTER, CHUTE_STEP);
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
  updateMotion();
}
