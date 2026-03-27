#!/usr/bin/env python3
"""Authenticate with Spotify and cache the token.

Run this once (on any machine with a browser) to complete the OAuth flow.
The resulting .cache file can then be copied to the Pi if needed.

Usage:
    uv run python scripts/auth.py
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import spotipy
from spotipy.oauth2 import SpotifyOAuth

scope = "user-read-playback-state,user-modify-playback-state"
sp = spotipy.Spotify(client_credentials_manager=SpotifyOAuth(scope=scope))
user = sp.current_user()
print(f"Authenticated as: {user['display_name']} ({user['id']})")
print(f"Token cached in .cache")
