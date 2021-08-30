#import RPIO
import RPi.GPIO as GPIO
from time import sleep, time
from statistics import mean, stdev
from gpiozero import SmoothedInputDevice
from gpiozero import Button
#from signal import pause

GPIO.setmode(GPIO.BCM)

#GPIO.setup(14, GPIO.OUT)

#GPIO.output(14, GPIO.HIGH)

#GPIO.output(14, GPIO.HIGH)

#RCPin = 14
def RCtime(RCPin):

  GPIO.setup(RCPin, GPIO.OUT, initial = GPIO.LOW)             # Set pin to output,
  #GPIO.output(RCPin, GPIO.LOW)           # and pull to low.    

  sleep(4/1000);                           # Allow time to let capacitor discharge.

  now = time()
                          
  GPIO.setup(RCPin, GPIO.IN)              # Now set the pin to an input,

  GPIO.input(RCPin)
  #pullUpDnControl(RCpin, PUD_OFF);    # turn off internal pull down resistor,
  #while (digitalRead(RCpin) == LOW);  # and wait for it to go high.
  #GPIO.wait_for_edge(RCPin, GPIO.RISING)
  while GPIO.input(RCPin) == GPIO.LOW:
    sleep(0.0001)  # wait 10 ms to give CPU chance to do other things

  val = time()-now

  return val * 10000                            
vals = [22]
sd = 0.6
mean3 = 7
mean2 = 12
mean1 = 17
mean0 = 23.2



while True:

    val = RCtime(14)
    vals.append(val)


    # This is for calibration
    #print('Mean {0:4.2f} \t SD: {1:4.2f}'.format(mean(vals), stdev(vals)))

    #print(val)
    #sleep(0.5)
    if mean3-3*sd <= val <= mean3+3*sd:
        print('Button 3')
    if mean2-3*sd <= val <= mean2+3*sd:
        print('Button 2')
    if mean1-3*sd <= val <= mean1+3*sd:
        print('Button 1')
    if mean0-3*sd <= val <= mean0+3*sd:
        print('No button pressed!')