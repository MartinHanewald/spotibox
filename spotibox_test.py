from spotibox.spotibox import Spotibox
from spotibox.spotibox import albums
import asyncio
import json
box = Spotibox(client_id='42e5b03bb466427bbdd2e328ba0260be',
    client_secret='1d45cee916fc489ab0cce264f0b215e4',
    redirect_uri='https://example.com/callback/',
    debug=True)

box.playback(albums.album1))
box.pause()


with open('playlist.json', 'w') as file:
    json.dump(playlist, file, indent=2)
    # file.write(json.dumps())

playback = box.sp.current_playback()
with open('playback.json', 'w') as file:
    json.dump(playback, file, indent=2)
    # file.write(json.dumps())

playback['context']['uri']

pl_tracks = [i['track']['uri'] for i in playlist['tracks']['items']]
pb_track = playback['item']['uri']
total = len(pl_tracks)
current = pl_tracks.index(pb_track) + 1



playlist['tracks']['items'][0]['track']['uri']


box.sp.current_playback()['item']['album']['total_tracks']
box.sp.current_playback()['item']['track_number']

if 'playlist' in albums.album1:
    print('Playlist')