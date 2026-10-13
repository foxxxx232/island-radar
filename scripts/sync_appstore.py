import json, urllib.request, datetime, pathlib, time, concurrent.futures
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
def cache_icon(item):
    app_id=item['id']
    url=item.get('icon','')
    if not url or not app_id.isdigit(): return
    target=pathlib.Path('assets/icons')/(app_id+'.png')
    if target.exists() and target.stat().st_size>1000:
        item['icon']='/'+str(target)
        return
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=12) as res:
            payload=res.read(350000)
            ct=res.headers.get('Content-Type','')
        if payload.startswith(b'\\x89PNG') or payload.startswith(b'\\xff\\xd8\\xff'):
            target.parent.mkdir(parents=True,exist_ok=True)
            if payload.startswith(b'\\xff\\xd8\\xff'):
                target=target.with_suffix('.jpg')
            target.write_bytes(payload)
            item['icon']='/'+str(target)
    except Exception as e:
        print('Icon unavailable',app_id,str(e)[:80])

pathlib.Path('assets/icons').mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
result={'source':'Apple iTunes public RSS','fetched_at':now,'data_type':'public_chart_snapshot','countries':{}}
for c in COUNTRIES:
    result['countries'][c]={}
    for kind,key in [('topfreeapplications','free'),('topgrossingapplications','grossing')]:
        rows=chart(c,kind)
        result['countries'][c][key]=rows or []
        result['countries'][c][key+'_status']='ok' if rows is not None else 'unavailable'
        time.sleep(.3)
items={x['id']:x for v in result['countries'].values() for key in ('free','grossing') for x in v[key]}
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    list(pool.map(cache_icon,items.values()))
for v in result['countries'].values():
    for key in ('free','grossing'):
        for item in v[key]:
            item['icon']=items[item['id']]['icon']
path=pathlib.Path('data/appstore.json')
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved',path,'records:',sum(len(v[k]) for v in result['countries'].values() for k in ['free','grossing']))
