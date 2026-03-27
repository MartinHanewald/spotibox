"""Console script for spotibox."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Load .env from the current directory (if it exists) so that
# SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI
# are available as environment variables for Click's envvar lookup.
load_dotenv(Path.cwd() / ".env")


@click.command()
@click.option(
    "--client-id",
    envvar="SPOTIPY_CLIENT_ID",
    prompt="Spotify Client ID",
    help="Spotify application client ID (env: SPOTIPY_CLIENT_ID).",
)
@click.option(
    "--client-secret",
    envvar="SPOTIPY_CLIENT_SECRET",
    prompt="Spotify Client Secret",
    help="Spotify application client secret (env: SPOTIPY_CLIENT_SECRET).",
)
@click.option(
    "--redirect-uri",
    envvar="SPOTIPY_REDIRECT_URI",
    prompt="Redirect URI",
    help="OAuth redirect URI (env: SPOTIPY_REDIRECT_URI).",
)
@click.option("--debug", is_flag=True, help="Skip GPIO setup (for development).")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose (DEBUG) logging.")
def main(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    debug: bool,
    verbose: bool,
) -> None:
    """Spotibox — Spotify player for kids with GPIO controls."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from spotibox.spotibox import Spotibox

    box = Spotibox(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        debug=debug,
    )
    box.run()


if __name__ == "__main__":
    sys.exit(main())
