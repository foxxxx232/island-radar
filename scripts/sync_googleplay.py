#!/usr/bin/env python3
"""Refresh publicly visible Google Play charts; never relabel stale rankings as current."""
import json, re, os, datetime, pathlib, urllib.request, urllib.parse
from bs4 import BeautifulSoup
from google_play_scraper import app as gp_app

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
        if not re.fullmatch(r"[a-zA-Z0-9_]+(?:\\.[a-zA-Z0-9_]+)+",appid) or appid in seen:continue
        text=a.get_text(" ",strip=True)
        if not text:
            img=a.find("img")
            text=(img.get("alt","") if img else "").strip()
        if not text or len(text)>130:continue
        seen.add(appid)
        results.append({"id":appid,"title":text,"url":"https://play.google.com/store/apps/details?id="+appid})
    return results

try:
    html=get_html(SOURCE)
    rows=parse(html)
    if len(rows)<10:
        raise ValueError("Could not verify 10+ Google Play package links in chart HTML; site may be JS-rendered or blocked")
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
                "source_url":SOURCE,"rank_source":"GamerScroll public chart"})
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
    existing["source"]="GamerScroll public Google Play chart"
    existing["source_url"]=SOURCE
    existing["refresh_status"]="ok"
    print("Verified Google Play chart:",len(verified))
except Exception as e:
    existing["refresh_status"]="failed"
    existing["refresh_error"]=str(e)[:250]
    existing["countries"]["tw"]["free_status"]="stale"
    print("Google Play refresh failed; previous snapshot preserved:",e)
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(existing,ensure_ascii=False,indent=2),encoding="utf-8")
