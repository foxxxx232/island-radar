import json, urllib.request, datetime, pathlib, time
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
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
result={'source':'Apple iTunes public RSS','fetched_at':now,'data_type':'public_chart_snapshot','countries':{}}
for c in COUNTRIES:
    result['countries'][c]={}
    for kind,key in [('topfreeapplications','free'),('topgrossingapplications','grossing')]:
        rows=chart(c,kind)
        result['countries'][c][key]=rows or []
        result['countries'][c][key+'_status']='ok' if rows is not None else 'unavailable'
        time.sleep(.3)
path=pathlib.Path('data/appstore.json')
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved',path,'records:',sum(len(v[k]) for v in result['countries'].values() for k in ['free','grossing']))
