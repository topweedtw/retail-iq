#!/usr/bin/env python3
"""
Helper script for RetailIQ ingest 任務.
Input: (source_name, source_tier, feed_url, title_blocklist_regex)
Output: fetch RSS → pick up to N relevant entries → save to /raw/<source>/<week>/ with .meta.json

Designed for pre-W2 testing. Real Ingest Agent will replace this.
"""
import os, sys, re, json, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

ROOT = os.path.expanduser(
    "~/Documents/Enchanté/Conversations/0F7F1213-2778-428F-8DB5-5B9CA9BC0728"
)
RAW_DIR = os.path.join(ROOT, "raw")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

def iso_week(dt=None):
    dt = dt or datetime.now(timezone(timedelta(hours=8)))
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"

def sha256_of(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{h}"

def fetch(url: str, timeout=20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

class TextExtractor(HTMLParser):
    """超簡單 HTML→text 提取器, 只取 <p>, <h1-3>, <li>"""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.capture = False
        self.current = []
    def handle_starttag(self, tag, attrs):
        if tag in ("p", "h1", "h2", "h3", "li"):
            self.capture = True
            self.current = []
    def handle_endtag(self, tag):
        if tag in ("p", "h1", "h2", "h3", "li") and self.capture:
            text = "".join(self.current).strip()
            if text: self.parts.append(text)
            self.capture = False
            self.current = []
    def handle_data(self, data):
        if self.capture:
            self.current.append(data)

def extract_text_from_html(html_bytes: bytes, max_chars=8000) -> str:
    try:
        html = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        html = html_bytes.decode("latin-1", errors="replace")
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    text = "\n\n".join(p.parts)
    return text[:max_chars]

def parse_rss(xml_bytes: bytes, max_items=20):
    """Return list of {title, link, pubDate, description} from RSS/Atom."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  XML parse error: {e}", file=sys.stderr)
        return []
    items = []
    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        items.append({"title": title, "link": link, "pubDate": pub, "description": desc})
        if len(items) >= max_items: break
    if items: return items
    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{ns}entry"):
        title = (entry.findtext(f"{ns}title") or "").strip()
        link_el = entry.find(f"{ns}link")
        link = link_el.get("href") if link_el is not None else ""
        pub = (entry.findtext(f"{ns}updated") or entry.findtext(f"{ns}published") or "").strip()
        summary = (entry.findtext(f"{ns}summary") or entry.findtext(f"{ns}content") or "").strip()
        items.append({"title": title, "link": link, "pubDate": pub, "description": summary})
        if len(items) >= max_items: break
    return items

def slugify(s: str, maxlen=60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower())
    s = s.strip("-")[:maxlen]
    return s or "item"

def save_article(source_name: str, source_tier: str, item: dict,
                 allow_url_regex=None, deny_url_regex=None,
                 title_blocklist_regex=None):
    url = item["link"]
    if not url:
        return None, "no URL"
    # URL filters
    if allow_url_regex and not re.search(allow_url_regex, url):
        return None, "url not in allow list"
    if deny_url_regex and re.search(deny_url_regex, url):
        return None, "url matches deny list"
    if title_blocklist_regex and re.search(title_blocklist_regex, item["title"], re.I):
        return None, "title hit blocklist"

    print(f"  → fetching {url[:80]}...")
    try:
        html_bytes = fetch(url)
    except Exception as e:
        return None, f"fetch failed: {e}"

    text = extract_text_from_html(html_bytes)
    if len(text) < 200:
        return None, "extracted text too short"

    week = iso_week()
    folder = os.path.join(RAW_DIR, source_name, week)
    os.makedirs(folder, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    slug = slugify(item["title"])
    basename = f"{slug}_{today}"
    html_path = os.path.join(folder, f"{basename}.html")
    txt_path = os.path.join(folder, f"{basename}.txt")
    meta_path = os.path.join(folder, f"{basename}.meta.json")

    with open(html_path, "wb") as f: f.write(html_bytes)
    with open(txt_path, "w", encoding="utf-8") as f: f.write(text)
    content_hash = sha256_of(text)
    size = len(html_bytes)

    meta = {
        "source_url": url,
        "source_type": source_name,
        "source_tier": source_tier,
        "source_title": item["title"],
        "fetched_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "fetched_by": "pre-w2-crawler-v0",
        "content_hash": content_hash,
        "content_type": "text/html",
        "content_size_bytes": size,
        "http_status": 200,
        "locale": "en-US",
        "related_wiki_pages": [],
        "ingest_status": "pending",
        "ingest_log_ref": None,
        "notes": f"pubDate: {item.get('pubDate','')}; extracted via pre-w2-crawler"
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return basename, None

def process_source(cfg):
    """cfg = {name, tier, feed_url, n, allow, deny, title_block}"""
    name = cfg["name"]
    print(f"\n=== {name} (Tier {cfg['tier']}) ===")
    try:
        xml = fetch(cfg["feed_url"])
    except Exception as e:
        print(f"  ❌ feed fetch failed: {e}")
        return 0, 0
    items = parse_rss(xml)
    print(f"  RSS items parsed: {len(items)}")
    saved = 0
    attempts = 0
    for item in items:
        if saved >= cfg["n"]: break
        attempts += 1
        basename, err = save_article(
            name, cfg["tier"], item,
            allow_url_regex=cfg.get("allow"),
            deny_url_regex=cfg.get("deny"),
            title_blocklist_regex=cfg.get("title_block"),
        )
        if err:
            print(f"  skip: {item['title'][:60]}  ({err})")
        else:
            saved += 1
            print(f"  ✓ saved: {basename}")
    return saved, attempts

# ────────────────────────────────────────────────────────────
# Config per source (matches sources-config.yaml)
# ────────────────────────────────────────────────────────────
TITLE_BLOCK = r"(leak|leaked|rumor|rumour|expected|reportedly|allegedly|may launch|might launch|coming soon|unveiled ahead|analyst predicts|supply chain says|tipster)"

SOURCES = [
    {"name": "six-colors", "tier": "T2", "feed_url": "https://sixcolors.com/feed/", "n": 2},
    {"name": "ars-technica", "tier": "T2", "feed_url": "https://feeds.arstechnica.com/arstechnica/apple", "n": 2},
    {"name": "macstories", "tier": "T2", "feed_url": "https://www.macstories.net/feed/", "n": 2},
    {"name": "petapixel", "tier": "T2", "feed_url": "https://petapixel.com/feed/", "n": 2},
    {"name": "engadget", "tier": "T2", "feed_url": "https://www.engadget.com/rss.xml", "n": 2},
    {"name": "macworld", "tier": "T2", "feed_url": "https://www.macworld.com/feed", "n": 2},
    {"name": "no-film-school", "tier": "T2", "feed_url": "https://nofilmschool.com/rss.xml", "n": 2},
    {"name": "cined", "tier": "T2", "feed_url": "https://www.cined.com/feed/", "n": 2},
    {"name": "macrumors", "tier": "T2-filtered", "feed_url": "https://feeds.macrumors.com/MacRumors-All",
     "allow": r"^https://www\.macrumors\.com/(review|roundup|how-to)/",
     "deny": r"^https://www\.macrumors\.com/(rumors|news)/",
     "title_block": TITLE_BLOCK, "n": 2},
    {"name": "9to5mac", "tier": "T2-filtered", "feed_url": "https://9to5mac.com/feed/",
     "allow": r"^https://9to5mac\.com/category/(review|guides)/",
     "deny": r"^https://9to5mac\.com/category/rumors/",
     "title_block": TITLE_BLOCK, "n": 2},
    {"name": "the-verge", "tier": "T3", "feed_url": "https://www.theverge.com/rss/index.xml", "n": 2},
    {"name": "toms-guide", "tier": "T3", "feed_url": "https://www.tomsguide.com/feeds/all", "n": 2},
]

def main():
    report = []
    for cfg in SOURCES:
        saved, attempts = process_source(cfg)
        report.append((cfg["name"], saved, attempts))
    print("\n\n=== SUMMARY ===")
    for name, saved, attempts in report:
        print(f"  {name:20s}  saved={saved}  attempted={attempts}")

if __name__ == "__main__":
    main()
