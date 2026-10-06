import os,sys,json,time,base64,math,statistics,platform
from urllib.request import Request,urlopen
from db import DB
mode=sys.argv[1]
assert mode in ('small','work')
base='http://127.0.0.1:8000'
headers={'Authorization':'Basic '+base64.b64encode(('librarian:'+os.environ['API_PASSWORD']).encode()).decode(),'Content-Type':'application/json'}
samples=[]
def run(op,method,path,body=None,warm=False):
    req=Request(base+path,data=json.dumps(body).encode() if body else (b'{}' if method=='POST' else None),headers=headers,method=method)
    start=time.perf_counter()
    with urlopen(req,timeout=120) as response:
        raw=response.read();total=(time.perf_counter()-start)*1000
        db=float(response.headers['X-DB-MS']);server=float(response.headers['X-App-MS'])
        s={'operation':op,'total_ms':total,'server_ms':server,'db_ms':db,'code_ms':server-db,'queries':int(response.headers['X-DB-Queries']),'bytes':len(raw),'status':response.status}
    if not warm:samples.append(s)
    return json.loads(raw)
# Measurements of writes require independent valid fixtures. 21 = one warmup + 20 samples.
with DB() as db:
    before={t:db.query('SELECT count(*) AS n FROM '+t)[0]['n'] for t in ('readers','books','copies','loans')}
    reader=db.query("INSERT INTO readers(id,name) SELECT coalesce(max(id),0)+1,'Замерщик' FROM readers RETURNING id")[0]['id']
    first=db.query('SELECT max(id)+1 AS id FROM copies')[0]['id']
    db.query('INSERT INTO copies(id,book_id) SELECT i,1 FROM generate_series(%s::integer,%s::integer) i',(first,first+20))
for op,path in [('list','/api/loans'),('filter','/api/loans?status=overdue'),('detail','/api/loans/1'),('summary','/api/summary')]:
    run(op,'GET',path,warm=True)
    for _ in range(20):run(op,'GET',path)
ids=[]
for i in range(21):
    ids.append(run('issue','POST','/api/loans',{'reader_id':reader,'copy_id':first+i},warm=i==0)['id'])
for i,lid in enumerate(ids):run('return','POST',f'/api/loans/{lid}/return',warm=i==0)
summary=[]
for op in dict.fromkeys(s['operation'] for s in samples):
    ss=[s for s in samples if s['operation']==op];times=sorted(s['total_ms'] for s in ss)
    summary.append({'operation':op,'p50_ms':statistics.median(times),'p95_ms':times[math.ceil(.95*len(times))-1],**{k:statistics.median(s[k] for s in ss) for k in ('server_ms','db_ms','code_ms','queries')}})
with DB() as db:after={t:db.query('SELECT count(*) AS n FROM '+t)[0]['n'] for t in before}
result={'mode':mode,'prefix':os.environ['PERSONAL_PREFIX'],'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'platform':platform.platform(),'python':platform.python_version(),'before_counts':before,'after_counts':after,'samples':samples,'summary':summary}
os.makedirs('results',exist_ok=True)
with open(f'results/{mode}.json','w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(summary,ensure_ascii=False,indent=2))
