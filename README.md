# HubCloud Link Extractor

A simple Flask web app that extracts direct download links, server mirrors, and an HBPlay player URL from a HubCloud drive page.

## Features

- Clean dark UI
- Extracts:
  - FSL / Cloudflare R2
  - GPDL 10 Gbps server
  - Pixel 10 Gbps server
  - Pixeldrain
  - Watch Online (HBPlay)
  - Direct Googleusercontent download (when available)
  - Generated HBPlay player link
- One-click "Copy All Links" / "Copy with Labels"
- JSON API endpoint (`POST /api`)

## Local run

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deploy to Heroku

### 1. Create a GitHub repo

```bash
cd hubcloud-extractor
git init
git add .
git commit -m "Initial commit: HubCloud Link Extractor"
# Create a new empty repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/hubcloud-extractor.git
git branch -M main
git push -u origin main
```

### 2. Deploy with Heroku CLI

```bash
# Login (one-time)
heroku login

# Create app
heroku create your-app-name

# Deploy
git push heroku main

# Open the app
heroku open
```

### 3. Or use Heroku Dashboard + GitHub

1. Go to [dashboard.heroku.com](https://dashboard.heroku.com)
2. **New** → **Create new app**
3. Connect to GitHub → select this repository
4. Enable **Automatic Deploys** (optional)
5. Click **Deploy Branch**

## API usage

```bash
curl -X POST https://your-app-name.herokuapp.com/api \
  -H "Content-Type: application/json" \
  -d '{"hub_url": "https://hubcloud.ist/drive/xxxxxxxx"}'
```

Response example:

```json
{
  "success": true,
  "links": [
    {"name": "Server 10Gbps (pixel)", "url": "https://pixel.hubcloud.ist/?id=..."},
    {"name": "Direct Googleusercontent Download", "url": "https://video-downloads.googleusercontent.com/..."},
    {"name": "HBPlay Player Link", "url": "https://hbplay.pages.dev/?u=..."}
  ]
}
```

## Notes

- The app makes outbound requests to HubCloud / Google servers. Heroku free dynos have network access.
- Timeouts are set reasonably high (60 s) because some intermediate pages can be slow.
- Not affiliated with HubCloud. Use at your own responsibility and respect the site's terms.
