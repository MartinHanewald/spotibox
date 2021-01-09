import RPi.GPIO as GPIO
import time


GPIO.setmode(GPIO.BCM)


GPIO.setup(14, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(15, GPIO.IN, pull_up_down = GPIO.PUD_UP)

while True:
    print(f'{GPIO.input(14)} \t {GPIO.input(15)}')
    time.sleep(0.2)

