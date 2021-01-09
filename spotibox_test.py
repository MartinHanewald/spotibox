from spotibox.spotibox import Spotibox
from spotibox import albums
from spotipy.exceptions import SpotifyException

box = Spotibox(
    client_id="42e5b03bb466427bbdd2e328ba0260be",
    client_secret="1d45cee916fc489ab0cce264f0b215e4",
    redirect_uri='https://example.com/callback/'
    )



box.playback(albums.album1)
box.next_track()
box.pause_resume()
box.volume_down()
box.volume_up()
box.pause()
box.resume()
box.buttonconfig()

box.sp.current_playback()["is_playing"]





try:
    current = box.sp.current_playback()
    box.sp.pause_playback()
    print('Playback paused.')
except SpotifyException as err:
    print(err.msg)

box.sp.start_playback(device_id = current['device']['id'],
                      context_uri = current['context']['uri'],
                      offset={'uri':current['item']['uri']},
                      position_ms=current['progress_ms'])

current['context']
