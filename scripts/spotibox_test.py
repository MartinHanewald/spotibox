from spotibox.spotibox import Spotibox
from spotibox.spotibox import albums
import asyncio
box = Spotibox(client_id='42e5b03bb466427bbdd2e328ba0260be',
    client_secret='1d45cee916fc489ab0cce264f0b215e4',
    redirect_uri='https://example.com/callback/',
    debug=True)

box.playback(albums.album1)
box.pause()


box.sp.current_playback()['item']['album']['total_tracks']
box.sp.current_playback()['item']['track_number']

if 'playlist' in albums.album1:
    print('Playlist')