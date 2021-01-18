from gpiozero import ButtonBoard, Button
from gpiozero.mixins import HoldMixin
from gpiozero.devices import CompositeDevice
from signal import pause
from time import sleep
from functools import wraps 


#graph = LEDBarGraph(2, 3, 4, 5)
#btns = ButtonBoard(5, 6, 13, 26)




class MultiButton(Button):

    def __init__(
            self, pin=None, pull_up=True, active_state=None, bounce_time=None,
            hold_time=1, hold_repeat=False, pin_factory=None, parent=None):
        super(MultiButton, self).__init__(
            pin, pull_up=True, active_state=None, bounce_time=None,
            hold_time=1, hold_repeat=False, pin_factory=None)
        self.parent = parent
    
    def _wrap_callback(self, fn):
        @wraps(fn)
        def wrapper():
            return fn(self.parent)
        return wrapper

class MultiButtonBoard(HoldMixin, CompositeDevice):
    """
    Extends :class:`CompositeDevice` and represents a generic button board or
    collection of buttons. The :attr:`value` of the button board is a tuple
    of all the buttons states. This can be used to control all the LEDs in a
    :class:`LEDBoard` with a :class:`ButtonBoard`::

        from gpiozero import LEDBoard, ButtonBoard
        from signal import pause

        leds = LEDBoard(2, 3, 4, 5)
        btns = ButtonBoard(6, 7, 8, 9)
        leds.source = btns.values
        pause()

    Alternatively you could represent the number of pressed buttons with an
    :class:`LEDBarGraph`::

        from gpiozero import LEDBarGraph, ButtonBoard
        from signal import pause

        graph = LEDBarGraph(2, 3, 4, 5)
        btns = ButtonBoard(6, 7, 8, 9)
        graph.source = (sum(value) for value in btn.values)
        pause()

    :type pins: int or str
    :param \\*pins:
        Specify the GPIO pins that the buttons of the board are attached to.
        See :ref:`pin-numbering` for valid pin numbers. You can designate as
        many pins as necessary.

    :type pull_up: bool or None
    :param pull_up:
        If :data:`True` (the default), the GPIO pins will be pulled high by
        default.  In this case, connect the other side of the buttons to
        ground.  If :data:`False`, the GPIO pins will be pulled low by default.
        In this case, connect the other side of the buttons to 3V3. If
        :data:`None`, the pin will be floating, so it must be externally pulled
        up or down and the ``active_state`` parameter must be set accordingly.

    :type active_state: bool or None
    :param active_state:
        See description under :class:`InputDevice` for more information.

    :param float bounce_time:
        If :data:`None` (the default), no software bounce compensation will be
        performed. Otherwise, this is the length of time (in seconds) that the
        buttons will ignore changes in state after an initial change.

    :param float hold_time:
        The length of time (in seconds) to wait after any button is pushed,
        until executing the :attr:`when_held` handler. Defaults to ``1``.

    :param bool hold_repeat:
        If :data:`True`, the :attr:`when_held` handler will be repeatedly
        executed as long as any buttons remain held, every *hold_time* seconds.
        If :data:`False` (the default) the :attr:`when_held` handler will be
        only be executed once per hold.

    :type pin_factory: Factory or None
    :param pin_factory:
        See :doc:`api_pins` for more information (this is an advanced feature
        which most users can ignore).

    :type named_pins: int or str
    :param \\*\\*named_pins:
        Specify GPIO pins that buttons of the board are attached to,
        associating each button with a property name. You can designate as
        many pins as necessary and use any names, provided they're not already
        in use by something else.
    """
    def __init__(self, *args, **kwargs):
        pull_up = kwargs.pop('pull_up', True)
        active_state = kwargs.pop('active_state', None)
        bounce_time = kwargs.pop('bounce_time', None)
        hold_time = kwargs.pop('hold_time', 1)
        hold_repeat = kwargs.pop('hold_repeat', False)
        pin_factory = kwargs.pop('pin_factory', None)
        order = kwargs.pop('_order', None)
        self.callbacks = kwargs.pop('callbacks', None)
        print(self.callbacks)
        
        super(MultiButtonBoard, self).__init__(
            *(
                MultiButton(pin, pull_up=pull_up, active_state=active_state,
                       bounce_time=bounce_time, hold_time=hold_time,
                       hold_repeat=hold_repeat, parent = self)
                for pin in args
            ),
            _order=order,
            pin_factory=pin_factory,
            **{
                name: MultiButton(pin, pull_up=pull_up, active_state=active_state,
                             bounce_time=bounce_time, hold_time=hold_time,
                             hold_repeat=hold_repeat, parent = self)
                for name, pin in kwargs.items()
            }
        )
        if len(self) == 0:
            raise GPIOPinMissing('No pins given')
        def get_new_handler(device):
            def fire_both_events(ticks, state):
                device._fire_events(ticks, device._state_to_value(state))
                self._fire_events(ticks, self.value)
            return fire_both_events
        # _handlers only exists to ensure that we keep a reference to the
        # generated fire_both_events handler for each Button (remember that
        # pin.when_changed only keeps a weak reference to handlers)
        self._handlers = tuple(get_new_handler(device) for device in self)
        for button, handler in zip(self, self._handlers):
            button.pin.when_changed = handler
        self._when_changed = None
        self._last_value = None
        self.when_changed = self.choose_callback
        # Call _fire_events once to set initial state of events
        self._fire_events(self.pin_factory.ticks(), self.is_active)
        self.hold_time = hold_time
        self.hold_repeat = hold_repeat
        

    def choose_callback(self, parent):
        #print('choose callback')
        v1 = parent.pin1.value
        v2 = parent.pin2.value
                
        #if v1 and v2:
        if v1 and not v2:
            self.callbacks[0]()
        
        if v2 and not v1:
            self.callbacks[1]()

        if v1 and v2:
            self.callbacks[2]()

        sleep(.2)
        

    @property
    def pull_up(self):
        """
        If :data:`True`, the device uses a pull-up resistor to set the GPIO pin
        "high" by default.
        """
        return self[0].pull_up

    @property
    def when_changed(self):
        return self._when_changed

    @when_changed.setter
    def when_changed(self, value):
        print('when_changed')
        self._when_changed = self._wrap_callback(value)
        print(self._when_changed)

    def _fire_changed(self):
        if self.when_changed:
            self.when_changed()

    def _fire_events(self, ticks, new_value):
        super(MultiButtonBoard, self)._fire_events(ticks, new_value)
        old_value, self._last_value = self._last_value, new_value
        if old_value is None:
            # Initial "indeterminate" value; don't do anything
            pass
        elif old_value != new_value:
            self._fire_changed()




def fun1():
    print('1')

def fun2():
    print('2')

def fun3():
    print('3')

def presser(parent):
    v1 = parent.btn1.value
    v2 = parent.btn2.value
    #if v1 and v2:
    if v1 and not v2:
        print('Play 4')
    
    if v2 and not v1:
        print('Play 5')

    if v1 and v2:
        print('Play 7')

    sleep(.2)
    

#btns.btn1.when_pressed = presser
#btns.btn2.when_pressed = presser
#btns.when_changed = presser

btns = MultiButtonBoard(pin1 = 5, pin2 = 6, bounce_time = .5,
    callbacks = (fun1, fun2, fun3))



pause()



# while True:
#     for v in btns.value:
#         print(v)

#     print('----------------')
#     sleep(.5)
# #pause()