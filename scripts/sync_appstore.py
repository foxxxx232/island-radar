import json, urllib.request, datetime, pathlib, time, concurrent.futures, xml.etree.ElementTree as ET, email.utils, re
COUNTRIES = ['tw','hk','mo']
BASE = 'https://itunes.apple.com'
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'IslandRadar/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response:
        return json.load(response)
def chart(country,kind):
    url=f'https://itunes.apple.com/{country}/rss/{kind}/limit=100/genre=6014/json'
    try:
        payload=get(url)
        entries=payload.get('feed',{}).get('entry',[])
        return [{'id':str(e.get('id',{}).get('attributes',{}).get('im:id','')),
                 'rank':i+1,'title':e.get('im:name',{}).get('label',''),
                 'publisher':e.get('im:artist',{}).get('label',''),
                 'icon':(e.get('im:image') or [{}])[-1].get('label',''),
                 'url':e.get('id',{}).get('label','')}
                for i,e in enumerate(entries) if e.get('id',{}).get('attributes',{}).get('im:id')]
    except Exception as ex:
        print(f'Unavailable {country} {kind}: {ex}')
        return None
def enrich(country, rows):
    ids=list(dict.fromkeys(x['id'] for x in rows if x['id'].isdigit()))
    details={}
    for i in range(0,len(ids),40):
        try:
            url='https://itunes.apple.com/lookup?id='+','.join(ids[i:i+40])+'&country='+country
            for app in get(url).get('results',[]):
                details[str(app.get('trackId',''))]=app
        except Exception as ex:
            print('Lookup unavailable',country,str(ex)[:100])
    for item in rows:
        d=details.get(item['id'],{})
        item['icon']=d.get('artworkUrl512') or d.get('artworkUrl100') or item['icon']
        item['screenshots']=d.get('screenshotUrls',[])[:10]
        item['ipad_screenshots']=d.get('ipadScreenshotUrls',[])[:10]
        item['description']=d.get('description','')
        item['genre']=d.get('primaryGenreName','')
        item['genres']=d.get('genres',[])
        item['genre_ids']=d.get('genreIds',[])
        item['developer']=d.get('artistName','')
        item['seller']=d.get('sellerName','')
        item['publisher']=item['publisher'] or d.get('artistName','')
        item['positioning']=None
        item['slogan']=None
        item['positioning_status']='unverified'
        item['slogan_status']='unverified'
        desc=item['description']
        m=re.search(r'(?:官方(?:宣傳)?(?:口號|標語)|遊戲(?:宣傳)?(?:口號|標語)|Slogan)\\s*[：:]\\s*([^\\n\\r。！!]{4,55})',desc,re.I)
        if m:
            item['slogan']=m.group(1).strip('「」『』" ')
            item['slogan_status']='store_description_explicit'
            item['slogan_source']=item['url']
        m=re.search(r'(?:遊戲定位|產品定位|主打特色)\\s*[：:]\\s*([^\\n\\r。！!]{4,90})',desc,re.I)
        if m:
            item['positioning']=m.group(1).strip('「」『』" ')
            item['positioning_status']='store_description_explicit'
            item['positioning_source']=item['url']
        item['release_date']=d.get('releaseDate','')
        item['version']=d.get('version','')
        item['rating']=d.get('averageUserRating')
        item['rating_count']=d.get('userRatingCount')
        item['url']=d.get('trackViewUrl') or item['url']
    return rows

now=datetime.datetime.now(datetime.timezone.utc).isoformat()
result={'source':'Apple iTunes public RSS','fetched_at':now,'data_type':'public_chart_snapshot','countries':{}}
for c in COUNTRIES:
    result['countries'][c]={}
    for kind,key in [('topfreeapplications','free'),('topgrossingapplications','grossing')]:
        rows=chart(c,kind)
        if rows: rows=enrich(c,rows)
        result['countries'][c][key]=rows or []
        result['countries'][c][key+'_status']='ok' if rows is not None else 'unavailable'
        time.sleep(.3)
def fetch_news():
    feeds=[('巴哈姆特 GNN','https://gnn.gamer.com.tw/rss.xml')]
    articles=[]
    for name,url in feeds:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 IslandRadar/1.0'})
            with urllib.request.urlopen(req,timeout=20) as response:
                root=ET.fromstring(response.read(1500000))
            for item in root.findall('.//item')[:60]:
                title=(item.findtext('title') or '').strip()
                link=(item.findtext('link') or '').strip()
                date=(item.findtext('pubDate') or '').strip()
                if title and link and link.startswith('https://'):
                    articles.append({'title':title,'url':link,'published_at':date,'source':name})
        except Exception as ex:
            print('News feed unavailable',name,str(ex)[:120])
    return articles

result['news']=fetch_news()
path=pathlib.Path('data/appstore.json')
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved',path,'records:',sum(len(v[k]) for v in result['countries'].values() for k in ['free','grossing']))
