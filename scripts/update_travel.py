#!/usr/bin/env python3
"""Official German Foreign Office travel advisory RSS updates, not a complete warning inventory."""
import datetime as dt
import json
import pathlib
import urllib.request
import xml.etree.ElementTree as ET

URL="https://www.auswaertiges-amt.de/static/includes/rss/Reisehinweise-RSS-Feed.xml"
req=urllib.request.Request(URL,headers={"User-Agent":"GlobalSecurityMonitor/1.0","Accept":"application/rss+xml,application/xml,text/xml"})
with urllib.request.urlopen(req,timeout=30) as response:
    xml=response.read(2_000_000)
root=ET.fromstring(xml)
items=[]
for item in root.findall("./channel/item"):
    title=(item.findtext("title") or "").strip()
    link=(item.findtext("link") or "").strip()
    date=(item.findtext("pubDate") or "").strip()
    if not title or not link.startswith("https://www.auswaertiges-amt.de/"):
        continue
    items.append({"title":title[:240],"url":link[:800],"published":date[:100]})
if not items:
    raise ValueError("No valid official travel updates; refusing to publish an empty feed")
output={"updated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"source":URL,"type":"recent_updates_not_complete_warnings","updates":items[:120]}
pathlib.Path("travel-updates.json").write_text(json.dumps(output,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print("Official travel advisory updates:",len(items))
