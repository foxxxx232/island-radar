#!/usr/bin/env python3
"""Aggregate Taiwan mobile game news from multiple media search feeds; preserve curated evidence."""
import json, pathlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET, datetime, email.utils, re
PATH=pathlib.Path("data/intelligence.json")
data=json.loads(PATH.read_text(encoding="utf-8"))
now=datetime.datetime.now(datetime.timezone.utc)
queries=[
("台灣手遊新遊戲",'"手遊" "上市" when:14d'),
("港台預約",'"手遊" "事前預約" when:30d'),
("遊戲行銷",'"手遊" "代言" OR "聯名" OR "KOL" when:30d'),
("4Gamers",'site:4gamers.com.tw/news/detail 手遊 when:14d'),
("遊戲基地",'site:news.gamebase.com.tw/news/detail 手遊 when:14d'),
("巴哈姆特",'site:gnn.gamer.com.tw 手機遊戲 when:14d'),
("GameApps 香港",'site:gameapps.hk 手遊 預約 when:30d'),
]
articles={x["url"]:x for x in data.get("news",[]) if x.get("url")}
marketing_terms=re.compile(r"代言|KOL|網紅|實況|聯名|聯動|合作|主題曲|演唱會|戶外|快閃|地鐵|捷運|廣告|宣傳",re.I)
pre_terms=re.compile(r"事前預約|事前登錄|預先註冊|預註冊|開放預約")
for label,query in queries:
    url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":query,"hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"})
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 IslandRadar/1.0"})
        with urllib.request.urlopen(req,timeout=17) as response:
            root=ET.fromstring(response.read(2000000))
        count=0
        for node in root.findall(".//item")[:45]:
            title=(node.findtext("title") or "").strip()
            link=(node.findtext("link") or "").strip()
            published=(node.findtext("pubDate") or "").strip()
            source_node=node.find("source")
            source=(source_node.text or label).strip() if source_node is not None else label
            if not title or not link.startswith("https://"):continue
            try:
                stamp=email.utils.parsedate_to_datetime(published)
                if (now-stamp.astimezone(datetime.timezone.utc)).days>35:continue
                pub=stamp.date().isoformat()
            except Exception:pub=published
            tags=[]
            if marketing_terms.search(title):tags.append("行銷動態")
            if pre_terms.search(title):tags.append("事前預約")
            if re.search(r"上市|公測|上線",title):tags.append("上線")
            articles.setdefault(link,{"title":title,"url":link,"source":source,"published_at":pub,"tags":tags,"source_type":"media_report"})
            count+=1
        print("News",label,count)
    except Exception as e:
        print("News feed unavailable",label,str(e)[:140])
def key(x):return str(x.get("published_at",""))[:10]
data["news"]=sorted(articles.values(),key=key,reverse=True)[:160]
# Candidate preregistrations from media headlines, distinctly separated from confirmed official dates.
existing={re.sub(r"\s+","",g.get("game","")) for g in data.get("preorders",[])}
candidates=[]
for article in data["news"]:
    if not pre_terms.search(article.get("title","")):continue
    m=re.search(r"《([^》]{2,45})》",article["title"])
    if not m:continue
    game=m.group(1).strip()
    if re.sub(r"\s+","",game) in existing:continue
    existing.add(re.sub(r"\s+","",game))
    candidates.append({"game":game,"publisher":"待核實","status":"媒體預約線索（待複核）",
        "registration_date":None,"expected_date":None,"estimate":"上市時間未公布",
        "evidence":"新聞標題提及預約，未確認官方預約頁或上市日期",
        "source":article["source"],"url":article["url"],"genre":"待確認","signals":["媒體預約線索"]})
data["preorders"]=[g for g in data.get("preorders",[]) if g.get("status")!="媒體預約線索（待複核）"]+candidates[:30]
# Optional low-confidence planning window: a rough 30–90 day period after
# announced preregistration, never treated as an official release date.
for g in data["preorders"]:
    if g.get("expected_date") or not g.get("registration_date"):continue
    try:
        start=datetime.date.fromisoformat(g["registration_date"])
        if 0 <= (now.date()-start).days <= 90:
            g["estimated_window"]=(start+datetime.timedelta(days=30)).isoformat()+" ～ "+(start+datetime.timedelta(days=90)).isoformat()
            g["estimated_method"]="僅依預約開啟日推算 30–90 天觀察窗，低信心、非官方預測"
    except ValueError:pass
# News is an evidence feed, not verified ad spend or a reliable forecast of launch dates.
data["updated_at"]=now.isoformat()
data["news_count"]=len(data["news"])
PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("Saved intelligence",len(data["news"]),"articles",len(data.get("campaigns",[])),"curated campaigns")
