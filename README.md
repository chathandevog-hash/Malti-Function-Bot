# Multifunctional Bot (Rename + Thumbnail) - Render Deploy

## Features
- /start welcome message
- Auto thumbnail save (send photo)
- /deletetub delete thumbnail
- Rename document/video
- Choose output format (Document/Video)
- Progress style bar
- Flask web server for Render + UptimeRobot

## Deploy on Render
1. Create Web Service from this repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `python app.py`
4. Add env vars: API_ID, API_HASH, BOT_TOKEN

## UptimeRobot
Monitor URL:
- `https://YOUR-RENDER-URL/health`
