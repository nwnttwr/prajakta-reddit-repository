import os
import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
import yt_dlp


# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHAT_ID = "-1003907685039"

REDDIT_RSS = "https://www.reddit.com/r/Prajakta_fans/.rss"

STATE_FILE = "state.json"

# ONLY these formats are allowed
ALLOWED_EXTENSIONS = {
    ".jpg",
    ".png",
    ".gif",
    ".mp4",
}

MAX_PHOTO_SIZE = 10 * 1024 * 1024 # 10 MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024 # 50 MB


# =========================
# TELEGRAM
# =========================

def telegram_request(method, data=None, files=None):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    response = requests.post(
        url,
        data=data,
        files=files,
        timeout=120
    )

    try:
        result = response.json()
    except Exception:
        print("Telegram returned invalid response:")
        print(response.text)
        return False

    if not result.get("ok"):
        print("Telegram error:")
        print(result)

        return False

    return True


def send_photo(file_path):

    file_size = os.path.getsize(file_path)

    if file_size > MAX_PHOTO_SIZE:
        print(f"Skipping photo > 10 MB: {file_path}")
        return False

    with open(file_path, "rb") as photo:

        return telegram_request(
            "sendPhoto",
            data={
                "chat_id": CHAT_ID
            },
            files={
                "photo": (
                    Path(file_path).name,
                    photo,
                    "image/jpeg"
                )
            }
        )


def send_png(file_path):

    file_size = os.path.getsize(file_path)

    if file_size > MAX_PHOTO_SIZE:
        print(f"Skipping PNG > 10 MB: {file_path}")
        return False

    with open(file_path, "rb") as photo:

        return telegram_request(
            "sendPhoto",
            data={
                "chat_id": CHAT_ID
            },
            files={
                "photo": (
                    Path(file_path).name,
                    photo,
                    "image/png"
                )
            }
        )


def send_gif(file_path):

    file_size = os.path.getsize(file_path)

    if file_size > MAX_VIDEO_SIZE:
        print(f"Skipping GIF > 50 MB: {file_path}")
        return False

    with open(file_path, "rb") as gif:

        return telegram_request(
            "sendAnimation",
            data={
                "chat_id": CHAT_ID
            },
            files={
                "animation": (
                    Path(file_path).name,
                    gif,
                    "image/gif"
                )
            }
        )


def send_video(file_path):

    file_size = os.path.getsize(file_path)

    if file_size > MAX_VIDEO_SIZE:
        print(f"Skipping MP4 > 50 MB: {file_path}")
        return False

    with open(file_path, "rb") as video:

        return telegram_request(
            "sendVideo",
            data={
                "chat_id": CHAT_ID,
                "supports_streaming": "true"
            },
            files={
                "video": (
                    Path(file_path).name,
                    video,
                    "video/mp4"
                )
            }
        )


# =========================
# FILE CHECKING
# =========================

def allowed_extension(file_path):

    extension = Path(file_path).suffix.lower()

    return extension in ALLOWED_EXTENSIONS


def detect_real_file_type(file_path):

    """
    Check the actual file signature.
    This prevents unsupported files being sent
    just because their filename has an allowed extension.
    """

    with open(file_path, "rb") as f:

        header = f.read(32)

    # JPG
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    # PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"

    # GIF
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return ".gif"

    # MP4 / ISO Base Media
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".mp4"

    return None


def send_allowed_file(file_path):

    extension = Path(file_path).suffix.lower()

    # First check filename
    if extension not in ALLOWED_EXTENSIONS:

        print(f"Unsupported extension. Skipping: {file_path}")

        return False

    # Then check actual file type
    real_type = detect_real_file_type(file_path)

    if real_type is None:

        print(f"Unknown/unsupported file type. Skipping: {file_path}")

        return False

    # JPG
    if extension == ".jpg" and real_type == ".jpg":

        return send_photo(file_path)

    # PNG
    if extension == ".png" and real_type == ".png":

        return send_png(file_path)

    # GIF
    if extension == ".gif" and real_type == ".gif":

        return send_gif(file_path)

    # MP4
    if extension == ".mp4" and real_type == ".mp4":

        return send_video(file_path)

    print(
        f"Extension/type mismatch. "
        f"Extension={extension}, real={real_type}"
    )

    return False


# =========================
# STATE
# =========================

def load_state():

    if not os.path.exists(STATE_FILE):

        return []

    try:

        with open(STATE_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except Exception:

        return []


def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as f:

        json.dump(
            state[-500:],
            f,
            indent=2
        )


# =========================
# DOWNLOAD REDDIT VIDEO
# =========================

def download_reddit_video(post_url, output_directory):

    print("Trying to download Reddit video:")
    print(post_url)

    output_template = os.path.join(
        output_directory,
        "reddit_video.%(ext)s"
    )

    options = {

        # MP4 output
        "format":
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/"
            "best",

        "outtmpl": output_template,

        # Merge audio/video into MP4
        "merge_output_format": "mp4",

        "quiet": True,

        "no_warnings": True,

        "noplaylist": True,

        "max_filesize": MAX_VIDEO_SIZE,

    }

    try:

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                post_url,
                download=True
            )

            requested = ydl.prepare_filename(info)

        # yt-dlp may create a .mp4 after merging
        possible_files = list(
            Path(output_directory).glob("*")
        )

        for file_path in possible_files:

            if file_path.suffix.lower() == ".mp4":

                print(f"Downloaded MP4: {file_path}")

                return str(file_path)

        # Sometimes prepare_filename points to original file
        if os.path.exists(requested):

            if Path(requested).suffix.lower() == ".mp4":

                return requested

    except Exception as e:

        print("Video download failed:")
        print(e)

    return None


# =========================
# FIND IMAGE URLS
# =========================

def get_image_urls(entry):

    urls = []

    # --------------------------------
    # RSS media content
    # --------------------------------

    media_content = entry.get("media_content", [])

    for media in media_content:

        url = media.get("url")

        if url:

            urls.append(url)

    # --------------------------------
    # RSS enclosure
    # --------------------------------

    enclosures = entry.get("enclosures", [])

    for enclosure in enclosures:

        url = enclosure.get("href") or enclosure.get("url")

        if url:

            urls.append(url)

    # --------------------------------
    # HTML description
    # --------------------------------

    description = entry.get(
        "description",
        ""
    )

    soup = BeautifulSoup(
        description,
        "html.parser"
    )

    for img in soup.find_all("img"):

        src = img.get("src")

        if src:

            urls.append(src)

    # --------------------------------
    # Remove duplicates
    # --------------------------------

    unique_urls = []

    for url in urls:

        if url not in unique_urls:

            unique_urls.append(url)

    return unique_urls


# =========================
# DOWNLOAD IMAGE
# =========================

def download_image(
    image_url,
    output_directory,
    number
):

    parsed = urlparse(image_url)

    extension = Path(
        parsed.path
    ).suffix.lower()

    # STRICT FORMAT CHECK
    if extension not in {
        ".jpg",
        ".png",
        ".gif"
    }:

        print(
            f"Skipping non JPG/PNG/GIF URL: {image_url}"
        )

        return None

    filename = (
        f"image_{number}"
        f"{extension}"
    )

    file_path = os.path.join(
        output_directory,
        filename
    )

    try:

        headers = {
            "User-Agent":
                "Mozilla/5.0 RedditTelegramBot/1.0"
        }

        response = requests.get(
            image_url,
            headers=headers,
            timeout=60
        )

        response.raise_for_status()

        with open(file_path, "wb") as f:

            f.write(response.content)

        # Check real file
        real_type = detect_real_file_type(
            file_path
        )

        if real_type != extension:

            print(
                f"File type mismatch: "
                f"{extension} vs {real_type}"
            )

            os.remove(file_path)

            return None

        # Size check
        if os.path.getsize(file_path) > MAX_PHOTO_SIZE:

            print(
                f"Skipping image > 10 MB: "
                f"{file_path}"
            )

            os.remove(file_path)

            return None

        return file_path

    except Exception as e:

        print(
            f"Image download failed: {e}"
        )

        if os.path.exists(file_path):

            os.remove(file_path)

        return None


# =========================
# PROCESS ONE REDDIT POST
# =========================

def process_post(entry):

    post_id = entry.get("id")

    post_url = entry.get("link")

    if not post_id:

        return False

    if not post_url:

        return False

    print()
    print("============================")
    print("Processing Reddit post:")
    print(post_url)
    print("============================")

    with tempfile.TemporaryDirectory() as temp_dir:

        # ==================================
        # FIRST: Try Reddit video
        # ==================================

        downloaded_video = download_reddit_video(
            post_url,
            temp_dir
        )

        if downloaded_video:

            if send_allowed_file(
                downloaded_video
            ):

                print("MP4 video sent.")

                return True

            return False

        # ==================================
        # SECOND: Images / GIFs
        # ==================================

        image_urls = get_image_urls(entry)

        if not image_urls:

            print(
                "No JPG/PNG/GIF media found."
            )

            # Text-only post = do nothing
            return False

        sent_any = False

        image_number = 1

        for image_url in image_urls:

            file_path = download_image(
                image_url,
                temp_dir,
                image_number
            )

            if not file_path:

                continue

            if send_allowed_file(
                file_path
            ):

                sent_any = True

                print(
                    f"Media sent: {file_path}"
                )

            image_number += 1

        return sent_any


# =========================
# MAIN
# =========================

def main():

    print("Starting Reddit → Telegram bot")

    state = load_state()

    print(
        f"Already processed posts: "
        f"{len(state)}"
    )

    # --------------------------------
    # Get Reddit RSS
    # --------------------------------

    headers = {
        "User-Agent":
            "Mozilla/5.0 RedditTelegramBot/1.0"
    }

    response = requests.get(
        REDDIT_RSS,
        headers=headers,
        timeout=60
    )

    response.raise_for_status()

    feed = feedparser.parse(
        response.content
    )

    if not feed.entries:

        print("No Reddit posts found.")

        return

    print(
        f"Reddit posts found: "
        f"{len(feed.entries)}"
    )

    # --------------------------------
    # Process oldest → newest
    # --------------------------------

    entries = list(
        reversed(feed.entries)
    )

    for entry in entries:

        post_id = entry.get("id")

        if not post_id:

            continue

        # Already processed
        if post_id in state:

            continue

        try:

            process_post(entry)

        except Exception as e:

            print(
                f"Error processing post "
                f"{post_id}:"
            )

            print(e)

        # Mark as processed even if it
        # contained unsupported media.
        #
        # This prevents the same unsupported
        # post being checked repeatedly.

        state.append(post_id)

        save_state(state)

    print()
    print("Finished.")


if __name__ == "__main__":

    main()
