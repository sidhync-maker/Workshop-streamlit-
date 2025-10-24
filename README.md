# Workshop Management Streamlit App

This is a Streamlit web app for managing a small vehicle workshop.
It includes modules for purchases, stock, billing, mechanics, and car models,
with a manager account and multiple mechanics users. Data is stored in SQLite.

## Files
- app.py        : main Streamlit app
- requirements.txt : Python dependencies
- workshop.db   : created automatically after first run (SQLite DB)

## Run locally
1. (Optional) Create and activate a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```
4. Open the URL Streamlit prints (usually http://localhost:8501)

## Default manager account
- username: `manager`
- password: `admin123`

Please change this password after first login. For production use, secure the app and database properly.

## Notes
- Passwords are hashed with SHA-256. For stronger security consider using bcrypt.
- The SQLite file `workshop.db` will be created in the project folder.
