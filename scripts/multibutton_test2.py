import RPi.GPIO as GPIO
import time


GPIO.setmode(GPIO.BCM)
A = 13
B = 26

GPIO.setup(A, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(B, GPIO.IN, pull_up_down = GPIO.PUD_UP)

while True:
    print(f'{GPIO.input(A)} \t {GPIO.input(B)}')
    time.sleep(0.2)

