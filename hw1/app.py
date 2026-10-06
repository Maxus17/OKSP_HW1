import os, time, hmac
from datetime import date, timedelta
from flask import Flask, request, jsonify, g
from db import DB
from rules import fine
app = Flask(__name__)

def fail(code, message):
    return jsonify(error=message), code

@app.before_request
def before():
    g.started=time.perf_counter(); g.db_ms=0.; g.db_count=0
    if request.path.startswith('/api/'):
        auth=request.authorization
        if not auth or auth.username!='librarian' or not hmac.compare_digest(auth.password or '',os.environ['API_PASSWORD']):
            response=fail(401,'Требуется авторизация')
            response[0].headers['WWW-Authenticate']='Basic realm="Library"'
            return response

@app.after_request
def after(response):
    response.headers['Cache-Control']='no-store'
    response.headers['X-DB-MS']=str(g.db_ms)
    response.headers['X-DB-Queries']=str(g.db_count)
    response.headers['X-App-MS']=str((time.perf_counter()-g.started)*1000)
    return response

def record(db):
    g.db_ms=db.ms; g.db_count=db.count

def positive(value):
    if isinstance(value,bool): raise ValueError()
    n=int(value)
    if str(n)!=str(value) or n<1: raise ValueError()
    return n

@app.get('/api/loans')
def loans():
    try:
        page=positive(request.args.get('page','1')); size=positive(request.args.get('size','20'))
        if size>100: raise ValueError()
        status=request.args.get('status','all')
        if status not in ('all','active','overdue','returned'): raise ValueError()
    except (ValueError,TypeError): return fail(422,'Неверные параметры')
    clause={'all':'TRUE','active':'returned_on IS NULL','overdue':'returned_on IS NULL AND due_on<CURRENT_DATE','returned':'returned_on IS NOT NULL'}[status]
    with DB() as db:
        total=db.query('SELECT count(*) AS n FROM loans WHERE '+clause)[0]['n']
        items=db.query('SELECT * FROM loans WHERE '+clause+' ORDER BY id DESC LIMIT %s OFFSET %s',(size,(page-1)*size))
        record(db)
    return jsonify(items=items,total=total,page=page,size=size)

@app.get('/api/loans/<int:loan_id>')
def detail(loan_id):
    with DB() as db:
        rows=db.query('''SELECT l.*,r.name AS reader,b.title AS book,c.book_id
          FROM loans l JOIN readers r ON r.id=l.reader_id JOIN copies c ON c.id=l.copy_id
          JOIN books b ON b.id=c.book_id WHERE l.id=%s''',(loan_id,));record(db)
    if not rows: return fail(404,'Выдача не найдена')
    row=rows[0];row['fine_rub']=fine(row['due_on'],row['returned_on'])
    return jsonify(row)

@app.get('/api/summary')
def summary():
    with DB() as db:
        totals=db.query('''SELECT count(*) FILTER(WHERE returned_on IS NULL) AS on_hands,
          count(*) FILTER(WHERE returned_on IS NULL AND due_on<CURRENT_DATE) AS overdue FROM loans''')[0]
        top=db.query('''SELECT b.id,b.title,count(*) AS issued FROM loans l JOIN copies c ON c.id=l.copy_id
          JOIN books b ON b.id=c.book_id GROUP BY b.id,b.title ORDER BY issued DESC,b.id LIMIT 10''')
        record(db)
    return jsonify(**totals,top_books=top)

@app.post('/api/loans')
def issue():
    try:
        data=request.get_json(silent=True) or {}
        reader=positive(data.get('reader_id'));copy=positive(data.get('copy_id'))
        days=positive(data.get('days',14))
        if days>60: raise ValueError()
    except (TypeError,ValueError): return fail(422,'Неверные параметры')
    with DB() as db:
        # Lock reader first in all issue paths: prevents races with another issue for this reader.
        readers=db.query('SELECT id FROM readers WHERE id=%s FOR UPDATE',(reader,))
        copies=db.query('SELECT id FROM copies WHERE id=%s FOR UPDATE',(copy,))
        if not readers or not copies: record(db);return fail(404,'Читатель или экземпляр не найден')
        busy=db.query('SELECT id FROM loans WHERE copy_id=%s AND returned_on IS NULL LIMIT 1',(copy,))
        overdue=db.query('SELECT id FROM loans WHERE reader_id=%s AND returned_on IS NULL AND due_on<CURRENT_DATE LIMIT 1',(reader,))
        if busy or overdue: record(db);return fail(409,'Экземпляр занят или есть просрочка')
        rows=db.query('INSERT INTO loans(reader_id,copy_id,issued_on,due_on) VALUES(%s,%s,CURRENT_DATE,CURRENT_DATE+%s) RETURNING *',(reader,copy,days));record(db)
    return jsonify(rows[0]),201

@app.post('/api/loans/<int:loan_id>/return')
def return_loan(loan_id):
    with DB() as db:
        rows=db.query('SELECT * FROM loans WHERE id=%s FOR UPDATE',(loan_id,))
        if not rows: record(db);return fail(404,'Выдача не найдена')
        row=rows[0]
        if row['returned_on']: record(db);return fail(409,'Уже возвращено')
        row=db.query('UPDATE loans SET returned_on=CURRENT_DATE WHERE id=%s RETURNING *',(loan_id,))[0];record(db)
    row['fine_rub']=fine(row['due_on'],row['returned_on'])
    return jsonify(row)

@app.get('/')
def index():
    return app.send_static_file('index.html')

if __name__=='__main__': app.run(host='0.0.0.0',port=8000,threaded=True)
