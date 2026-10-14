#!/usr/bin/env python3
"""Refresh publicly visible Google Play charts; never relabel stale rankings as current."""
import json, re, os, datetime, pathlib, urllib.request, urllib.parse
from bs4 import BeautifulSoup
from google_play_scraper import app as gp_app, search as gp_search
try:
    from google_play_scraper import collection as gp_collection, collections as gp_collections, categories as gp_categories
except ImportError:
    gp_collection=gp_collections=gp_categories=None
import difflib, concurrent.futures

OUT=pathlib.Path("data/googleplay.json")
SOURCE="https://gamerscroll.com/zh-tw/rankings/free/tw/"
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
existing=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"countries":{}}
existing.setdefault("countries",{})
for c in ("tw","hk","mo"):
    existing["countries"].setdefault(c,{"free":[],"grossing":[],"free_status":"unavailable","grossing_status":"unavailable"})
existing["last_attempt_at"]=now
existing["refresh_status"]="unavailable"
existing["refresh_source"]=SOURCE

def get_html(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; IslandRadar/1.0; public-chart-research)","Accept-Language":"zh-TW,zh;q=0.9,en;q=0.7"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read(3500000).decode("utf-8","replace")

def parse(html):
    soup=BeautifulSoup(html,"html.parser")
    results=[]
    seen=set()
    # Trust only anchors linking to an identifiable Google Play package.
    for a in soup.select('a[href*="play.google.com/store/apps/details"]'):
        href=urllib.parse.urljoin(SOURCE,a.get("href",""))
        appid=urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("id",[""])[0]
        if not re.fullmatch(r"[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+",appid) or appid in seen:continue
        text=a.get_text(" ",strip=True)
        if not text:
            img=a.find("img")
            text=(img.get("alt","") if img else "").strip()
        if not text or len(text)>130:continue
        seen.add(appid)
        results.append({"id":appid,"title":text,"url":"https://play.google.com/store/apps/details?id="+appid})
    return results

def fill_metadata(row):
    """Enrich existing ranked titles without changing their rank when chart retrieval fails."""
    if row.get("icon") and row.get("screenshots") and row.get("id","").count(".")>=1:
        return row
    try:
        appid=row.get("id","")
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+",appid):
            candidates=gp_search(row["title"],lang="zh_TW",country="tw",n_hits=7)
            def sim(c):
                a=re.sub(r"[^\w]","",row["title"].casefold())
                b=re.sub(r"[^\w]","",c.get("title","").casefold())
                return difflib.SequenceMatcher(None,a,b).ratio()
            candidates=sorted(candidates,key=sim,reverse=True)
            if not candidates or sim(candidates[0])<.84:
                return row
            appid=candidates[0]["appId"]
        meta=gp_app(appid,lang="zh_TW",country="tw")
        row.update({"id":appid,"title":meta.get("title") or row["title"],
           "publisher":meta.get("developer") or row.get("publisher",""),
           "developer":meta.get("developer",""),"icon":meta.get("icon",""),
           "url":"https://play.google.com/store/apps/details?id="+appid,
           "genre":meta.get("genre",""),"genres":[meta.get("genre","")],
           "description":meta.get("description",""),
           "screenshots":meta.get("screenshots",[])[:8],
           "rating":meta.get("score"),"rating_count":meta.get("ratings"),
           "release_date":meta.get("released",""),
           "metadata_source":"Google Play store details",
           "positioning":None,"slogan":None})
        desc=meta.get("description","")
        lines=[p.strip("「」『』【】#*• ") for p in desc.splitlines()]
        lines=[p for p in lines if 10<=len(p)<=100 and not re.search(r"隱私|客服|Facebook|https?://|條款|更新|下載|email",p,re.I)]
        if lines:
            row["positioning"]=lines[0][:95]
            row["positioning_status"]="store_description_excerpt"
            slogans=[p for p in lines if len(p)<=48]
            if slogans:
                row["slogan"]=slogans[0]
                row["slogan_status"]="store_copy_excerpt_not_official"
    except Exception as e:
        print("GP metadata unavailable",row.get("title"),str(e)[:80])
    return row

try:
    html=get_html(SOURCE)
    rows=parse(html)
    if len(rows)<10:
        print("GamerScroll HTML does not expose package links; trying Google Play public collection")
        try:
            if gp_collection is None:raise RuntimeError("Google Play chart collection API unavailable")
            raw=gp_collection(collection=gp_collections.TOP_FREE,category=gp_categories.GAME,results=100,lang="zh_TW",country="tw")
            rows=[{"id":x["appId"],"title":x["title"],
                   "url":"https://play.google.com/store/apps/details?id="+x["appId"]}
                  for x in raw if x.get("appId") and x.get("title")]
            if len(rows)>=10:
                existing["refresh_source"]="Google Play public chart via google-play-scraper"
                print("GP collection:",len(rows))
        except Exception as colerr:
            print("Google Play collection unavailable",str(colerr)[:180])
    if len(rows)<10:
        raise ValueError("No verifiable public Google Play ranking source returned 10+ records")
    verified=[]
    for item in rows[:100]:
        try:
            meta=gp_app(item["id"],lang="zh_TW",country="tw")
            title=meta.get("title") or item["title"]
            verified.append({"id":item["id"],"rank":len(verified)+1,"title":title,
                "publisher":meta.get("developer",""),"developer":meta.get("developer",""),
                "seller":"","icon":meta.get("icon",""),"url":item["url"],
                "genre":meta.get("genre",""),"genres":[meta.get("genre","")],
                "description":meta.get("description",""),"screenshots":meta.get("screenshots",[])[:10],
                "rating":meta.get("score"),"rating_count":meta.get("ratings"),
                "release_date":meta.get("released",""),"positioning":None,"slogan":None,
                "positioning_status":"unverified","slogan_status":"unverified",
                "source_url":existing.get("source_url") or SOURCE,"rank_source":existing.get("refresh_source") or SOURCE})
        except Exception as e:
            print("Metadata unavailable:",item["id"],str(e)[:100])
            verified.append({**item,"rank":len(verified)+1,"publisher":"","developer":"",
                "icon":"","screenshots":[],"positioning":None,"slogan":None,
                "source_url":SOURCE,"rank_source":"GamerScroll public chart"})
    if len(verified)<10:raise ValueError("Too few verified chart entries")
    existing["countries"]["tw"]["free"]=verified
    existing["countries"]["tw"]["free_status"]="ok"
    existing["snapshot_date"]=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    existing["fetched_at"]=now
    existing["source"]=existing.get("refresh_source",SOURCE)
    existing["source_url"]=SOURCE if "GamerScroll" in existing["source"] else "https://play.google.com/store/games?hl=zh_TW&gl=TW"
    existing["refresh_status"]="ok"
    print("Verified Google Play chart:",len(verified))
except Exception as e:
    existing["refresh_status"]="failed"
    existing["refresh_error"]=str(e)[:250]
    existing["countries"]["tw"]["free_status"]="stale"
    print("Google Play rank refresh failed; enriching last verified snapshot:",e)
    oldrows=existing["countries"]["tw"].get("free",[])
    if oldrows:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            existing["countries"]["tw"]["free"]=list(pool.map(fill_metadata,oldrows[:70]))
        existing["metadata_refreshed_at"]=now
        print("GP metadata filled:",sum(bool(x.get("icon")) for x in existing["countries"]["tw"]["free"]))
OUT.parent.mkdir(parents=True,exist_ok=True)
# Cross-platform visual fallback only when Google Play details are unavailable.
# Clearly label the Apple artwork source; never misrepresent it as Google Play screenshots.
try:
    apple=json.loads(pathlib.Path("data/appstore.json").read_text(encoding="utf-8"))
    lookup={}
    def title_key(t):return re.sub(r"[\W_]+","",str(t or "").casefold())
    for country in ("tw","hk","mo"):
        for kind in ("free","grossing"):
            for item in apple.get("countries",{}).get(country,{}).get(kind,[]):
                if item.get("icon"):
                    lookup.setdefault(title_key(item.get("title")),item)
    for country in ("tw","hk","mo"):
        for kind in ("free","grossing"):
            for row in existing["countries"].get(country,{}).get(kind,[]):
                if row.get("icon"):continue
                match=lookup.get(title_key(row.get("title")))
                if match:
                    row["icon"]=match["icon"]
                    row["screenshots"]=match.get("screenshots",[])[:5]
                    row["visual_source"]="Apple App Store cross-platform visual reference (Google Play visual not yet verified)"
                    print("Apple cross-platform visual reference:",row.get("title"))
except Exception as e:
    print("Cross-platform visual fallback unavailable",str(e)[:100])
OUT.write_text(json.dumps(existing,ensure_ascii=False,indent=2),encoding="utf-8")
