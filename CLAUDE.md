# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gesture-Controlled Spotify Player for Raspberry Pi. Uses a camera to detect hand gestures (via MediaPipe) and map them to Spotify playback commands (via Spotipy OAuth2). An optional body pose "hologram" visualization can be toggled at runtime.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (never commit it):
```
SPOTIPY_CLIENT_ID=<your_client_id>
SPOTIPY_CLIENT_SECRET=<your_client_secret>
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Running

```bash
python main.py
```

- **Q** — quit
- **H** — toggle hologram (body pose visualization)

Requires Raspberry Pi with `rpicam-vid` or `libcamera-vid` installed, and an active Spotify device to control.

First run opens a browser for Spotify OAuth; token is cached to `.spotify_cache`.

## Architecture

```
main.py  ← entry point, main processing loop
├── camera/capture.py        — MJPEG stream via rpicam-vid subprocess (avoids picamera2)
├── vision/
│   ├── hand_tracker.py      — MediaPipe Hands (1 hand, model_complexity=0 for Pi performance)
│   ├── gesture_classifier.py — Finger-position rules → gesture name
│   └── pose_visualizer.py   — MediaPipe Pose, glowing skeleton, runs every 3rd frame
├── spotify/
│   ├── auth.py              — spotipy OAuth2, reads .env, caches token
│   └── controller.py        — play/pause/next/prev/volume_up/volume_down wrappers
├── ui/overlay.py            — OpenCV text overlay (current gesture, last action)
├── utils/
│   ├── cooldown.py          — 1-second minimum between actions
│   └── gesture_stability.py — 3-frame confirmation before gesture is acted on
└── config/gestures.json     — maps gesture names to Spotify action strings
```

**Data flow:** Camera frame → HandTracker → GestureClassifier → GestureStability (3-frame filter) → Cooldown → gestures.json lookup → SpotifyController

## Key Design Decisions

- **Camera via subprocess**: `rpicam-vid`/`libcamera-vid` is used instead of `picamera2` Python bindings to avoid compatibility issues on Raspberry Pi OS.
- **12 FPS cap + model_complexity=0**: Raspberry Pi CPU constraint; pose visualizer only runs every 3rd frame.
- **Gesture stability filter + cooldown**: Prevents jitter from triggering unintended actions.
- **JSON gesture map** (`config/gestures.json`): Edit this file to remap gestures to actions without touching Python code.

## Gesture–Action Mapping

| Gesture | Action |
|---|---|
| `open_palm` | play |
| `fist` | pause |
| `three_fingers` | next_track |
| `peace` | previous_track |
| `thumbs_up` | volume_up |
| `thumbs_down` | volume_down |

## Python Version

3.12.8 (see `.python-version`)
