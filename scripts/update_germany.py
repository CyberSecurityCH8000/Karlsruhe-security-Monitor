"""National DWD district warnings; fail closed on malformed or unreachable source."""
import json, pathlib, urllib.request, datetime
URL="https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json"
req=urllib.request.Request(URL,headers={"User-Agent":"DeutschlandSecurityMonitor/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=35) as response:
    raw=response.read(12_000_000)
text=raw.decode("utf-8-sig").strip()
if text.startswith("warnWetter.loadWarnings("):
    text=text[len("warnWetter.loadWarnings("):].rstrip(";").rstrip(")")
data=json.loads(text)
if not isinstance(data,dict) or not isinstance(data.get("warnings"),dict):
    raise ValueError("Unexpected DWD JSON structure")
items=[]
for district,warnings in data["warnings"].items():
    if not isinstance(warnings,list): continue
    for w in warnings:
        if not isinstance(w,dict): continue
        title=w.get("headline") or w.get("event") or "Wetterwarnung"
        if not isinstance(title,str):continue
        items.append({"district":str(district),"title":title[:400],"region":str(w.get("regionName") or "")[:200],"level":w.get("level"),"start":w.get("start"),"end":w.get("end"),"description":str(w.get("description") or "")[:700]})
output={"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source":URL,"warnings":items,"scope":"Deutschland; DWD-Landkreise"}
pathlib.Path("germany.json").write_text(json.dumps(output,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print("National DWD warnings:",len(items))
