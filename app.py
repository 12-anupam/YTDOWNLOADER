from flask import Flask, render_template, request, send_file, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from yt_dlp import YoutubeDL
import os
import logging
import re
import json

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Set a secret key for session management
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')

# Temporary folder to store downloaded files
TEMP_FOLDER = os.path.join(os.getcwd(), "temp_downloads")
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

# Google OAuth configuration
GOOGLE_CLIENT_SECRETS_FILE = "client_secret.json"  # Path to your OAuth client secrets JSON file
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
REDIRECT_URI = "https://your-app-name.onrender.com/callback"  # Update with your Render URL

# Initialize the OAuth flow
flow = Flow.from_client_secrets_file(
    GOOGLE_CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)

# Function to sanitize file names
def sanitize_filename(filename):
    sanitized = re.sub(r'[\\/*?:"<>|#]', "_", filename)  # Replace invalid characters with underscores
    sanitized = sanitized.replace(" ", "_")  # Replace spaces with underscores
    return sanitized

# Function to download YouTube video
def download_youtube_video(url, quality, credentials):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(TEMP_FOLDER, '%(title)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'cookiefile': 'cookies.txt',  # Use cookies for authentication
            'no_check_certificate': True,  # Bypass SSL certificate verification
            'force_generic_extractor': True,  # Handle YouTube Shorts
        }

        # Save credentials to cookies.txt
        with open('cookies.txt', 'w') as f:
            json.dump(credentials, f)

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            logging.debug(f"File downloaded successfully: {file_path}")
            if not os.path.exists(file_path):
                logging.error(f"File not found at: {file_path}")
                raise FileNotFoundError(f"File not found at: {file_path}")
            return file_path
    except Exception as e:
        logging.error(f"Error downloading YouTube video: {e}")
        raise

# Route for Google OAuth login
@app.route("/login")
def login():
    auth_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state
    return redirect(auth_url)

# Route for Google OAuth callback
@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)
    session["credentials"] = flow.credentials.to_json()
    return redirect("/")  # Redirect to the home page after login

# Route for the home page
@app.route("/", methods=["GET", "POST"])
def index():
    # Check if the user is logged in
    if "credentials" not in session:
        return redirect("/login")  # Redirect to login if not authenticated

    if request.method == "POST":
        platform = request.form.get("platform")
        url = request.form.get("url")
        quality = request.form.get("quality")

        try:
            if platform == "youtube":
                # Get user credentials from the session
                credentials = json.loads(session["credentials"])
                file_path = download_youtube_video(url, quality, credentials)
            else:
                return jsonify({"error": "Invalid platform selected."}), 400

            # Sanitize the file name
            file_name = os.path.basename(file_path)
            sanitized_file_name = sanitize_filename(file_name)
            sanitized_file_path = os.path.join(TEMP_FOLDER, sanitized_file_name)

            # Rename the file to the sanitized name
            os.rename(file_path, sanitized_file_path)

            logging.debug(f"Sanitized file name: {sanitized_file_name}")
            return jsonify({"success": True, "file_name": sanitized_file_name})
        except Exception as e:
            logging.error(f"Error in index route: {e}")
            return jsonify({"error": str(e)}), 500

    return render_template("index.html")

# Route for downloading files
@app.route("/download/<file_name>")
def download_file(file_name):
    file_path = os.path.join(TEMP_FOLDER, file_name)
    logging.debug(f"Attempting to download file: {file_path}")
    if os.path.exists(file_path):
        try:
            # Send the file for download
            response = send_file(file_path, as_attachment=True)
            # Delete the file after sending it
            @response.call_on_close
            def delete_file():
                try:
                    os.remove(file_path)
                    logging.debug(f"File deleted: {file_path}")
                except Exception as e:
                    logging.error(f"Error deleting file: {e}")
            return response
        except Exception as e:
            logging.error(f"Error serving file: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        logging.error(f"File not found: {file_path}")
        return "File not found.", 404

if __name__ == "__main__":
    app.run(debug=False)  # Debug mode is now disabled
