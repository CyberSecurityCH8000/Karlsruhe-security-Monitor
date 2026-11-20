import datetime as dt
import json, pathlib, re, urllib.request
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

NOW=dt.datetime.now(dt.timezone.utc)
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"KarlsruheSecurityMonitor/1.0 (+public-information-dashboard)","Accept":"text/html,application/rss+xml,application/xml"})
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
        if title and url.startswith("https://www.presseportal.de/"):
            items.append({"category":"polizei","title":title[:260],"url":url,"published":published})
    if not any(x["category"]=="polizei" for x in items):raise ValueError("RSS feed empty or changed")
    sources["polizei"]="ok"
except Exception as exc:
    sources["polizei"]="error";print("Police feed unavailable:",repr(exc))
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
if not items:raise SystemExit("No validated source available; preserving previous snapshot")
pathlib.Path("public-reports.json").write_text(json.dumps({"updated_at":NOW.isoformat(),"sources":sources,"items":items},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print("Published",len(items),"reports; source status",sources)
