import sqlite3
import os

try:
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    c.execute("SELECT auth_user.username FROM auth_user INNER JOIN api_profile ON auth_user.id = api_profile.user_id WHERE api_profile.role='THEATRE_ADMIN'")
    admins = c.fetchall()
    print("Theatre Admins:", admins)
except Exception as e:
    print(e)
