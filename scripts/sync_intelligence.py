#!/usr/bin/env python3
"""Aggregate Taiwan mobile game news from multiple media search feeds; preserve curated evidence."""
import json, pathlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET, datetime, email.utils, re, difflib, time
PATH=pathlib.Path("data/intelligence.json")
data=json.loads(PATH.read_text(encoding="utf-8"))
now=datetime.datetime.now(datetime.timezone.utc)
queries=[
("台灣手遊新遊戲",'"手遊" "上市" when:14d'),
("港台預約",'("手遊" OR "手機遊戲") ("事前預約" OR "預先註冊" OR "預訂") when:45d'),
("巴哈預約",'site:gnn.gamer.com.tw ("事前預約" OR "事前登錄" OR "預訂" OR "預約開跑") when:60d'),
("巴哈上線",'site:gnn.gamer.com.tw ("正式上市" OR "正式上線" OR "開服") 手遊 when:45d'),
("FB預約",'site:facebook.com ("事前預約" OR "事前登錄" OR "預約開啟") ("手遊" OR "遊戲") when:45d'),
("FB預訂",'site:facebook.com ("商店預訂" OR "預先註冊" OR "雙平台預約") when:45d'),
("遊戲基地預約",'site:news.gamebase.com.tw ("預約開啟" OR "事前預約") when:45d'),
("4Gamers預約",'site:4gamers.com.tw ("事前預約" OR "預先註冊") when:45d'),
("遊戲行銷",'"手遊" "代言" OR "聯名" OR "KOL" when:30d'),
("4Gamers",'site:4gamers.com.tw/news/detail 手遊 when:14d'),
("遊戲基地",'site:news.gamebase.com.tw/news/detail 手遊 when:14d'),
("巴哈姆特",'site:gnn.gamer.com.tw 手機遊戲 when:14d'),
("GameApps 香港",'site:gameapps.hk 手遊 預約 when:30d'),
]
def relevant(title):
    mobile=re.search(r"手遊|手機遊戲|行動遊戲|移動遊戲|事前預約|事前登錄|預先註冊|預註冊|App Store|Google Play|Android|iOS|MMORPG",title,re.I)
    game=re.search(r"《[^》]+》|遊戲|電玩|RPG|SLG|三國|寶可夢|Pokémon|Garena|NEXON|騰訊|網易|遊戲業",title,re.I)
    noise=re.search(r"滑鼠|鍵盤|顯示卡|筆電|主機維修|Steam原版|車色|汽車售價|房地產|桌機|機殼|處理器|顯示器",title,re.I)
    return bool((mobile or game) and not noise and (mobile or not re.search(r"Steam|PS5|Switch|PC版|主機",title,re.I)))
articles={x["url"]:x for x in data.get("news",[]) if x.get("url") and relevant(x.get("title",""))}
marketing_terms=re.compile(r"代言|KOL|網紅|實況|聯名|聯動|合作|主題曲|演唱會|戶外|快閃|地鐵|捷運|廣告|宣傳",re.I)
pre_terms=re.compile(r"事前預約|事前登錄|預先註冊|預註冊|開放預約|預約開啟|預約開跑|商店預訂|預訂開啟|雙平台預約")
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
            if not title or not link.startswith("https://") or not relevant(title):continue
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
existing={re.sub(r"\s+","",g.get("game","")) for g in data.get("preorders",[]) if g.get("status")!="媒體預約線索（待複核）"}
candidates=[]
for article in data["news"]:
    if not pre_terms.search(article.get("title","")):continue
    if re.search(r"改版|週年|周年|活動|更新|伺服器|測試|復刻|DLC|擴充|新版本",article.get("title","")) and not re.search(r"新作|新遊戲|新手遊|上市",article.get("title","")):continue
    if re.search(r"突破|達成|破\d+萬|破十萬|破百萬",article.get("title","")) and not re.search(r"開放|開始|啟動",article.get("title","")):continue
    m=re.search(r"《([^》]{2,45})》",article["title"])
    if not m:continue
    game=m.group(1).strip()
    if re.sub(r"\s+","",game) in existing:continue
    existing.add(re.sub(r"\s+","",game))
    candidates.append({"game":game,"publisher":"待核實","status":"媒體預約線索（待複核）",
        "registration_date":None,"detected_at":article.get("published_at"),"expected_date":None,"estimate":"上市時間未公布",
        "evidence":"新聞標題提及預約，未確認官方預約頁或上市日期",
        "source":article["source"],"url":article["url"],"genre":"待確認","signals":["媒體預約線索"]})
data["preorders"]=[g for g in data.get("preorders",[]) if g.get("status")!="媒體預約線索（待複核）"]+candidates[:60]
# Optional low-confidence planning window: a rough 30–90 day period after
# announced preregistration, never treated as an official release date.
for g in data["preorders"]:
    if g.get("expected_date") or g.get("expected_precision") or not g.get("registration_date"):continue
    try:
        start=datetime.date.fromisoformat(g["registration_date"])
        if 0 <= (now.date()-start).days <= 90 and not g.get("rewards"):
            g["estimated_window"]=(start+datetime.timedelta(days=30)).isoformat()+" ～ "+(start+datetime.timedelta(days=90)).isoformat()
            g["estimated_method"]="僅依預約開啟日推算 30–90 天觀察窗，低信心、非官方預測"
    except ValueError:pass
# Resolve visual and metadata only for strict title matches in the public Apple store.
# A released iOS store listing is not evidence that a preregistration is still active.
def normal(t):return re.sub(r"[\W_]+","",str(t or "").casefold())
for g in data["preorders"][:25]:
    if g.get("icon") and g.get("screenshots"):continue
    try:
        term=g.get("game","").strip()
        if len(term)<3:continue
        q=urllib.parse.urlencode({"term":term,"country":"tw","media":"software","entity":"software","limit":12})
        req=urllib.request.Request("https://itunes.apple.com/search?"+q,headers={"User-Agent":"IslandRadar/1.0"})
        with urllib.request.urlopen(req,timeout=8) as response:
            hits=json.loads(response.read(1500000)).get("results",[])
        matches=sorted(hits,key=lambda x:difflib.SequenceMatcher(None,normal(term),normal(x.get("trackName",""))).ratio(),reverse=True)
        if not matches:continue
        best=matches[0]
        score=difflib.SequenceMatcher(None,normal(term),normal(best.get("trackName",""))).ratio()
        if score<0.94:continue
        g["icon"]=best.get("artworkUrl512") or best.get("artworkUrl100") or ""
        g["screenshots"]=best.get("screenshotUrls",[])[:5]
        g["ios_url"]=best.get("trackViewUrl","")
        g["store_visual_source"]="Apple iTunes Search, exact-title verified"
        if g.get("publisher") in ("待核實",""):
            g["publisher"]=best.get("artistName","待核實")
        if g.get("genre") in ("待確認",""):
            g["genre"]=best.get("primaryGenreName","待確認")
        print("Preorder visual match:",term)
    except Exception as e:
        print("Preorder metadata lookup unavailable:",g.get("game"),str(e)[:100])

# News is an evidence feed, not verified ad spend or a reliable forecast of launch dates.
data["updated_at"]=now.isoformat()
data["news_count"]=len(data["news"])
PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("Saved intelligence",len(data["news"]),"articles",len(data.get("campaigns",[])),"curated campaigns")
