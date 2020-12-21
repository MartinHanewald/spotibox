from signal import pause
from spotibox.spotibox import Spotibox
import click


@click.command()
@click.option('--client_id', prompt='Please enter your Client ID:')
@click.option('--client_secret', prompt='Please enter your Client Secret:')
@click.option('--redirect_uri', prompt='Enter Redirect URI:')

def init(client_id, client_secret, redirect_uri):
    s = Spotibox(client_id, client_secret, redirect_uri)
    return s

if __name__ == '__main__':
    s = init()
    pause()