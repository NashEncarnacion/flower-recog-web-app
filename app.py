"""
Flower Recognition Web App
==========================
Flask application that:
  1. Accepts JPG / PNG uploads.
  2. Classifies each image with a pretrained flower model (PlantNet API).
  3. Posts the images to a Facebook Page via the Graph API.
"""

import io
import os
import uuid
import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

# ── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App config ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/classify", methods=["POST"])
def classify():
    """Handle image upload, classify, and optionally post to Facebook."""
    if "images" not in request.files:
        flash("No files selected.", "error")
        return redirect(url_for("index"))

    files = request.files.getlist("images")
    if not files or files[0].filename == "":
        flash("No files selected.", "error")
        return redirect(url_for("index"))

    results = []
    post_to_fb = request.form.get("post_to_facebook") == "on"
    location = request.form.get("location", "").strip() or None

    from model.classifier import top_prediction
    from utils.facebook import post_photos_to_page
    from utils.cloudinary_storage import is_configured as cloudinary_configured
    from utils.cloudinary_storage import upload_image as cloudinary_upload

    use_cloudinary = cloudinary_configured()

    # Lists for successfully classified images
    image_paths = []      # paths to classified images
    result_indices = []   # indices into `results` that correspond to image_paths

    for file in files:
        if not allowed_file(file.filename):
            flash(f"'{file.filename}' is not a supported format (JPG/PNG).", "warning")
            continue

        # Save locally — needed for classification and FB upload
        unique_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        save_path = UPLOAD_FOLDER / unique_name
        file.save(save_path)

        # Classify
        try:
            prediction = top_prediction(save_path)
        except Exception as exc:
            logger.exception("Classification failed for %s", unique_name)
            save_path.unlink(missing_ok=True)
            results.append({"filename": file.filename, "error": f"Classification error: {exc}"})
            continue

        label = prediction["label"]
        confidence = prediction["percent"]
        low_confidence = prediction.get("low_confidence", False)
        common_name = prediction.get("common_name")
        scientific_name = prediction.get("scientific_name", "Unknown")

        idx = len(results)
        results.append(
            {
                "filename": file.filename,
                "image_url": None,
                "image_local": save_path.name,
                "label": label,
                "confidence": confidence,
                "low_confidence": low_confidence,
                "common_name": common_name,
                "scientific_name": scientific_name,
                "fb_post_id": None,
                "fb_post_url": None,
                "fb_error": None,
                # internal — removed before render
                "_save_path": save_path,
            }
        )
        image_paths.append(save_path)
        result_indices.append(idx)

    if not results:
        flash("No valid images were processed.", "error")
        return redirect(url_for("index"))

    # ── Facebook multi-photo post (single post for all images) ───────────────
    if post_to_fb and image_paths:
        # Build main caption with location
        caption_lines = []
        if location:
            caption_lines.append(f"📍: {location}")
        
        # If single image, add flower details to main caption
        if len(image_paths) == 1:
            r = results[result_indices[0]]
            flower_line = "🌼: "
            if r["common_name"]:
                flower_line += f"{r['common_name']} ({r['scientific_name']})"
            else:
                flower_line += r['scientific_name']
            caption_lines.append(flower_line)
            main_caption = "\n".join(caption_lines) if caption_lines else ""
            photo_captions = None
        else:
            # Multiple images: flower details go in photo subcaptions
            main_caption = "\n".join(caption_lines) if caption_lines else ""
            photo_captions = []
            for i in result_indices:
                r = results[i]
                flower_line = "🌼: "
                if r["common_name"]:
                    flower_line += f"{r['common_name']} ({r['scientific_name']})"
                else:
                    flower_line += r['scientific_name']
                photo_captions.append(flower_line)

        fb_post_id = None
        fb_post_url = None
        fb_error = None
        try:
            fb_result = post_photos_to_page(
                image_paths, 
                main_caption, 
                photo_captions=photo_captions
            )
            fb_post_id = fb_result.get("id")
            if fb_post_id:
                fb_post_url = f"https://www.facebook.com/{fb_post_id}"
        except Exception as exc:
            logger.exception("Facebook multi-photo upload failed")
            fb_error = str(exc)

        for i in result_indices:
            results[i]["fb_post_id"] = fb_post_id
            results[i]["fb_post_url"] = fb_post_url
            results[i]["fb_error"] = fb_error

    # ── Cloudinary upload + local cleanup ────────────────────────────────────
    for i in result_indices:
        r = results[i]
        save_path = r.pop("_save_path")

        if use_cloudinary:
            try:
                r["image_url"] = cloudinary_upload(save_path, folder="flower-recog")
                save_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.exception("Cloudinary upload failed for %s", r["filename"])

    return render_template("result.html", results=results, post_to_fb=post_to_fb)


@app.route("/api/classify", methods=["POST"])
def api_classify():
    """JSON API endpoint — same logic as /classify but returns JSON."""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided."}), 400

    file = request.files["image"]
    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Use JPG or PNG."}), 400

    unique_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    save_path = UPLOAD_FOLDER / unique_name
    file.save(save_path)

    from model.classifier import classify_image

    try:
        predictions = classify_image(save_path)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(
        {
            "filename": file.filename,
            "predictions": predictions,
        }
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
