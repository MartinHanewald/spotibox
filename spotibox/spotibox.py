"""Main module."""
from gpiozero import PWMLED, Button
from signal import pause
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pprint import pprint
from time import sleep, time

import requests
import os.path
import os
from spotibox import albums
from spotipy.exceptions import SpotifyException
from requests import ReadTimeout

import pygame
from PIL import Image

class Spotibox():
    """
    This class implements the Spotibox player
    with GPIO controls.
    """

    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, debug = False):
        
        # init display
        pygame.display.init()
        pygame.font.init()
        pygame.mouse.set_visible(False)
        self.displaysize = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        self.screen = pygame.display.set_mode(self.displaysize, pygame.FULLSCREEN)
        self.display_image('spotibox.PNG')
        self.fps = pygame.time.Clock()

        self.current = None
        self.current_image = None
        self._circle_cache = {}
        
        target = 'SPOTIBOX'
        scope = "user-read-playback-state,user-modify-playback-state"
        
        self.sp = spotipy.Spotify(client_credentials_manager=SpotifyOAuth(
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri))

        # Shows playing devices
        devs = self.sp.devices()
        #except ReadTimeout:
        #    print('API not reachable, trying again in 2 secs')
        #    sleep(2)
        #    self.__init__(client_id, client_secret, redirect_uri)
        self.target_id = next(d['id'] for d in devs['devices'] if d['name'] == target)

        print(f'Found device {target} at {self.target_id}.')
        
        #self.loop = asyncio.get_event_loop()
        #self.loop.run_until_complete(self.main())
        if not debug:
            self.buttonconfig()

    def reset_timer(self):
        self.timer = time()
        self.led.value = 1
    
    async def main(self):
        asyncio.ensure_future(self.buttonconfig())
        asyncio.ensure_future(self.shutdown_timer())
        
    async def shutdown_timer(self):
        while True:
            sleep(2)
            print('Made it')

    def get_tracklist(self, uid):
        try:
            tracks = self.sp.album_tracks(uid)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.get_tracklist(uid)
        tracklist = [t['uri'] for t in tracks['items']]
        return tracklist

    def get_playlist_name(self, uid):
        try:
            thisname = self.sp.playlist(uid)['name']
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.get_playlist_name(uid)
        return thisname
    
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
            if 'album' in uid:
                name = self.get_album_name(uid)
            else:
                name = self.get_playlist_name(uid)
            print(f'Playing {name}')
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
            self.display_track_number()
            self.reset_timer()
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
            self.reset_timer()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.pause_resume()
        except TypeError:
            print('Nothing playing yet.')


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
            self.reset_timer()
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
            self.reset_timer()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.volume_down()

    def next_track(self):
        print('Next track...')
        try:
            self.sp.next_track()
            self.display_track_number()
            self.reset_timer()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.next_track()    
        

    def get_image(self, uid):
        try:
            if 'album' in uid:
                res = self.sp.album(uid)   
            else:
                res = self.sp.playlist(uid)
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
    
    def shutdown(self):
        print('Shutting down...')
        os.system(f'sudo shutdown -f now')

    def display_image(self, filename):       
        Image.open(f"/home/pi/spotibox/assets/{filename}").save("/home/pi/spotibox/assets/temp.bmp")
        picture = pygame.image.load("/home/pi/spotibox/assets/temp.bmp")
        #picture = pygame.image.load(f'assets/{filename}')
        print(f'Displaying {filename} with size {picture.get_size()}')
        picture = pygame.transform.scale(picture, self.displaysize)
        self.screen.blit(picture, (0, 0))
        self.current_image = filename
        #pygame.display.update()
        #os.system(f'sudo fbi -d /dev/fb0 -T 1 -a -noverbose /home/pi/spotibox/assets/{filename}')

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
        BUTTONPLAY4 = 5
        BUTTONPLAY5 = 6
        BUTTONPLAY6 = 13
        BUTTONVOLUP = 14 # Temporary until Diode setup
        BUTTONVOLDOWN = 15
        BUTTONPAUSE= 26
        BUTTONNEXT = 12


        self.led = PWMLED(LEDPIN)

        
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

        buttonpause = Button(BUTTONPAUSE, pull_up = True, hold_time=3, active_state=None)
        buttonpause.when_pressed = self.pause_resume
        buttonpause.when_held = self.shutdown
        #buttonnext.when_released = self.led.off

        buttonvolup = Button(BUTTONVOLUP)
        buttonvolup.when_pressed = self.volume_up
        #buttonvolup.when_released = self.led.off

        buttonvoldown = Button(BUTTONVOLDOWN)
        buttonvoldown.when_pressed = self.volume_down
        #buttonvoldown.when_released = self.led.off

        self.reset_timer()

        

        while True:
            timediff = time() - self.timer
            if timediff > 600:
                try:
                    if not self.sp.current_playback()["is_playing"]:
                        self.shutdown()
                except ReadTimeout:
                    print('API not reachable, trying again in 2 secs')
                except TypeError:
                    self.shutdown()
                    
            if timediff > 30:
                self.display_fade()
            #print(timediff)
            pygame.display.update()
            self.fps.tick(30)
        #pause()

    def display_track_number(self):
        font = pygame.font.Font(None, 60)
        self.clear_screen()
        # Render some white text (pyScope 0.1) onto text_surface
        try:
            if self.sp.current_playback()["is_playing"]:
                total = self.sp.current_playback()['item']['album']['total_tracks']
                current = self.sp.current_playback()['item']['track_number']
                #text_surface = font.render(f'{current} / {total}', 
                #    True, (255, 255, 255))  # White text   
                text_surface =  self.render(f'{current} / {total}', font)
                self.screen.blit(text_surface, (10, 180))
            #else:
            #    self.clear_screen()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
        
        # Blit the text at 10, 0
        
    def clear_screen(self):
        self.display_image(self.current_image)

    def display_fade(self):
        if self.led.value > 0:
            for i in reversed(range(20)):
                self.led.value = i / 20
                pygame.time.wait(100)

    def render(self, text, font, gfcolor=(0,0,0), ocolor=(255, 255, 255), opx=2):
        textsurface = font.render(text, True, gfcolor).convert_alpha()
        w = textsurface.get_width() + 2 * opx
        h = font.get_height()

        osurf = pygame.Surface((w, h + 2 * opx)).convert_alpha()
        osurf.fill((0, 0, 0, 0))

        surf = osurf.copy()

        osurf.blit(font.render(text, True, ocolor).convert_alpha(), (0, 0))

        for dx, dy in self._circlepoints(opx):
            surf.blit(osurf, (dx + opx, dy + opx))

        surf.blit(textsurface, (opx, opx))
        return surf

    
    def _circlepoints(self, r):
        r = int(round(r))
        if r in self._circle_cache:
            return self._circle_cache[r]
        x, y, e = r, 0, 1 - r
        self._circle_cache[r] = points = []
        while x >= y:
            points.append((x, y))
            y += 1
            if e < 0:
                e += 2 * y - 1
            else:
                x -= 1
                e += 2 * (y - x) - 1
        points += [(y, x) for x, y in points if x > y]
        points += [(-x, y) for x, y in points if x]
        points += [(x, -y) for x, y in points if y]
        points.sort()
        return points

    
        





