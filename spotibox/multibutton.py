import warnings
from time import sleep, time
from threading import Event, Lock

from gpiozero.exc import InputDeviceError, DeviceClosed, DistanceSensorNoEcho, \
    PinInvalidState
from gpiozero.devices import GPIODevice
from gpiozero.mixins import GPIOQueue, EventsMixin, HoldMixin
from gpiozero.threads import GPIOThread


class MultiButton(EventsMixin, GPIODevice):
    """
    Represents a generic input device with typical on/off behaviour.

    This class extends :class:`InputDevice` with machinery to fire the active
    and inactive events for devices that operate in a typical digital manner:
    straight forward on / off states with (reasonably) clean transitions
    between the two.

    :type pin: int or str
    :param pin:
        The GPIO pin that the device is connected to. See :ref:`pin-numbering`
        for valid pin numbers. If this is :data:`None` a :exc:`GPIODeviceError`
        will be raised.

    :type pull_up: bool or None
    :param pull_up:
        See descrpition under :class:`InputDevice` for more information.

    :type active_state: bool or None
    :param active_state:
        See description under :class:`InputDevice` for more information.

    :type bounce_time: float or None
    :param bounce_time:
        Specifies the length of time (in seconds) that the component will
        ignore changes in state after an initial change. This defaults to
        :data:`None` which indicates that no bounce compensation will be
        performed.

    :type pin_factory: Factory or None
    :param pin_factory:
        See :doc:`api_pins` for more information (this is an advanced feature
        which most users can ignore).
    """
    def __init__(
            self, pin=None, callbacks = None,
            pin_factory=None):
        super(MultiButton, self).__init__(
            pin, pin_factory=pin_factory)
        self._callbacks = callbacks
        self._blink_thread = None
        self._controller = None
        self._buttonval = None
        self._prev_buttonval = None
        self._reading = None
        self._cooldown = 0.2
        self._last_tick = 0
        # try:
        #     #self.pin.bounce = bounce_time
        #     #self.pin.edges = 'rising'
        #     #self.pin.when_changed = self._check_buttons
        #     # Call _fire_events once to set initial state of events
        #     #self._fire_events(self.pin_factory.ticks(), self.is_active)
        # except:
        #     self.close()
        #     raise

    def _state_to_value(self, state):
        return state # int(state == self._active_state)

    def _read(self):
        try:
            return self._state_to_value(self.pin.state)
        except (AttributeError, TypeError):
            self._check_open()
            raise

    def _check_buttons(self, ticks):
        # XXX This is a bit of a hack; _fire_events takes *is_active* rather
        # than *value*. Here we're assuming no-one's overridden the default
        # implementation of *is_active*.
        if not self._prev_buttonval and \
            self._buttonval and \
            ticks - self._last_tick > self._cooldown:

            print('{0} \t {1} \t {2:4.2f} \t {3}' \
                .format(self._buttonval, self._prev_buttonval, self._reading, ticks))
            self._prev_buttonval = self._buttonval
            self._last_tick = ticks
            fn = self._callbacks[self._buttonval]
            fn()
        #self._fire_events(ticks, bool(self._state_to_value(state)))

    def blink(self, on_time=1, off_time=1, n=None, background=True):
        """
        Make the device turn on and off repeatedly.

        :param float on_time:
            Number of seconds on. Defaults to 1 second.

        :param float off_time:
            Number of seconds off. Defaults to 1 second.

        :type n: int or None
        :param n:
            Number of times to blink; :data:`None` (the default) means forever.

        :param bool background:
            If :data:`True` (the default), start a background thread to
            continue blinking and return immediately. If :data:`False`, only
            return when the blink is finished (warning: the default value of
            *n* will result in this method never returning).
        """
        self._stop_blink()
        self._blink_thread = GPIOThread(
            target=self._blink_device, args=(on_time, off_time, n)
        )
        self._blink_thread.start()
        if not background:
            self._blink_thread.join()
            self._blink_thread = None

    def _stop_blink(self):
        if getattr(self, '_controller', None):
            self._controller._stop_blink(self)
        self._controller = None
        if getattr(self, '_blink_thread', None):
            self._blink_thread.stop()
        self._blink_thread = None

    def _blink_device(self, on_time, off_time, n):
        sd = 1
        mean3 = 14
        mean2 = 26
        mean1 = 39
        mean0 = 45
        
        while True:
            val = self.RCtime()
            self._reading = val
            self._prev_buttonval = self._buttonval
            if mean3-3*sd <= val <= mean3+3*sd:
                self._buttonval = 3
            if mean2-3*sd <= val <= mean2+3*sd:
                self._buttonval = 2
            if mean1-3*sd <= val <= mean1+3*sd:
                self._buttonval = 1
            if mean0-3*sd <= val <= mean0+3*sd: 
                self._buttonval = None
            self._check_buttons(self.pin_factory.ticks())

            

    def RCtime(self):
        
        self.pin.output_with_state(0)
        #GPIO.setup(RCPin, GPIO.OUT, initial = GPIO.LOW)             # Set pin to output,
        #GPIO.output(RCPin, GPIO.LOW)           # and pull to low.    

        sleep(1/1000);                           # Allow time to let capacitor discharge.

        now = time()
        self.pin.input_with_pull('floating')
        #self.pin.function = 'input'
        #self.pin.pull = 'floating' 
                           
        #GPIO.setup(RCPin, GPIO.IN)              # Now set the pin to an input,

        #GPIO.input(RCPin)

        while self.pin.state == 0:
            sleep(0.0001)  # wait 10 ms to give CPU chance to do other things

        val = time()-now
        #print(val)
        return val * 10000   