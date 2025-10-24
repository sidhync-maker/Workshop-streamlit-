# app.py
import streamlit as st
import sqlite3
from datetime import date, datetime
import pandas as pd
import hashlib
import io

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
    # users: username (unique), password_hash, role ('manager' or 'mechanic')
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

    # Ensure a default manager account exists
    c.execute("SELECT * FROM users WHERE role='manager'")
    if c.fetchone() is None:
        default_user = 'manager'
        default_pass = 'admin123'  # change after first login
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
    # update stock
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

# ----------------- Utilities -----------------

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
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        if st.button('Login'):
            user = get_user(username)
            if user and verify_password(password, user['password_hash']):
                st.session_state.user = dict(user)
                st.success(f"Logged in as {username} ({user['role']})")
                st.experimental_rerun()
            else:
                st.error('Invalid credentials')
    else:
        st.markdown(f"**Signed in:** {st.session_state.user['username']}  \nRole: {st.session_state.user['role']}")
        if st.button('Logout'):
            st.session_state.user = None
            st.experimental_rerun()

# If not logged in, show public info and stop
if st.session_state.user is None:
    st.info('Please log in from the sidebar. Default manager: username `manager`, password `admin123`. Change it after first login.')
    st.stop()

role = st.session_state.user['role']
username = st.session_state.user['username']

# Manager-only: user management
if role == 'manager':
    st.sidebar.header('Manager')
    st.sidebar.write('Add mechanic user')
    with st.sidebar.form('add_mech'):
        new_user = st.text_input('Mechanic username')
        new_pass = st.text_input('Password', type='password')
        add_sub = st.form_submit_button('Add')
        if add_sub:
            if new_user and new_pass:
                ok = create_user(new_user, new_pass, 'mechanic')
                if ok:
                    st.sidebar.success('Mechanic added')
                else:
                    st.sidebar.error('Username already exists')
            else:
                st.sidebar.error('Enter username and password')

# Main navigation
pages = ['Home', 'Purchase', 'Stock', 'Billing', 'Mechanics', 'Car Models', 'Export/Import']
# Mechanics role sees limited menu
if role == 'mechanic':
    pages = ['Home', 'Mechanics']

page = st.sidebar.selectbox('Module', pages)

# --- HOME ---
if page == 'Home':
    st.header('Dashboard')
    if role == 'manager':
        st.subheader('Quick stats')
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric('Purchases', len(list_purchases()))
        with col2:
            st.metric('Stock Items', len(list_stock()))
        with col3:
            st.metric('Billing Records', len(list_billing()))

# --- PURCHASE ---
elif page == 'Purchase':
    st.header('Purchase Entry (Manager only)')
    if role != 'manager':
        st.error('Access denied')
        st.stop()

    with st.form('purchase_form'):
        item_code = st.text_input('Item Code')
        item_name = st.text_input('Item Name')
        qty = st.number_input('Quantity', min_value=1, step=1, value=1)
        rate = st.number_input('Rate / Unit', min_value=0.0, step=0.1, value=0.0)
        sub = st.form_submit_button('Add Purchase')
        if sub:
            if item_code and item_name and qty > 0:
                add_purchase(item_code, item_name, int(qty), float(rate))
                st.success('Purchase added and stock updated')
            else:
                st.error('Fill fields')

    st.subheader('Purchase History')
    st.dataframe(list_purchases())

# --- STOCK ---
elif page == 'Stock':
    st.header('Stock List')
    if role != 'manager':
        st.error('Access denied')
        st.stop()
    st.dataframe(list_stock())

# --- BILLING ---
elif page == 'Billing':
    st.header('Billing (Manager only)')
    if role != 'manager':
        st.error('Access denied')
        st.stop()

    car_models = list_car_models()['model'].tolist()
    with st.form('billing_form'):
        car_model = st.selectbox('Car Model', options=car_models or ['-- add models first --'])
        complaints = st.text_area('Complaints / Work Details')
        start_date = st.date_input('Work Start Date', value=date.today())
        end_date = st.date_input('Work Completed Date', value=date.today())
        labour = st.number_input('Labour Charge', min_value=0.0, step=10.0)
        # choose purchase items to include in billing
        purchases_df = list_purchases()
        picks = []
        purchase_amt = 0.0
        if not purchases_df.empty:
            picks = st.multiselect('Select Purchases to include (by id)', options=purchases_df['id'].tolist())
            if picks:
                selected = purchases_df[purchases_df['id'].isin(picks)]
                st.table(selected[['item_name','qty','rate','total']])
                purchase_amt = float(selected['total'].sum())
        sub = st.form_submit_button('Generate Bill')
        if sub:
            if car_model and (car_model != '-- add models first --'):
                total = add_billing(car_model, complaints, str(start_date), str(end_date), float(labour), purchase_amt)
                st.success(f'Bill generated — Total: ₹{total:.2f}')
            else:
                st.error('Select a car model first')

    st.subheader('Billing Records')
    st.dataframe(list_billing())

# --- MECHANICS ---
elif page == 'Mechanics':
    st.header('Mechanic Daily Activity')
    if role == 'mechanic':
        st.subheader(f'Welcome, {username}')
        with st.form('mech_form'):
            work_date = st.date_input('Date', value=date.today())
            activity = st.text_area("Today's Activity")
            earning = st.number_input('Earnings (₹)', min_value=0.0, step=10.0)
            sub = st.form_submit_button('Add')
            if sub:
                add_mechanic_entry(username, str(work_date), activity, float(earning))
                st.success('Added')
        st.subheader('Your Entries')
        st.dataframe(list_mechanics_entries(username))

    elif role == 'manager':
        st.subheader('All Mechanics — Manager View')
        # add quick filter by mechanic
        conn = get_conn()
        users = pd.read_sql_query(\"SELECT username FROM users WHERE role='mechanic'\", conn)
        conn.close()
        mech_list = users['username'].tolist()
        filt = st.selectbox('Filter by mechanic', options=['All'] + mech_list)
        if filt == 'All':
            df = list_mechanics_entries()
        else:
            df = list_mechanics_entries(filt)
        st.dataframe(df)
        # show earnings summary
        if not df.empty:
            st.write('Earnings summary')
            summary = df.groupby('username').earning.sum().reset_index()
            st.dataframe(summary)

# --- CAR MODELS ---
elif page == 'Car Models':
    st.header('Car Models (Manager only)')
    if role != 'manager':
        st.error('Access denied')
        st.stop()
    with st.form('car_model_form'):
        model = st.text_input('Model name')
        addm = st.form_submit_button('Add Model')
        if addm and model:
            add_car_model(model)
            st.success('Added')
    st.dataframe(list_car_models())

# --- EXPORT / IMPORT ---
elif page == 'Export/Import':
    st.header('Export / Import Data')
    if role != 'manager':
        st.error('Access denied')
        st.stop()

    st.subheader('Export CSV')
    if st.button('Export Purchases'):
        df = list_purchases()
        st.download_button('Download purchases.csv', data=df_to_csv_bytes(df), file_name='purchases.csv')
    if st.button('Export Stock'):
        df = list_stock()
        st.download_button('Download stock.csv', data=df_to_csv_bytes(df), file_name='stock.csv')
    if st.button('Export Billing'):
        df = list_billing()
        st.download_button('Download billing.csv', data=df_to_csv_bytes(df), file_name='billing.csv')
    if st.button('Export Mechanics'):
        df = list_mechanics_entries()
        st.download_button('Download mechanics.csv', data=df_to_csv_bytes(df), file_name='mechanics.csv')

    st.subheader('Import CSV into Purchases (append)')
    uploaded = st.file_uploader('Upload purchases CSV', type=['csv'])
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        st.write('Preview')
        st.dataframe(df.head())
        if st.button('Append to purchases'):
            for _, row in df.iterrows():
                try:
                    add_purchase(row['item_code'], row['item_name'], int(row['qty']), float(row['rate']))
                except Exception as e:
                    st.error(f'Error: {e}')
            st.success('Imported')

# ----------------- end app -----------------
