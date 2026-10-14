#!/usr/bin/env python3
"""Produce evidence-labelled market alerts from real store records and chart history."""
import json, pathlib, datetime, re
ROOT=pathlib.Path("data")
STATE=ROOT/"watch_state.json"
OUT=ROOT/"alerts.json"
SCHEDULE=ROOT/"launch_schedule.json"
schedule=json.loads(SCHEDULE.read_text(encoding="utf-8")) if SCHEDULE.exists() else {"games":{}}
WATCH={
 "露珠":["露珠","luzhu"],
 "天游":["天游","tianyou"],
 "星創":["星創","星创","starcreate"],
 "樂牛":["樂牛","乐牛","le niu","leniu"],
 "靈犀":["靈犀","灵犀","lingxi","ling xi","lingxi games"],
 "四三":["四三","4399","fourthree"],
 "三七":["三七","37games","37 games","37 interactive","37games global","37 entertainment"],
}
# Matching is based on exact registered/visible names or explicit aliases, not speculation.
def norm(s):
 return re.sub(r"[^a-z0-9\u3400-\u9fff]","",str(s or "").casefold())
def watch_match(row):
 fields=[row.get("publisher",""),row.get("developer",""),row.get("seller","")]
 for brand,aliases in WATCH.items():
  for f in fields:
   n=norm(f)
   for a in aliases:
    q=norm(a)
    if q and (n==q or (len(q)>=5 and q in n)):
     return brand,f
 return None,None
now=datetime.datetime.now(datetime.timezone.utc)
old=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
had_baseline=bool(old.get("ids"))
next_ids={}
alerts=[]
for platform,file in (("ios","appstore.json"),("gp","googleplay.json")):
 path=ROOT/file
 if not path.exists():continue
 doc=json.loads(path.read_text(encoding="utf-8"))
 for region in ("tw","hk","mo"):
  for kind in ("free","grossing"):
   rows=doc.get("countries",{}).get(region,{}).get(kind,[])
   if not rows:continue
   # Only trust refreshed GP records, never treat an old imported snapshot as new.
   if platform=="gp" and doc.get("refresh_status")!="ok":continue
   key=f"{platform}:{region}:{kind}"
   ids={str(x.get("id","")) for x in rows if x.get("id")}
   next_ids[key]=sorted(ids)
   previous=set(old.get("ids",{}).get(key,[]))
   for x in rows:
    ident=str(x.get("id",""))
    if not ident:continue
    brand,matched=watch_match(x)
    release=(x.get("release_date") or "")[:10]
    recent=False
    try:
     days=(now.date()-datetime.date.fromisoformat(release)).days
     recent=0<=days<=14
    except (ValueError,TypeError):pass
    new_entry=had_baseline and key in old.get("ids",{}) and ident not in previous
    top_entry=new_entry and isinstance(x.get("rank"),int) and x["rank"]<=10
    if not (brand or recent or new_entry):continue
    tags=[]
    if brand:tags.append("重點廠商："+brand)
    if recent:tags.append("近期上架（商店日期）")
    if new_entry:tags.append("新進榜（不等於新上線）")
    if top_entry:tags.append("TOP10 重點關注")
    level="high" if ((brand and (recent or new_entry)) or top_entry) else "watch"
    planned=schedule.get("games",{}).get(platform+":"+ident,{})
    planned_date=planned.get("expected_date") if planned.get("source_url") else None
    planned_precision=planned.get("precision","day") if planned_date else None
    time_label=("預計上架："+planned_date if planned_date else ("已上架："+release if release and recent else ("商店上架日期："+release if release else "上架時間待公布")))
    alerts.append({"id":key+":"+ident,"platform":platform,"region":region,"kind":kind,
      "title":x.get("title",""),"publisher":x.get("publisher",""),"rank":x.get("rank"),
      "game_id":ident,"url":x.get("url",""),"brand":brand,"matched_publisher":matched,
      "keywords":tags,"level":level,"release_date":release or None,
      "expected_release_date":planned_date,"expected_date_precision":planned_precision,
      "expected_release_source":planned.get("source_url") if planned_date else None,
      "launch_time_label":time_label,
      "evidence":"商店上架日期" if recent else ("本期新進榜" if new_entry else "發行商名稱符合關注名單"),
      "is_confirmed_launch":recent,
      "observed_at":now.isoformat()})
# Preserve old chart IDs if a feed failed this run.
for k,v in old.get("ids",{}).items():next_ids.setdefault(k,v)
STATE.write_text(json.dumps({"updated_at":now.isoformat(),"ids":next_ids},ensure_ascii=False,indent=2),encoding="utf-8")
OUT.write_text(json.dumps({"generated_at":now.isoformat(),"has_baseline":had_baseline,
 "watchlist":list(WATCH),"alerts":sorted(alerts,key=lambda a:(a["level"]!="high",a["rank"] or 999))},ensure_ascii=False,indent=2),encoding="utf-8")
print("Alerts:",len(alerts),"high:",sum(x["level"]=="high" for x in alerts))
