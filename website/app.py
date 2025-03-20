from flask import Flask, render_template, request, send_file, jsonify
import os
from yt_dlp import YoutubeDL
from pytube import YouTube  # Fallback library
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


# Function to download YouTube video using yt-dlp
def download_youtube_video_ytdlp(url, quality):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(TEMP_FOLDER, '%(title)s.%(ext)s'),
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'no_check_certificate': True,  # Bypass SSL certificate verification
            'force_generic_extractor': True,  # Handle YouTube Shorts
            'quiet': True,  # Suppress logs
            'no_warnings': True,  # Suppress warnings
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found at: {file_path}")
            return file_path
    except Exception as e:
        logging.error(f"yt-dlp failed: {e}")
        raise Exception(f"yt-dlp failed: {str(e)}")


# Function to download YouTube video using pytube (fallback)
def download_youtube_video_pytube(url, quality):
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(res=quality, file_extension="mp4").first()
        if not stream:
            stream = yt.streams.get_highest_resolution()
        file_path = stream.download(output_path=TEMP_FOLDER)
        return file_path
    except Exception as e:
        logging.error(f"pytube failed: {e}")
        raise Exception(f"pytube failed: {str(e)}")


# Main function to download YouTube video
def download_youtube_video(url, quality):
    try:
        # Try yt-dlp first
        return download_youtube_video_ytdlp(url, quality)
    except Exception as ytdlp_error:
        logging.warning(f"yt-dlp failed, trying pytube: {ytdlp_error}")
        try:
            # Fallback to pytube if yt-dlp fails
            return download_youtube_video_pytube(url, quality)
        except Exception as pytube_error:
            logging.error(f"Both yt-dlp and pytube failed: {pytube_error}")
            raise Exception("Failed to download video using both yt-dlp and pytube.")


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
    app.run(host="0.0.0.0", port=5000, debug=False)