import os, base64
from datetime import date
from unittest.mock import patch
os.environ['API_PASSWORD']='test'
from app import app
HEAD={'Authorization':'Basic '+base64.b64encode(b'librarian:test').decode()}
ROW={'id':1,'reader_id':1,'copy_id':1,'issued_on':date(2026,1,1),'due_on':date(2026,1,15),'returned_on':None}
class FakeDB:
    def __init__(self,answers): self.answers=iter(answers);self.ms=0;self.count=0
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def query(self,*args): self.count+=1;return next(self.answers)
def call(method,path,answers,body=None):
    with patch('app.DB',return_value=FakeDB(answers)):
        return app.test_client().open(path,method=method,headers=HEAD,json=body)
def test_auth():
    assert app.test_client().get('/api/loans').status_code==401
def test_pagination():
    r=call('GET','/api/loans',[ [{'n':1}], [ROW] ])
    assert r.status_code==200 and r.json['total']==1 and len(r.json['items'])==1
def test_bad_size(): assert call('GET','/api/loans?size=101',[]).status_code==422
def test_bad_filter(): assert call('GET','/api/loans?status=x',[]).status_code==422
def test_missing_detail(): assert call('GET','/api/loans/999',[[]]).status_code==404
def test_detail():
    r=call('GET','/api/loans/1',[[dict(ROW,reader='A',book='B',book_id=1)]])
    assert r.status_code==200 and 'fine_rub' in r.json
def test_summary():
    r=call('GET','/api/summary',[[{'on_hands':1,'overdue':0}],[]])
    assert set(r.json)=={'on_hands','overdue','top_books'}
def test_issue():
    r=call('POST','/api/loans',[[{'id':1}],[{'id':1}],[],[],[ROW]],{'reader_id':1,'copy_id':1})
    assert r.status_code==201 and r.json['id']==1
def test_issue_busy(): assert call('POST','/api/loans',[[{'id':1}],[{'id':1}],[{'id':1}],[]],{'reader_id':1,'copy_id':1}).status_code==409
def test_issue_overdue(): assert call('POST','/api/loans',[[{'id':1}],[{'id':1}],[],[{'id':1}]],{'reader_id':1,'copy_id':1}).status_code==409
def test_issue_missing(): assert call('POST','/api/loans',[[],[]],{'reader_id':1,'copy_id':1}).status_code==404
def test_issue_invalid(): assert call('POST','/api/loans',[],{'reader_id':0,'copy_id':1}).status_code==422
def test_return():
    r=call('POST','/api/loans/1/return',[[ROW],[dict(ROW,returned_on=date(2026,1,18))]])
    assert r.status_code==200 and r.json['fine_rub']==30
def test_return_missing(): assert call('POST','/api/loans/99/return',[[]]).status_code==404
def test_return_twice(): assert call('POST','/api/loans/1/return',[[dict(ROW,returned_on=date(2026,1,2))]]).status_code==409
