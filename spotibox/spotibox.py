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

class Spotibox():
    """
    This class implements the Spotibox player
    with GPIO controls.
    """

    def __init__(self, client_id, client_secret, redirect_uri):
        self.display_image('spotibox.PNG')

        target = 'SPOTIBOX'
        scope = "user-read-playback-state,user-modify-playback-state"
        self.sp = spotipy.Spotify(client_credentials_manager=SpotifyOAuth(
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri))

        # Shows playing devices
        devs = self.sp.devices()
        self.target_id = next(d['id'] for d in devs['devices'] if d['name'] == target)

        print(f'Found device {target} at {self.target_id}.')
        self.buttonconfig()

    def get_tracklist(self, uid):
        tracks = self.sp.album_tracks(uid)
        tracklist = [t['uri'] for t in tracks['items']]
        return tracklist

    def get_album_name(self, uid):
        thisalbum = self.sp.album(uid)
        artist = " , ".join([n['name'] for n in thisalbum['artists']])
        name = thisalbum['name']
        return f'{artist} - {name}'


    def playback(self, uid):
        print(f'Playing {self.get_album_name(uid)}')
        self.led.on()
        self.sp.start_playback(
            device_id = self.target_id,
            uris = self.get_tracklist(uid))
        self.display_image(
            self.get_image(uid)
        )

    def volume_up(self):
        self.led.on()
        current_vol = self.sp.current_playback()['device']['volume_percent']
        newvol = min(100, current_vol + 10)
        print(f'Setting volume to {newvol}')
        self.sp.volume(newvol)


    def volume_down(self):
        self.led.on()
        current_vol = self.sp.current_playback()['device']['volume_percent']
        newvol = max(0, current_vol - 10)
        print(f'Setting volume to {newvol}')
        self.sp.volume(newvol)

    def next_track(self):
        self.led.on()
        print('Next track...')
        self.sp.next_track()

    def get_image(self, uid):
        res = self.sp.album(uid)   
        fileurl = res['images'][0]['url']
        filename = f"{fileurl.split('/')[-1]}.jpg"
        if not os.path.isfile(f'assets/{filename}'):
            r = requests.get(fileurl, allow_redirects=True)
            open(f'assets/{filename}', 'wb').write(r.content)
        return filename

    def display_image(self, filename):
        os.system(f'sudo fbi -d /dev/fb1 -T 2 -a -noverbose assets/{filename}')

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

        LEDPIN = 5
        BUTTONNEXT = 12
        BUTTONPLAY1 = 6
        BUTTONPLAY2 = 13
        BUTTONVOLUP = 16
        BUTTONVOLDOWN = 26

        self.led = LED(LEDPIN)

        buttonplay1 = Button(BUTTONPLAY1)
        buttonplay1.when_pressed = lambda: self.playback(albums.album1)
        buttonplay1.when_released = self.led.off

        buttonplay2 = Button(BUTTONPLAY2)
        buttonplay2.when_pressed = lambda: self.playback(albums.album2)
        buttonplay2.when_released = self.led.off

        buttonnext = Button(BUTTONNEXT)
        buttonnext.when_pressed = self.next_track
        buttonnext.when_released = self.led.off

        buttonvolup = Button(BUTTONVOLUP)
        buttonvolup.when_pressed = self.volume_up
        buttonvolup.when_released = self.led.off

        buttonvoldown = Button(BUTTONVOLDOWN)
        buttonvoldown.when_pressed = self.volume_down
        buttonvoldown.when_released = self.led.off

        pause()



