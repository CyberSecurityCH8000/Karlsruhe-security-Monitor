import datetime as dt
import json, pathlib, re, urllib.request, html
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

NOW=dt.datetime.now(dt.timezone.utc)
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"KarlsruheSecurityMonitor/1.0 (+public-information-dashboard)","Accept":"text/html,application/rss+xml,application/xml", "Accept-Language":"de-DE,de;q=0.9", "Cache-Control":"no-cache"})
    with urllib.request.urlopen(req,timeout=25) as res:
        return res.read()

class KVVParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_heading=False; self.parts=[]; self.headings=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("h2","h3"):
            self.in_heading=True;self.parts=[]
    def handle_endtag(self,tag):
        if tag in ("h2","h3") and self.in_heading:
            title=" ".join("".join(self.parts).split())
            if title and title not in ("Aktuelle Verkehrsmeldungen","Verkehrsmeldungen","Detail","Ergebnisse filtern"):
                self.headings.append(title)
            self.in_heading=False
    def handle_data(self,data):
        if self.in_heading:self.parts.append(data)


class PolicePageParser(HTMLParser):
    """Extract article links even if the newsroom changes its link markup."""
    def __init__(self):
        super().__init__()
        self.href = None
        self.parts = []
        self.entries = []
    def handle_starttag(self, tag, attrs):
        if tag != "a": return
        href = dict(attrs).get("href", "")
        if re.search(r"/blaulicht/pm/110972/\d+", href):
            self.href = urljoin("https://www.presseportal.de", href)
            self.parts = []
    def handle_data(self, data):
        if self.href: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            title = " ".join("".join(self.parts).split())
            if title and len(title) > 15:
                self.entries.append({"category":"polizei","title":title[:260],"url":self.href,"published":None})
            self.href = None

def police_fallback():
    page = get("https://www.presseportal.de/blaulicht/nr/110972").decode("utf-8","replace")
    parser = PolicePageParser()
    parser.feed(page)
    # Newsroom article titles are also exposed in structured data on some page versions.
    for script in re.findall(r'<script[^>]+type=["\\\']application/ld\\+json["\\\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try: nodes = json.loads(html.unescape(script))
        except (ValueError, TypeError): continue
        def visit(node):
            if isinstance(node, list):
                for child in node: visit(child)
            elif isinstance(node, dict):
                url = node.get("url") or node.get("mainEntityOfPage")
                if isinstance(url, dict): url = url.get("@id")
                title = node.get("headline") or node.get("name")
                if isinstance(url,str) and isinstance(title,str) and re.search(r"presseportal\.de/blaulicht/pm/110972/\d+",url):
                    parser.entries.append({"category":"polizei","title":title[:260],"url":url,"published":node.get("datePublished")})
                for child in node.values():
                    if isinstance(child,(dict,list)): visit(child)
        visit(nodes)
    results = list({entry["url"]:entry for entry in parser.entries}.values())[:35]
    if not results: raise ValueError("No verified Karlsruhe police article links on newsroom page")
    return results

items=[];sources={}
try:
    root=ET.fromstring(get("https://www.presseportal.de/rss/blaulicht/nr/110972"))
    from email.utils import parsedate_to_datetime
    for entry in root.findall(".//item")[:35]:
        title=(entry.findtext("title") or "").strip()
        url=(entry.findtext("link") or "").strip()
        raw=entry.findtext("pubDate") or ""
        try: published=parsedate_to_datetime(raw).astimezone(dt.timezone.utc).isoformat()
        except Exception: published=None
        if title and url.startswith(("https://www.presseportal.de/","http://www.presseportal.de/")):
            items.append({"category":"polizei","title":title[:260],"url":url,"published":published})
    if not any(x["category"]=="polizei" for x in items):raise ValueError("RSS feed empty or changed")
    sources["polizei"]="ok"
except Exception as exc:
    print("Police RSS unavailable; trying newsroom fallback:",repr(exc))
    try:
        fallback=police_fallback()
        items.extend(fallback)
        sources["polizei"]="ok"
        print("Police newsroom fallback:",len(fallback),"articles; publication times not verified")
    except Exception as fallback_exc:
        sources["polizei"]="error";print("Police newsroom fallback unavailable:",repr(fallback_exc))
try:
    parser=KVVParser()
    parser.feed(get("https://www.kvv.de/fahrplan/verkehrsmeldungen.html").decode("utf-8","replace"))
    titles=list(dict.fromkeys(x for x in parser.headings if len(x)>12 and x.lower() not in ("aktuelle verkehrsmeldungen","verkehrsmeldungen","ergebnisse filtern","filter","suchergebnisse","alle meldungen")))
    if not titles:raise ValueError("No KVV headings found")
    for title in titles[:30]:
        items.append({"category":"verkehr","title":title[:260],"url":"https://www.kvv.de/fahrplan/verkehrsmeldungen.html","published":None})
    sources["verkehr"]="ok"
except Exception as exc:
    sources["verkehr"]="error";print("KVV page unavailable:",repr(exc))
previous_path=pathlib.Path("public-reports.json")
if previous_path.exists():
    try:
        previous=json.loads(previous_path.read_text(encoding="utf-8"))
        for category in ("polizei","verkehr"):
            if sources.get(category)!="ok":
                old=[dict(x,stale=True) for x in previous.get("items",[]) if x.get("category")==category]
                items.extend(old[:35])
                if old:sources[category]="stale"
    except (ValueError,OSError,TypeError) as exc:
        print("Previous snapshot unavailable:",repr(exc))
if not items:raise SystemExit("No validated source available; preserving previous snapshot")
pathlib.Path("public-reports.json").write_text(json.dumps({"updated_at":NOW.isoformat(),"sources":sources,"items":items},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print("Published",len(items),"reports; source status",sources)
