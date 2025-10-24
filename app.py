# app.py
import streamlit as st
import sqlite3
from datetime import date, datetime
import pandas as pd
import hashlib

DB_PATH = 'workshop.db'

# ----------------- Database helpers -----------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY,
            item_code TEXT,
            item_name TEXT,
            qty INTEGER,
            rate REAL,
            total REAL,
            purchased_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY,
            item_code TEXT UNIQUE,
            item_name TEXT,
            qty INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY,
            car_model TEXT,
            complaints TEXT,
            start_date TEXT,
            end_date TEXT,
            labour REAL,
            purchase_amt REAL,
            total REAL,
            billed_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS mechanics (
            id INTEGER PRIMARY KEY,
            username TEXT,
            work_date TEXT,
            activity TEXT,
            earning REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS car_models (
            id INTEGER PRIMARY KEY,
            model TEXT UNIQUE
        )
    ''')
    conn.commit()
    c.execute("SELECT * FROM users WHERE role='manager'")
    if c.fetchone() is None:
        default_user = 'manager'
        default_pass = 'admin123'
        phash = hash_password(default_pass)
        c.execute('INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
                  (default_user, phash, 'manager', datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

# ----------------- Auth helpers -----------------
def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def get_user(username: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(username: str, password: str, role: str = 'mechanic'):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
                  (username, hash_password(password), role, datetime.utcnow().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False
    conn.close()
    return True

# ----------------- Business logic -----------------
def add_purchase(item_code, item_name, qty, rate):
    total = qty * rate
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO purchases (item_code, item_name, qty, rate, total, purchased_at) VALUES (?, ?, ?, ?, ?, ?)',
              (item_code, item_name, qty, rate, total, datetime.utcnow().isoformat()))
    c.execute('SELECT * FROM stock WHERE item_code = ?', (item_code,))
    row = c.fetchone()
    if row:
        new_qty = row['qty'] + qty
        c.execute('UPDATE stock SET qty = ? WHERE item_code = ?', (new_qty, item_code))
    else:
        c.execute('INSERT INTO stock (item_code, item_name, qty) VALUES (?, ?, ?)', (item_code, item_name, qty))
    conn.commit()
    conn.close()

def list_purchases():
    conn = get_conn()
    df = pd.read_sql_query('SELECT * FROM purchases ORDER BY purchased_at DESC', conn)
    conn.close()
    return df

def list_stock():
    conn = get_conn()
    df = pd.read_sql_query('SELECT * FROM stock', conn)
    conn.close()
    return df

def add_billing(car_model, complaints, start_date, end_date, labour, purchase_amt):
    total = labour + purchase_amt
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO billing (car_model, complaints, start_date, end_date, labour, purchase_amt, total, billed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (car_model, complaints, start_date, end_date, labour, purchase_amt, total, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return total

def list_billing():
    conn = get_conn()
    df = pd.read_sql_query('SELECT * FROM billing ORDER BY billed_at DESC', conn)
    conn.close()
    return df

def add_mechanic_entry(username, work_date, activity, earning):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO mechanics (username, work_date, activity, earning) VALUES (?, ?, ?, ?)',
              (username, work_date, activity, earning))
    conn.commit()
    conn.close()

def list_mechanics_entries(username=None):
    conn = get_conn()
    if username:
        df = pd.read_sql_query('SELECT * FROM mechanics WHERE username = ? ORDER BY work_date DESC', conn, params=(username,))
    else:
        df = pd.read_sql_query('SELECT * FROM mechanics ORDER BY work_date DESC', conn)
    conn.close()
    return df

def add_car_model(model_name):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO car_models (model) VALUES (?)', (model_name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def list_car_models():
    conn = get_conn()
    df = pd.read_sql_query('SELECT * FROM car_models', conn)
    conn.close()
    return df

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode('utf-8')

# ----------------- App UI -----------------
st.set_page_config(page_title='Workshop Manager', layout='wide')
init_db()

if 'user' not in st.session_state:
    st.session_state.user = None

st.title('Workshop Management — Multi-user')

# --- Authentication ---
with st.sidebar:
    st.header('Login')
    if st.session_state.user is None:
        username_input = st.text_input('Username')
        password_input = st.text_input('Password', type='password')
        login_btn = st.button('Login')
        if login_btn:
            user = get_user(username_input)
            if user and verify_password(password_input, user['password_hash']):
                st.session_state.user = dict(user)
                st.success(f"Logged in as {username_input} ({user['role']})")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")
    else:
        st.markdown(f"**Signed in:** {st.session_state.user['username']}  \nRole: {st.session_state.user['role']}")
        if st.button('Logout'):
            st.session_state.user = None
            st.experimental_rerun()

# The rest of the modules (Purchase, Stock, Billing, Mechanics, Car Models) can be included as-is
# from previous code.
