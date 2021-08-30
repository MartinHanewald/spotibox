from spotibox.multibutton import MultiButton
from statistics import mean, stdev
import time
from signal import pause

CALIBRATE = False

def fun1():
    print('Button 1')

def fun2():
    print('Button 2')

def fun3():
    print('Button 3')

btn = MultiButton(14, 
        callbacks = {1: fun1,
                     2: fun2,
                     3: fun3} )



if not CALIBRATE:
    btn.blink()
else:
    vals = [btn.RCtime()]

while True:

    val = btn.RCtime()


    if(CALIBRATE):
    # This is for calibration
        vals.append(val)
        print('Mean {0:4.2f} \t SD: {1:4.2f}'.format(mean(vals), stdev(vals)))
        time.sleep(0.01)

    else:
        pause()

    #
    # print(btn._buttonval)
    #pause()
    #time.sleep(0.01)