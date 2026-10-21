import sqlite3, threading

class Store:
    def __init__(s, path):
        s.c = sqlite3.connect(path, check_same_thread=False); s.l = threading.Lock()
        s.q("create table if not exists rates(metal text,ts real,buy real,sell real,src text)")
        s.q("create index if not exists i1 on rates(metal,ts)")
        s.q("create table if not exists ops(id integer primary key,metal text,ts real,kind text,grams real,total real)")

    def q(s, sql, a=()):
        with s.l:
            r = s.c.execute(sql, a).fetchall(); s.c.commit(); return r

    def add_rate(s, m, ts, b, sl, src):
        last = s.q("select ts,buy,sell from rates where metal=? order by ts desc limit 1", (m,))
        if last and last[0][1:] == (b, sl) and ts - last[0][0] < 600:
            return
        s.q("insert into rates values(?,?,?,?,?)", (m, ts, b, sl, src))

    def add_many(s, rows):
        with s.l:
            s.c.executemany("insert into rates values(?,?,?,?,?)", rows); s.c.commit()

    def latest(s, m):
        r = s.q("select ts,buy,sell,src from rates where metal=? order by ts desc limit 1", (m,))
        return dict(zip(("ts", "buy", "sell", "src"), r[0])) if r else None

    def history(s, m, a, b, cap=500):
        rows = s.q("select ts,buy,sell from rates where metal=? and ts between ? and ? order by ts", (m, a, b))
        k = max(1, len(rows) // cap)
        out = rows[::k]
        if rows and out[-1] != rows[-1]:
            out.append(rows[-1])
        return out

    def has_cbr(s):
        return bool(s.q("select 1 from rates where src='cbr' limit 1"))

    def ops(s, m):
        return [dict(zip(("id", "ts", "kind", "grams", "total"), r))
                for r in s.q("select id,ts,kind,grams,total from ops where metal=? order by ts desc", (m,))]
