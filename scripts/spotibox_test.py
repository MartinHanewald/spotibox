from spotibox.spotibox import Spotibox
from spotibox.spotibox import albums
import asyncio
box = Spotibox(client_id='42e5b03bb466427bbdd2e328ba0260be',
    client_secret='1d45cee916fc489ab0cce264f0b215e4',
    redirect_uri='https://example.com/callback/',
    debug=True)

box.sp.playb

box.display_image(box.get_image(albums.album1))


if 'playlist' in albums.album1:
    print('Playlist')