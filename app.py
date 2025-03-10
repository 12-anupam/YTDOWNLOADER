from flask import Flask, render_template, request, send_file, jsonify
import os
from yt_dlp import YoutubeDL
import instaloader
import logging
import re

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Temporary folder to store downloaded files
TEMP_FOLDER = os.path.join(os.getcwd(), "temp_downloads")
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)


# Function to sanitize file names
def sanitize_filename(filename):
    # Remove or replace special characters
    sanitized = re.sub(r'[\\/*?:"<>|#]', "_", filename)  # Replace invalid characters with underscores
    sanitized = sanitized.replace(" ", "_")  # Replace spaces with underscores
    return sanitized


# Function to download YouTube video
def download_youtube_video(url, quality):
    try:
        if quality == "best":
            ydl_opts = {
                'outtmpl': os.path.join(TEMP_FOLDER, '%(title)s.%(ext)s'),
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'cookiesfrombrowser': ('chrome',),
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'keepvideo': True,
                'no_check_certificate': True,  # Bypass SSL certificate verification
                'force_generic_extractor': True,  # Handle YouTube Shorts
            }
        elif quality == "1080":
            ydl_opts = {
                'outtmpl': os.path.join(TEMP_FOLDER, '%(title)s.%(ext)s'),
                'format': 'bestvideo[height<=1080]+bestaudio/best',
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'keepvideo': True,
                'no_check_certificate': True,  # Bypass SSL certificate verification
                'force_generic_extractor': True,  # Handle YouTube Shorts
            }
        else:
            ydl_opts = {
                'outtmpl': os.path.join(TEMP_FOLDER, '%(title)s.%(ext)s'),
                'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'keepvideo': True,
                'no_check_certificate': True,  # Bypass SSL certificate verification
                'force_generic_extractor': True,  # Handle YouTube Shorts
            }

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


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        platform = request.form.get("platform")
        url = request.form.get("url")
        quality = request.form.get("quality")

        try:
            if platform == "youtube":
                file_path = download_youtube_video(url, quality)
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
    app.run(debug=True)
