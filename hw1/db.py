import os, re, time
import psycopg
from psycopg.rows import dict_row

class DB:
    def __enter__(self):
        prefix = os.environ['PERSONAL_PREFIX']
        if not re.fullmatch(r'[a-z][a-z_]{1,62}', prefix):
            raise ValueError('Invalid PERSONAL_PREFIX')
        self.conn = psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row)
        self.conn.execute(f'SET search_path TO "{prefix}"')
        self.ms = 0.0
        self.count = 0
        return self
    def query(self, sql, params=()):
        start = time.perf_counter()
        try:
            cur = self.conn.execute(sql, params)
            return cur.fetchall() if cur.description else []
        finally:
            self.ms += (time.perf_counter() - start) * 1000
            self.count += 1
    def __exit__(self, typ, value, tb):
        try:
            self.conn.rollback() if typ else self.conn.commit()
        finally:
            self.conn.close()
