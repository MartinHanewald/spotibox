"""Main module."""
import os
import os.path
import signal
from pprint import pprint
from time import sleep, time

import pygame
import requests
import spotipy
from gpiozero import LED, PWMLED, Button
from PIL import Image
from requests import ReadTimeout
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from spotibox import albums
from spotibox.multibutton import MultiButtonBoard


class Spotibox():
    """
    This class implements the Spotibox player
    with GPIO controls.
    """

    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, debug=False):

        # init display
        pygame.display.init()
        # pygame.font.init()
        pygame.mouse.set_visible(False)
        self.displaysize = (pygame.display.Info().current_w,
                            pygame.display.Info().current_h)
        self.screen = pygame.display.set_mode(
            self.displaysize, pygame.FULLSCREEN)
        self.display_image('spotibox.PNG')
        self.fps = pygame.time.Clock()

        self.current = None
        self.current_image = None

        target = 'SPOTIBOX'
        scope = "user-read-playback-state,user-modify-playback-state"

        self.sp = spotipy.Spotify(client_credentials_manager=SpotifyOAuth(
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri))

        # Shows playing devices
        devs = self.sp.devices()

        self.target_id = next(d['id']
                              for d in devs['devices'] if d['name'] == target)

        print(f'Found device {target} at {self.target_id}.')

        if not debug:
            self.buttonconfig()

    def reset_timer(self):
        self.timer = time()
        self.led.on()

    def get_tracklist(self, uid):
        try:
            tracks = self.sp.album_tracks(uid)
        except ReadTimeout:
            print('API not reachable')
            sleep(2)
            return
        tracklist = [t['uri'] for t in tracks['items']]
        return tracklist

    def get_playlist_name(self, uid):
        try:
            thisname = self.sp.playlist(uid)['name']
        except ReadTimeout:
            print('API not reachable')
            return
        return thisname

    def get_album_name(self, uid):
        try:
            thisalbum = self.sp.album(uid)
        except ReadTimeout:
            print('API not reachable')
            return
        artist = " , ".join([n['name'] for n in thisalbum['artists']])
        name = thisalbum['name']
        return f'{artist} - {name}'

    def playback(self, uid):
        if 'album' in uid:
            name = self.get_album_name(uid)
        else:
            name = self.get_playlist_name(uid)
        try:
            self.sp.start_playback(
                device_id=self.target_id,
                context_uri=uid
            )
            print(f'Playing {name}')

        except ReadTimeout:
            print('API not reachable')
            return

        self.sp.volume(50)
        self.display_image(
            self.get_image(uid)
        )
        self.display_track_number()
        self.display_volume()
        self.reset_timer()

    def pause_resume(self):
        try:
            if self.sp.current_playback()["is_playing"]:
                self.pause()
            else:
                self.resume()
        except ReadTimeout:
            print('API not reachable')
        except TypeError:
            print('Nothing playing yet.')
        self.reset_timer()

    def pause(self):
        try:
            self.current = self.sp.current_playback()
            self.sp.pause_playback()
            print('Playback paused.')
        except SpotifyException as err:
            print(err.msg)
        except ReadTimeout:
            print('API not reachable')

    def resume(self):
        try:
            self.sp.start_playback(device_id=self.current['device']['id'],
                                   context_uri=self.current['context']['uri'],
                                   offset={'uri': self.current['item']['uri']},
                                   position_ms=self.current['progress_ms'])
        except ReadTimeout:
            print('API not reachable')
            return

    def volume_up(self):
        try:
            current_vol = self.sp.current_playback()[
                'device']['volume_percent']
            newvol = max(0, current_vol + 10)
            print(f'Setting volume to {newvol}')
            self.sp.volume(newvol)
        except ReadTimeout:
            print('API not reachable')
            return
        self.reset_timer()
        self.display_volume()

    def volume_down(self):
        try:
            current_vol = self.sp.current_playback()[
                'device']['volume_percent']
            newvol = max(0, current_vol - 10)
            print(f'Setting volume to {newvol}')
            self.sp.volume(newvol)
        except ReadTimeout:
            print('API not reachable')
            return
        self.reset_timer()
        self.display_volume()

    def next_track(self):
        print('Next track...')
        try:
            self.sp.next_track()
        except ReadTimeout:
            print('API not reachable')
            return
        self.display_track_number()
        self.reset_timer()

    def get_image(self, uid):
        try:
            if 'album' in uid:
                res = self.sp.album(uid)
            else:
                res = self.sp.playlist(uid)
            fileurl = res['images'][0]['url']
            filename = f"{fileurl.split('/')[-1]}.jpg"
            if not os.path.isfile(f'assets/{filename}'):
                r = requests.get(fileurl, allow_redirects=True)
                open(f'assets/{filename}', 'wb').write(r.content)
        except ReadTimeout:
            print('API not reachable')
            return
        return filename

    def shutdown(self):
        print('Shutting down...')
        pygame.display.quit()
        os.system(f'sudo shutdown -f now')

    def display_image(self, filename):
        Image.open(f"./assets/{filename}").save("./assets/temp.bmp")
        picture = pygame.image.load("assets/temp.bmp")
        print(f'Displaying {filename} with size {picture.get_size()}')

        psize = picture.get_size()
        scale = self.displaysize[1]/psize[1]
        psize_new = tuple(int(s * scale) for s in psize)

        picture = pygame.transform.scale(picture, psize_new)
        coord = (int((self.displaysize[0] - psize_new[0]) / 2),
                 int((self.displaysize[1] - psize_new[1]) / 2))

        picture = pygame.transform.scale(picture, psize_new)
        self.screen.fill((0, 0, 0))
        self.screen.blit(picture, coord)
        self.current_image = filename

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

        LEDPIN = 23

        BUTTONPLAY1 = 4
        BUTTONPLAY2 = 27
        BUTTONPLAY3 = 22

        # Group to Buttonboard 1 -> PLAY7
        BUTTONPLAY4 = 5
        BUTTONPLAY5 = 6

        # Group to BUttonboard 2 -> PLAY8
        BUTTONPLAY6 = 13
        BUTTONPAUSE = 26

        BUTTONVOLUP = 14
        BUTTONVOLDOWN = 15
        BUTTONNEXT = 12

        self.led = PWMLED(LEDPIN)

        mltbtns1 = MultiButtonBoard(pin1=BUTTONPLAY4, pin2=BUTTONPLAY5, bounce_time=.5,
                                    callbacks=(
                                        lambda: self.playback(albums.album4),
                                        lambda: self.playback(albums.album5),
                                        lambda: self.playback(albums.album7)
                                    ))

        mltbtns2 = MultiButtonBoard(pin1=BUTTONPLAY6, pin2=BUTTONPAUSE, bounce_time=.5,
                                    callbacks=(
                                        lambda: self.playback(albums.album6),
                                        self.pause_resume,
                                        lambda: self.playback(albums.album8)
                                    ))

        buttonplay1 = Button(BUTTONPLAY1)
        buttonplay1.when_pressed = lambda: self.playback(albums.album1)

        buttonplay2 = Button(BUTTONPLAY2)
        buttonplay2.when_pressed = lambda: self.playback(albums.album2)

        buttonplay3 = Button(BUTTONPLAY3)
        buttonplay3.when_pressed = lambda: self.playback(albums.album3)

        # buttonplay4 = Button(BUTTONPLAY4)
        # buttonplay4.when_pressed = lambda: self.playback(albums.album4)

        # buttonplay5 = Button(BUTTONPLAY5)
        # buttonplay5.when_pressed = lambda: self.playback(albums.album5)

        # buttonplay6 = Button(BUTTONPLAY6)
        # buttonplay6.when_pressed = lambda: self.playback(albums.album6)

        # buttonpause = Button(BUTTONPAUSE, pull_up = True, hold_time=3, active_state=None)
        # buttonpause.when_pressed = self.pause_resume
        # # buttonpause.when_held = self.shutdown

        buttonnext = Button(BUTTONNEXT)
        buttonnext.when_pressed = self.next_track

        buttonvolup = Button(BUTTONVOLUP)
        buttonvolup.when_pressed = self.volume_up

        buttonvoldown = Button(BUTTONVOLDOWN)
        buttonvoldown.when_pressed = self.volume_down

        self.reset_timer()

        signal.signal(signal.SIGTERM, self.service_shutdown)
        signal.signal(signal.SIGINT, self.service_shutdown)

        print('Starting main loop')
        try:
            while True:
                timediff = time() - self.timer
                if timediff > 300:
                    try:
                        if not self.sp.current_playback()["is_playing"]:
                            self.shutdown()
                    except ReadTimeout:
                        print('API not reachable')
                    except TypeError:
                        self.shutdown()

                if timediff > 30:
                    self.display_fade()

                pygame.display.update()
                self.fps.tick(30)
        except ServiceExit:
            pygame.display.quit()
            print('Exiting!')

    def display_track_number(self):
        try:
            playback = self.sp.current_playback()
        except ReadTimeout:
            print('API not reachable')
            return

        context_uri = playback['context']['uri']
        # if playback["is_playing"]:
        if 'album' in context_uri:
            total = playback['item']['album']['total_tracks']
            current = playback['item']['track_number']
        else:
            try:
                playlist = self.sp.playlist(context_uri)
            except ReadTimeout:
                print('API not reachable')
                return
            pl_tracks = [i['track']['uri']
                         for i in playlist['tracks']['items']]
            pb_track = playback['item']['uri']
            total = len(pl_tracks)
            current = pl_tracks.index(pb_track) + 1

        self.remove_boxes('left')
        self.draw_boxes(total, current, 'left')

    def display_volume(self):
        try:
            current_vol = self.sp.current_playback()[
                'device']['volume_percent']
        except ReadTimeout:
            print('API not reachable')
            return
        self.remove_boxes('right')
        self.draw_boxes(10, int(current_vol/10), 'right')

    def clear_screen(self):
        self.screen.fill((0, 0, 0))
        self.display_image(self.current_image)

    def display_fade(self):

        if self.led.value > 0:
            # self.led.off()
            for i in reversed(range(20)):
                self.led.value = i / 20
                self.fps.tick(100)

    def draw_boxes(self, n, active, side='left'):

        BASE = (50, 50, 50)
        ACTIVE = (150, 100, 250)

        X = 10 if side == 'left' else 290
        screen_h = 240
        box = screen_h / n
        margin = max(int(.1 * box), 1)
        h = box - 2 * margin

        for k in range(n):
            color = BASE if k >= active else ACTIVE
            pygame.draw.rect(self.screen, color,
                             (X, screen_h - h - margin - box * k, 20, h))

    def remove_boxes(self, side='left'):
        X = 10 if side == 'left' else 290
        color = (0, 0, 0)
        pygame.draw.rect(self.screen, color,
                         (X, 0, 20, 240))

    def service_shutdown(self, signum, frame):
        print('Caught signal %d' % signum)
        raise ServiceExit


class ServiceExit(Exception):
    """
    Custom exception which is used to trigger the clean exit
    of all running threads and the main program.
    """
    pass
