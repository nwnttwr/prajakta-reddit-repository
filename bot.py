import os
import json
import html
import requests
import feedparser
from bs4 import BeautifulSoup

RSS_URL = "https://www.reddit.com/r/Prajakta_fans/new/.rss"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "-1003907685039"

STATE_FILE = "state.json"

HEADERS = {
    "User-Agent": "PrajaktaRedditTelegramBot/1.0"
}


def telegram(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    response = requests.post(
        url,
        data=data,
        files=files,
        timeout=60
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise Exception(result)

    return result


def load_state():
    if not os.path.exists(STATE_FILE):
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))
    except Exception:
        return set()


def save_state(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(list(seen)[-200:], file)


def clean_html(value):
    if not value:
        return ""

    soup = BeautifulSoup(value, "html.parser")

    return soup.get_text("\n").strip()


def get_images(entry):
    images = []

    summary = entry.get("summary", "")

    soup = BeautifulSoup(summary, "html.parser")

    for img in soup.find_all("img"):
        url = img.get("src")

        if url:
            images.append(url)

    for media in entry.get("media_content", []):
        if isinstance(media, dict):
            url = media.get("url")

            if url:
                images.append(url)

    return list(dict.fromkeys(images))


def send_photo(url, caption):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        "image/jpeg"
    )

    if "image" not in content_type:
        return False

    telegram(
        "sendPhoto",
        data={
            "chat_id": CHAT_ID,
            "caption": caption[:1024],
            "parse_mode": "HTML"
        },
        files={
            "photo": (
                "reddit.jpg",
                response.content,
                content_type
            )
        }
    )

    return True


def send_text(title, body, author, link):
    message = f"<b>{html.escape(title)}</b>\n\n"

    if body:
        message += html.escape(body[:3500])
        message += "\n\n"

    if author:
        message += f"👤 {html.escape(author)}\n"

    message += "📍 r/Prajakta_fans\n"

    message += (
        f'<a href="{html.escape(link)}">'
        "Original Reddit post</a>"
    )

    telegram(
        "sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
    )


def process_post(entry):
    title = entry.get("title", "Reddit post")
    link = entry.get("link", "")
    author = entry.get("author", "")

    body = clean_html(
        entry.get("summary", "")
    )

    caption = (
        f"<b>{html.escape(title)}</b>\n"
        "📍 r/Prajakta_fans"
    )

    if author:
        caption += f"\n👤 {html.escape(author)}"

    images = get_images(entry)

    for image in images[:10]:
        try:
            if send_photo(image, caption):
                return
        except Exception as error:
            print("Image error:", error)

    send_text(
        title,
        body,
        author,
        link
    )


def main():
    print("Checking r/Prajakta_fans...")

    feed = feedparser.parse(
        RSS_URL,
        request_headers=HEADERS
    )

    if not feed.entries:
        print("No Reddit posts found.")
        return

    seen = load_state()

    entries = list(reversed(feed.entries))

    for entry in entries:
        post_id = (
            entry.get("id")
            or entry.get("link")
        )

        if not post_id:
            continue

        if post_id in seen:
            continue

        print(
            "New post:",
            entry.get("title")
        )

        try:
            process_post(entry)
            seen.add(post_id)

        except Exception as error:
            print("ERROR:", error)

    save_state(seen)


if __name__ == "__main__":
    main()
