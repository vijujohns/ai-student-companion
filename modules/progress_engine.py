
import sqlite3

conn=sqlite3.connect("progress.db",check_same_thread=False)
cur=conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS progress(
topic TEXT,
correct INTEGER,
wrong INTEGER
)
""")

conn.commit()

def update_progress(topic,correct):
    cur.execute("SELECT * FROM progress WHERE topic=?",(topic,))
    row=cur.fetchone()
    if row is None:
        if correct:
            cur.execute("INSERT INTO progress VALUES(?,?,?)",(topic,1,0))
        else:
            cur.execute("INSERT INTO progress VALUES(?,?,?)",(topic,0,1))
    else:
        c=row[1]
        w=row[2]
        if correct:
            c+=1
        else:
            w+=1
        cur.execute("UPDATE progress SET correct=?,wrong=? WHERE topic=?",(c,w,topic))
    conn.commit()

def get_progress():
    cur.execute("SELECT * FROM progress")
    return cur.fetchall()
