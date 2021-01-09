"""Main module."""
from gpiozero import LED, Button
from signal import pause
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pprint import pprint
from time import sleep
import requests
import os.path
import os
from spotibox import albums
from spotipy.exceptions import SpotifyException
from requests import ReadTimeout

class Spotibox():
    """
    This class implements the Spotibox player
    with GPIO controls.
    """

    def __init__(self, client_id=None, client_secret=None, redirect_uri=None):
        self.display_image('spotibox.PNG')
        self.current = None

        target = 'SPOTIBOX'
        scope = "user-read-playback-state,user-modify-playback-state"
        try:
            self.sp = spotipy.Spotify(client_credentials_manager=SpotifyOAuth(
                scope=scope,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri))

            # Shows playing devices
            devs = self.sp.devices()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            self.__init__(client_id, client_secret, redirect_uri)
        self.target_id = next(d['id'] for d in devs['devices'] if d['name'] == target)

        print(f'Found device {target} at {self.target_id}.')
        self.buttonconfig()

    def get_tracklist(self, uid):
        try:
            tracks = self.sp.album_tracks(uid)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.get_tracklist(uid)
        tracklist = [t['uri'] for t in tracks['items']]
        return tracklist

    def get_album_name(self, uid):
        try:
            thisalbum = self.sp.album(uid)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.get_album_name(uid)
        artist = " , ".join([n['name'] for n in thisalbum['artists']])
        name = thisalbum['name']
        return f'{artist} - {name}'


    def playback(self, uid):
        try:
            print(f'Playing {self.get_album_name(uid)}')
            #self.led.on()
            self.sp.start_playback(
                device_id = self.target_id,
                context_uri=uid
                #uris = self.get_tracklist(uid)
            )
            self.sp.volume(50)
            self.display_image(
                self.get_image(uid)
            )
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.playback(uid)

    def pause_resume(self):
        try:
            if self.sp.current_playback()["is_playing"]:
                self.pause()
            else:
                self.resume()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.pause_resume()

    def pause(self):
        try:
            self.current = self.sp.current_playback()
            self.sp.pause_playback()
            print('Playback paused.')
        except SpotifyException as err:
            print(err.msg)

    def resume(self):
        self.sp.start_playback(device_id = self.current['device']['id'],
                      context_uri = self.current['context']['uri'],
                      offset={'uri':self.current['item']['uri']},
                      position_ms=self.current['progress_ms'])
    def volume_up(self):
        #self.led.on()
        try:
            current_vol = self.sp.current_playback()['device']['volume_percent']
            newvol = min(100, current_vol + 10)
            print(f'Setting volume to {newvol}')
            self.sp.volume(newvol)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.volume_up()


    def volume_down(self):
        try:
            current_vol = self.sp.current_playback()['device']['volume_percent']
            newvol = max(0, current_vol - 10)
            print(f'Setting volume to {newvol}')
            self.sp.volume(newvol)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.volume_down()

    def next_track(self):
        print('Next track...')
        try:
            self.sp.next_track()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.next_track()    
        

    def get_image(self, uid):
        try:
            res = self.sp.album(uid)   
            fileurl = res['images'][0]['url']
            filename = f"{fileurl.split('/')[-1]}.jpg"
            if not os.path.isfile(f'/home/pi/spotibox/assets/{filename}'):
                r = requests.get(fileurl, allow_redirects=True)
                open(f'/home/pi/spotibox/assets/{filename}', 'wb').write(r.content)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.get_image(uid)   
        return filename

    def display_image(self, filename):
        os.system(f'fbi -d /dev/fb0 -T 2 -a -noverbose /home/pi/spotibox/assets/{filename}')

    def buttonconfig(self):
        # Default wiring with colored patch cable
        # WHITE - GROUND
        # BLACK - 5 - LED
        # GREY - 12 - BUTTON NEXT
        # PURPLE - 6 - BUTTON PLAY 1
        # BLUE - 13 - BUTTON PLAY 2
        # GREEN - 16 - BUTTON VOL UP
        # YELLOW - 26 - BUTTON VOL DOWN

        # NOT 19, 20, 21

        # LEDPIN = 5
        
        BUTTONPLAY1 = 4
        BUTTONPLAY2 = 27
        BUTTONPLAY3 = 22
        BUTTONPLAY4 = 5
        BUTTONPLAY5 = 6
        BUTTONPLAY6 = 13
        BUTTONVOLUP = 14 # Temporary until Diode setup
        BUTTONVOLDOWN = 15
        BUTTONPAUSE= 26
        BUTTONNEXT = 12


        #self.led = LED(LEDPIN)

        buttonplay1 = Button(BUTTONPLAY1)
        buttonplay1.when_pressed = lambda: self.playback(albums.album1)
        #buttonplay1.when_released = self.led.off

        buttonplay2 = Button(BUTTONPLAY2)
        buttonplay2.when_pressed = lambda: self.playback(albums.album2)
        #buttonplay2.when_released = self.led.off

        buttonplay3 = Button(BUTTONPLAY3)
        buttonplay3.when_pressed = lambda: self.playback(albums.album3)

        buttonplay4 = Button(BUTTONPLAY4)
        buttonplay4.when_pressed = lambda: self.playback(albums.album4)

        buttonplay5 = Button(BUTTONPLAY5)
        buttonplay5.when_pressed = lambda: self.playback(albums.album5)

        buttonplay6 = Button(BUTTONPLAY6)
        buttonplay6.when_pressed = lambda: self.playback(albums.album6)

        buttonnext = Button(BUTTONNEXT)
        buttonnext.when_pressed = self.next_track
        #buttonnext.when_released = self.led.off

        buttonpause = Button(BUTTONPAUSE)
        buttonpause.when_pressed = self.pause_resume
        #buttonnext.when_released = self.led.off

        buttonvolup = Button(BUTTONVOLUP)
        buttonvolup.when_pressed = self.volume_up
        #buttonvolup.when_released = self.led.off

        buttonvoldown = Button(BUTTONVOLDOWN)
        buttonvoldown.when_pressed = self.volume_down
        #buttonvoldown.when_released = self.led.off

        pause()




