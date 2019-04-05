static int NTURNS = 10; //Number of simulated wheel turns
static int WHEEL_PULSE_WIDTH = 10; //Time between high and low state on single wheel event
static int WHEEL_INTERVAL = 1000-WHEEL_PULSE_WIDTH; //Number of seconds between wheel events
static int DELAY_DOOR_OPEN = 5000; //Time between wheel event and door open
static int DELAY_DOOR_CLOSED = 4000; //Time between door open and door closed
static int DELAY_WHEEL_START = 5000; //Time between door closed and start of wheel
static float JITTER = 0.9; //Ratio of +/- random jitter to be applied to time values
static int WHEEL_PIN = 6;
static int DOOR_PIN = 5;
static int PUMP_PIN = 3;
static int SLEEP = 30; //Duration of sleep cycle (minutes)
static int SLEEP_PROBABILITY = 5

0...; //Percent probability that the mouse sleeps each cycle 

int a = 0; //Event counter
long stopTime = 0; //Stop time for door event
boolean pumpOn = false;
boolean state = false; //Pin state
int minTime = 0;
int maxTime = 0;
int turns = 0;


void jitter(int timeDelay){
  minTime = timeDelay - timeDelay * JITTER;
  maxTime = timeDelay + timeDelay * JITTER;
  timeDelay = random(minTime, maxTime);
  Serial.print(" - Delay: ");
  Serial.println(timeDelay);
  delay(timeDelay);
}

void pumpISR(){
  pumpOn = !digitalRead(PUMP_PIN);
  if (pumpOn) Serial.println("Pump on");
  else Serial.println("Pump off");
}

void flip(int pin){
  state = !digitalRead(pin);
  digitalWrite(pin, state);
  digitalWrite(13, state);  
}

void printWheel(int rev){
    Serial.print("Wheel rev ");
    Serial.print(rev);
    Serial.print(" of ");
    Serial.println(turns);
}

void setup() {
  // put your setup code here, to run once:
  pinMode(WHEEL_PIN, OUTPUT); //11
  pinMode(DOOR_PIN, OUTPUT); //13
  pinMode(PUMP_PIN, INPUT_PULLUP); //22
  pinMode(7, OUTPUT); //GND
  pinMode(13, OUTPUT); //output mirror
  digitalWrite(WHEEL_PIN, LOW);
  digitalWrite(DOOR_PIN, LOW);
  digitalWrite(7, LOW); //Set pin 7 as ground
  digitalWrite(13, LOW); //Initialize pin 13 
  Serial.begin(250000);

  //Setup interrupt to monitor pump state
  attachInterrupt(digitalPinToInterrupt(PUMP_PIN), pumpISR, CHANGE);
}

void loop() {
  //Simulate wheel
  turns = random(0,2*NTURNS);
  for(a=1; a<=turns; a++){
    flip(WHEEL_PIN);
    delay(WHEEL_PULSE_WIDTH);
    flip(WHEEL_PIN);
    printWheel(a);
    delay(WHEEL_INTERVAL);
  } 
  Serial.print("End wheel");
  jitter(DELAY_DOOR_OPEN);

  //Simulate door open
  flip(DOOR_PIN);
  Serial.print("Door open"); 
  jitter(DELAY_DOOR_CLOSED);
  
  //Simulate door closed
  flip(DOOR_PIN);
  Serial.print("Door closed");
  jitter(DELAY_WHEEL_START);

  //Check if mouse sleeps
  if (random(1-100) < SLEEP_PROBABILITY){
    for(a=SLEEP; a>0; a--){
      Serial.print("Sleeping for ");
      Serial.print(a);
      Serial.println(" more minutes.");
      delay(60000);
    }
  }
}
