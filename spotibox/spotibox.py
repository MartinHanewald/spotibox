"""Main module."""
from gpiozero import LED, Button
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
        #pygame.font.init()
        pygame.mouse.set_visible(False)
        self.displaysize = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        self.screen = pygame.display.set_mode(self.displaysize, pygame.FULLSCREEN)
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
        
        self.target_id = next(d['id'] for d in devs['devices'] if d['name'] == target)

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
            self.sp.start_playback(
                device_id = self.target_id,
                context_uri=uid
            )
            self.sp.volume(50)
            self.display_image(
                self.get_image(uid)
            )
            self.display_track_number()
            self.display_volume()
            self.reset_timer()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')

    def pause_resume(self):
        try:
            if self.sp.current_playback()["is_playing"]:
                self.pause()
            else:
                self.resume()
            self.reset_timer()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
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
        try:
            current_vol = self.sp.current_playback()['device']['volume_percent']
            newvol = max(0, current_vol + 10)
            print(f'Setting volume to {newvol}')
            self.sp.volume(newvol)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
        self.reset_timer()
        self.display_volume()

    def volume_down(self):
        try:
            current_vol = self.sp.current_playback()['device']['volume_percent']
            newvol = max(0, current_vol - 10)
            print(f'Setting volume to {newvol}')
            self.sp.volume(newvol)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
        self.reset_timer()
        self.display_volume()

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
            if not os.path.isfile(f'assets/{filename}'):
                r = requests.get(fileurl, allow_redirects=True)
                open(f'assets/{filename}', 'wb').write(r.content)
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            sleep(2)
            return self.get_image(uid)   
        return filename
    
    def shutdown(self):
        print('Shutting down...')
        pygame.display.quit()
        os.system(f'sudo shutdown -f now')

    def display_image(self, filename):       
        Image.open(f"./assets/{filename}").save("./assets/temp.bmp")
        picture = pygame.image.load("assets/temp.bmp")
        #picture = pygame.image.load(f'assets/{filename}')
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
        BUTTONPLAY4 = 5
        BUTTONPLAY5 = 6
        BUTTONPLAY6 = 13
        BUTTONVOLUP = 14 # Temporary until Diode setup
        BUTTONVOLDOWN = 15
        BUTTONPAUSE= 26
        BUTTONNEXT = 12


        self.led = LED(LEDPIN)

        
        buttonplay1 = Button(BUTTONPLAY1)
        buttonplay1.when_pressed = lambda: self.playback(albums.album1)

        buttonplay2 = Button(BUTTONPLAY2)
        buttonplay2.when_pressed = lambda: self.playback(albums.album2)

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

        buttonpause = Button(BUTTONPAUSE, pull_up = True, hold_time=3, active_state=None)
        buttonpause.when_pressed = self.pause_resume
        buttonpause.when_held = self.shutdown

        buttonvolup = Button(BUTTONVOLUP)
        buttonvolup.when_pressed = self.volume_up

        buttonvoldown = Button(BUTTONVOLDOWN)
        buttonvoldown.when_pressed = self.volume_down

        self.reset_timer()      

        while True:
            timediff = time() - self.timer
            if timediff > 300:
                try:
                    if not self.sp.current_playback()["is_playing"]:
                        self.shutdown()
                except ReadTimeout:
                    print('API not reachable, trying again in 2 secs')
                except TypeError:
                    self.shutdown()
                    
            if timediff > 30:
                self.display_fade()
            
            pygame.display.update()
            self.fps.tick(30)

    def display_track_number(self):
        try:
            playback = self.sp.current_playback()
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            return
        
        if playback["is_playing"]:
                total = playback['item']['album']['total_tracks']
                current = playback['item']['track_number']
                self.remove_boxes('left')
                self.draw_boxes(total, current, 'left')
            #else:
            #    self.clear_screen()
        # Blit the text at 10, 0
    
    def display_volume(self):
        try:
            current_vol = self.sp.current_playback()['device']['volume_percent']
        except ReadTimeout:
            print('API not reachable, trying again in 2 secs')
            return 
        self.remove_boxes('right')
        self.draw_boxes(10, int(current_vol/10), 'right')     
        
    def clear_screen(self):
        self.screen.fill((0, 0, 0))
        self.display_image(self.current_image)

    
    def display_fade(self):
        
        if self.led.value > 0:
            self.led.off()
            # for i in reversed(range(20)):
            #     self.led.value = i / 20
            #     self.fps.tick(100)


    def draw_boxes(self, n, active, side = 'left'):

        BASE = (50, 50, 50)
        ACTIVE = (150, 100, 250)

        X = 10 if side == 'left' else 290
        screen_h = 240
        box = screen_h / n
        margin = max(int(.1 * box),1)
        h = box - 2 * margin

        for k in range(n):
                color = BASE if k >= active else ACTIVE
                pygame.draw.rect(self.screen, color, 
                        (X, screen_h - h - margin - box * k,20,h))

    def remove_boxes(self, side = 'left'):
        X = 10 if side == 'left' else 290
        color = (0, 0, 0)
        pygame.draw.rect(self.screen, color, 
                        (X, 0, 20, 240)) 


    
        





