from gpiozero import Button
from subprocess import check_call
from signal import pause

BUTTONPAUSE= 26

def shutdown():
    print('Shutting down...')
    check_call(['sudo', 'shutdown', '-f', 'now'])

shutdown_btn = Button(BUTTONPAUSE, hold_time=3)
shutdown_btn.when_held = shutdown
print('Waiting for shutdown trigger...')

pause()