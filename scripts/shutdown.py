from gpiozero import Button
from subprocess import check_call
from signal import pause

BUTTONPAUSE = 26
BUTTONNEXT = 12

def shutdown():
    print('Shutting down...')
    check_call(['sudo', 'shutdown', '-f', 'now'])

def reboot():
    print('Rebooting...')
    check_call(['sudo', 'reboot'])

shutdown_btn = Button(BUTTONPAUSE, hold_time=3)
shutdown_btn.when_held = shutdown

reboot_btn = Button(BUTTONNEXT, hold_time=3)
reboot_btn.when_held = reboot

print('Waiting for shutdown/reboot trigger...')

pause()