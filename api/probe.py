"""Temporary preview-only network probe; no bot token or stored state."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        results = []
        for query in ("Winx", "Винкс"):
            url = "https://www.avito.ru/rossiya?" + urlencode({"q": query, "s": 104})
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ru-RU,ru;q=0.9"})
                with urlopen(req, timeout=20) as response:
                    document = response.read(8_000_000).decode("utf-8", errors="replace")
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(document, "html.parser")
                    cards = soup.select('[data-marker="item"]')
                    script_info = [{"id": s.get("id"), "type": s.get("type"), "bytes": len(s.get_text())}
                                   for s in soup.find_all("script") if s.get("id") or s.get("type") == "application/ld+json"]
                    for element in soup.select('script, style, noscript'):
                        element.decompose()
                    text = soup.get_text(" ", strip=True)
                    results.append({"query": query, "status": response.status, "cards": len(cards),
                                    "page_title": soup.title.get_text(strip=True) if soup.title else None,
                                    "page_text": text[-1800:], "bytes": len(document),
                                    "final_url": response.geturl(), "script_info": script_info,
                                    "listing_links": len(soup.select('a[data-marker="item-title"]'))})
            except HTTPError as exc:
                results.append({"query": query, "status": exc.code, "cards": 0})
            except (URLError, TimeoutError, OSError):
                results.append({"query": query, "status": "network_error", "cards": 0})
        body = json.dumps({"ready": all(r["status"] == 200 and r["cards"] > 0 for r in results),
                           "results": results}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
