import os
import json
import html
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp


# ============================================================
# SETTINGS
# ============================================================

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHAT_ID = "-1003907685039"

SUBREDDIT = "Prajakta_fans"

STATE_FILE = "state.json"

# ONLY these formats are allowed
ALLOWED_EXTENSIONS = {
    ".jpg",
    ".png",
    ".gif",
    ".mp4",
}

MAX_PHOTO_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 50 * 1024 * 1024

HEADERS = {
    "User-Agent": "RedditTelegramBot/1.0"
}


# ============================================================
# TELEGRAM
# ============================================================

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

    if os.path.getsize(file_path) > MAX_PHOTO_SIZE:
        print("Skipping photo larger than 10 MB")
        return False

    extension = Path(file_path).suffix.lower()

    if extension == ".jpg":
        mime = "image/jpeg"
    elif extension == ".png":
        mime = "image/png"
    else:
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
                    mime
                )
            }
        )


def send_gif(file_path):

    if os.path.getsize(file_path) > MAX_VIDEO_SIZE:
        print("Skipping GIF larger than 50 MB")
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

    if os.path.getsize(file_path) > MAX_VIDEO_SIZE:
        print("Skipping MP4 larger than 50 MB")
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


# ============================================================
# FILE TYPE DETECTION
# ============================================================

def detect_real_file_type(file_path):

    with open(file_path, "rb") as f:
        header = f.read(64)

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

    # Filename must be allowed
    if extension not in ALLOWED_EXTENSIONS:

        print(
            f"SKIPPED unsupported extension: "
            f"{extension}"
        )

        return False

    # Actual file must also be allowed
    real_type = detect_real_file_type(file_path)

    if real_type is None:

        print(
            f"SKIPPED unknown file type: "
            f"{file_path}"
        )

        return False

    # Extension and actual type must match
    if extension != real_type:

        print(
            f"SKIPPED type mismatch: "
            f"{extension} / {real_type}"
        )

        return False

    if extension in [".jpg", ".png"]:
        return send_photo(file_path)

    if extension == ".gif":
        return send_gif(file_path)

    if extension == ".mp4":
        return send_video(file_path)

    return False


# ============================================================
# DOWNLOAD MEDIA
# ============================================================

def download_media(url, output_directory, number):

    url = html.unescape(url)

    extension = Path(
        urlparse(url).path
    ).suffix.lower()

    # STRICT RULE
    if extension not in {
        ".jpg",
        ".png",
        ".gif"
    }:

        print(
            f"Skipping URL because it is not "
            f"JPG/PNG/GIF: {url}"
        )

        return None

    filename = f"media_{number}{extension}"

    file_path = os.path.join(
        output_directory,
        filename
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
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
                f"Skipping because actual type "
                f"is {real_type}"
            )

            os.remove(file_path)

            return None

        if os.path.getsize(file_path) > MAX_PHOTO_SIZE:

            print(
                "Skipping image larger than 10 MB"
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


# ============================================================
# REDDIT VIDEO
# ============================================================

def download_reddit_video(
    permalink,
    output_directory
):

    print("Trying Reddit video:")
    print(permalink)

    output_template = os.path.join(
        output_directory,
        "reddit_video.%(ext)s"
    )

    options = {

        "format":
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]",

        "outtmpl": output_template,

        "merge_output_format": "mp4",

        "quiet": True,

        "no_warnings": True,

        "noplaylist": True,

        "max_filesize": MAX_VIDEO_SIZE,
    }

    try:

        with yt_dlp.YoutubeDL(options) as ydl:

            ydl.download([permalink])

        # Find resulting MP4
        for file_path in Path(
            output_directory
        ).glob("*.mp4"):

            if file_path.stat().st_size > MAX_VIDEO_SIZE:

                print(
                    "Video is larger than 50 MB"
                )

                return None

            return str(file_path)

    except Exception as e:

        print(
            "Reddit video download failed:"
        )

        print(e)

    return None


# ============================================================
# GET REDDIT POSTS
# ============================================================

def get_reddit_posts():

    url = (
        f"https://www.reddit.com/r/"
        f"{SUBREDDIT}/new.json"
        f"?limit=25"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    return data["data"]["children"]


# ============================================================
# GET ORIGINAL GALLERY IMAGES
# ============================================================

def get_gallery_images(post):

    images = []

    gallery_data = post.get(
        "gallery_data"
    )

    media_metadata = post.get(
        "media_metadata"
    )

    if not gallery_data or not media_metadata:
        return images

    for item in gallery_data.get(
        "items",
        []
    ):

        media_id = item.get(
            "media_id"
        )

        if not media_id:
            continue

        metadata = media_metadata.get(
            media_id
        )

        if not metadata:
            continue

        # Reddit's full-size source
        source = metadata.get("s")

        if not source:
            continue

        url = source.get("u")

        if not url:
            continue

        url = html.unescape(url)

        images.append(url)

    return images


# ============================================================
# GET ORIGINAL IMAGE
# ============================================================

def get_single_image(post):

    # Reddit's submitted URL is preferred.
    # DO NOT use the thumbnail.

    url = post.get("url")

    if not url:
        return None

    url = html.unescape(url)

    extension = Path(
        urlparse(url).path
    ).suffix.lower()

    if extension in {
        ".jpg",
        ".png",
        ".gif"
    }:

        return url

    return None


# ============================================================
# PROCESS ONE POST
# ============================================================

def process_post(post):

    data = post["data"]

    post_id = data.get("id")

    permalink = data.get(
        "permalink"
    )

    if not post_id or not permalink:
        return False

    full_permalink = (
        "https://www.reddit.com"
        + permalink
    )

    print()
    print("================================")
    print("Processing:")
    print(full_permalink)
    print("================================")

    with tempfile.TemporaryDirectory() as temp_dir:

        # ------------------------------------------------
        # 1. VIDEO
        # ------------------------------------------------

        if data.get("is_video"):

            video = download_reddit_video(
                full_permalink,
                temp_dir
            )

            if video:

                if send_allowed_file(video):

                    print(
                        "Original MP4 sent."
                    )

                    return True

            print(
                "Video could not be sent."
            )

            return False

        # ------------------------------------------------
        # 2. GALLERY
        # ------------------------------------------------

        gallery_images = get_gallery_images(
            data
        )

        if gallery_images:

            sent_any = False

            number = 1

            for image_url in gallery_images:

                file_path = download_media(
                    image_url,
                    temp_dir,
                    number
                )

                if file_path:

                    if send_allowed_file(
                        file_path
                    ):

                        sent_any = True

                number += 1

            return sent_any

        # ------------------------------------------------
        # 3. SINGLE IMAGE
        # ------------------------------------------------

        image_url = get_single_image(
            data
        )

        if image_url:

            file_path = download_media(
                image_url,
                temp_dir,
                1
            )

            if file_path:

                return send_allowed_file(
                    file_path
                )

        # ------------------------------------------------
        # 4. EVERYTHING ELSE
        # ------------------------------------------------

        print(
            "No allowed media. Skipping."
        )

        return False


# ============================================================
# STATE
# ============================================================

def load_state():

    if not os.path.exists(
        STATE_FILE
    ):

        return []

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return []


def save_state(state):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state[-500:],
            f,
            indent=2
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Starting Reddit → Telegram..."
    )

    state = load_state()

    print(
        f"Already processed: "
        f"{len(state)} posts"
    )

    posts = get_reddit_posts()

    print(
        f"Reddit returned "
        f"{len(posts)} posts"
    )

    # Reddit gives newest first.
    # Reverse so we send older new posts first.
    posts = list(reversed(posts))

    for post in posts:

        data = post["data"]

        post_id = data.get("id")

        if not post_id:
            continue

        # Already processed
        if post_id in state:

            continue

        try:

            process_post(post)

        except Exception as e:

            print(
                f"ERROR processing "
                f"{post_id}:"
            )

            print(e)

        # Mark as processed
        state.append(post_id)

        save_state(state)

    print()
    print("Finished.")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
