# Flower Recognizer Web App

A Flask web application that classifies flower photos using a pretrained AI model and automatically posts labelled images to a Facebook Page via the Graph API.

## Features

- **Upload** JPG / PNG flower photos via drag-and-drop or file browser
- **AI classification** using [`dima806/flowers_image_detection`](https://huggingface.co/dima806/flowers_image_detection) a fine-tuned ViT model covering 102 flower categories (Oxford 102 Flowers)
- **Automatic labelling** the top prediction and confidence score are rendered directly onto each image
- **Facebook auto-post** one click sends the labelled photo to your Facebook Page via the Graph API v19
- **JSON API** endpoint (`POST /api/classify`) for programmatic access

## Project Structure

```
flower-recog-web-app/
 app.py                   # Flask application & routes
 model/
    classifier.py        # HuggingFace model wrapper
 utils/
    facebook.py          # Facebook Graph API helper
 templates/
    index.html           # Upload form
    result.html          # Results page
 static/
    css/style.css
    js/main.js
 uploads/                 # Temporary image storage (git-ignored)
 .env.example             # Environment variable template
 requirements.txt
 README.md
```

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd flower-recog-web-app

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

> **Note:** `torch` and `transformers` will be installed automatically.
> The model weights (~330 MB) are downloaded from HuggingFace on first run and cached in `~/.cache/huggingface/`.

### 2. Configure environment variables

```bash
copy .env.example .env
```

Edit `.env` and fill in:

| Variable               | Description                         |
| ---------------------- | ----------------------------------- |
| `FLASK_SECRET_KEY`     | Any random string used for sessions |
| `FB_PAGE_ID`           | Your Facebook Page's numeric ID     |
| `FB_PAGE_ACCESS_TOKEN` | A Page Access Token (see below)     |

### 3. Run the app

```bash
python app.py
```

Open http://localhost:5000 in your browser.

## Getting a Facebook Page Access Token

### Prerequisites

- You must have a **Facebook Page** that you administer.
  Create one at https://www.facebook.com/pages/create if you don't have one yet.
- You must have a **Facebook Developer account** at https://developers.facebook.com.

### Steps

1. Go to https://developers.facebook.com/ and create an app (type: **Business**).
2. Open **Tools → Graph API Explorer**, select your app.
3. Click **Generate Access Token** and log in with your **personal Facebook account**
   (the account that administers the Page — do _not_ log in as the Page itself).
4. Request these permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`.
5. Run the following query to list pages you manage and retrieve their tokens:
   ```
   GET /me/accounts
   ```
6. Copy the `access_token` and `id` for your Page into `.env`.

> **Token expiry:** Graph API Explorer tokens expire in ~1 hour.
> Exchange for a 60-day token with:
>
> ```
> GET /oauth/access_token
>   ?grant_type=fb_exchange_token
>   &client_id=YOUR_APP_ID
>   &client_secret=YOUR_APP_SECRET
>   &fb_exchange_token=SHORT_LIVED_USER_TOKEN
> ```
>
> Then call `/me/accounts` again with the long-lived user token to get a long-lived Page token.

## JSON API Usage

```bash
curl -X POST http://localhost:5000/api/classify \
     -F "image=@/path/to/rose.jpg"
```

Response:

```json
{
  "filename": "rose.jpg",
  "predictions": [
    { "label": "Rose", "score": 0.972, "percent": "97.2%" },
    { "label": "Hibiscus", "score": 0.015, "percent": "1.5%" }
  ]
}
```

## Requirements

- Python 3.10+
- Internet access (first run only, for model download)
- Facebook Developer account + Page (for the posting feature)

## Tech Stack

| Layer            | Technology                                                     |
| ---------------- | -------------------------------------------------------------- |
| Web framework    | Flask 3                                                        |
| ML model         | HuggingFace Transformers, ViT fine-tuned on Oxford 102 Flowers |
| Image annotation | Pillow                                                         |
| Facebook posting | Graph API v19 via requests                                     |
| Frontend         | Vanilla HTML / CSS / JS (no build step)                        |
