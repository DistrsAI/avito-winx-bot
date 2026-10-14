"""Read public Avito search pages; fail closed on blocks or layout changes."""
import argparse
import copy
import html
import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

QUERIES = ("Winx", "Винкс")
STATE = Path("state.json")


def request(url, data=None):
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ru-RU,ru;q=0.9"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=35) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: request failed") from None
    except URLError:
        # Never include a Telegram URL (which contains the secret token).
        raise RuntimeError("Network request failed") from None


def parse_page(document):
    soup = BeautifulSoup(document, "html.parser")
    cards = soup.select('[data-marker="item"]')
    if not cards:
        raise RuntimeError("No listing cards: blocked page, empty search or changed layout")
    items = []
    for card in cards:
        link = card.select_one('a[data-marker="item-title"]')
        if link is None:
            raise RuntimeError("Listing title missing: changed layout")
        url = urljoin("https://www.avito.ru", link.get("href", ""))
        if urlparse(url).hostname not in ("www.avito.ru", "avito.ru"):
            raise RuntimeError("Unexpected listing host")
        match = re.search(r"_(\d+)(?:[/?]|$)", url)
        item_id = card.get("data-item-id") or (match.group(1) if match else None)
        if not item_id:
            raise RuntimeError("Listing ID missing: changed layout")
        title = link.get_text(" ", strip=True)
        price = card.select_one('[data-marker="item-price"]')
        items.append({"id": str(item_id), "title": title, "url": url,
                      "price": price.get_text(" ", strip=True) if price else "Цена не указана"})
    has_next = soup.select_one('[data-marker="pagination-button/nextPage"]') is not None
    return items, has_next


def collect(fetch=request):
    found = {}
    max_pages = int(os.getenv("MAX_PAGES", "100"))
    for query in QUERIES:
        for page in range(1, max_pages + 1):
            url = "https://www.avito.ru/rossiya?" + urlencode({"q": query, "s": 104, "p": page})
            items, has_next = parse_page(fetch(url))
            found.update((item["id"], item) for item in items)
            if not has_next:
                break
            time.sleep(2)
        else:
            raise RuntimeError("Page limit reached; refusing incomplete scan")
    return found


def update_state(state, items):
    updated = copy.deepcopy(state)
    known = set(updated.get("seen", []))
    if not updated.get("initialized"):
        updated.update(initialized=True, seen=sorted(items), pending={})
        return updated
    pending = updated.setdefault("pending", {})
    for item_id, item in items.items():
        if item_id not in known:
            pending[item_id] = item
    updated["seen"] = sorted(known | set(items))
    return updated


def save(state):
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE)


def telegram(item, token, chat_id):
    text = f"{html.escape(item['title'])}\n{html.escape(item['price'])}\n<a href=\"{html.escape(item['url'], quote=True)}\">Открыть на Авито</a>"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    result = json.loads(request(f"https://api.telegram.org/bot{token}/sendMessage",
                                json.dumps(payload).encode()))
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.probe:
        items, _ = parse_page(request("https://www.avito.ru/rossiya?" + urlencode({"q": "Winx", "s": 104})))
        print(f"Avito accessible: {len(items)} matching cards on first page")
        return
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in GitHub Secrets")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    state = update_state(state, collect())
    save(state)  # Persist pending messages even if Telegram fails.
    for item_id, item in list(state["pending"].items()):
        telegram(item, token, chat_id)
        del state["pending"][item_id]
        save(state)
        time.sleep(1)
    print(f"Scan complete; tracked IDs: {len(state['seen'])}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
