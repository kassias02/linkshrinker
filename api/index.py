import os
from flask import Flask, request, redirect, render_template_string
import random
import string
import requests
from bs4 import BeautifulSoup
import json
import sqlite3

app = Flask(__name__)

# Inline templates
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>LinkShrinker</title>
</head>
<body>
    <h1>LinkShrinker</h1>
    <form method="post">
        <input type="url" name="url" placeholder="Enter URL" required>
        <input type="text" name="alias" placeholder="Custom Alias (optional)">
        <button type="submit">Shrink</button>
    </form>
    {% if error %}
        <p style="color: red;">{{ error }}</p>
    {% endif %}
</body>
</html>
'''

RESULT_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Shortened URL</title>
</head>
<body>
    <h1>Your Shortened URL</h1>
    <p><a href="{{ short_url }}" target="_blank">{{ short_url }}</a></p>
    <p>Preview: {{ preview.title }}</p>
</body>
</html>
'''

DB_PATH = '/tmp/links.db'

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS links 
                     (short_code TEXT PRIMARY KEY, url TEXT, preview TEXT)''')
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"DB init failed: {e}")
    finally:
        conn.close()

def get_db_connection():
    return sqlite3.connect(DB_PATH)

# Initialize DB on first request
if not os.path.exists(DB_PATH):
    init_db()

def generate_short_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_preview_data(url):
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else "No Title"
        desc = soup.find('meta', attrs={'name': 'description'})['content'] if soup.find('meta', attrs={'name': 'description'}) else "No description"
        img = soup.find('meta', attrs={'property': 'og:image'})['content'] if soup.find('meta', attrs={'property': 'og:image'}) else None
        return {'title': title, 'description': desc, 'image': img}
    except Exception:
        return {'title': 'Error', 'description': 'Unable to load preview', 'image': None}

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        long_url = request.form['url']
        alias = request.form.get('alias', '').strip()
        conn = get_db_connection()
        c = conn.cursor()
        if alias:
            c.execute("SELECT short_code FROM links WHERE short_code = ?", (alias,))
            if c.fetchone():
                conn.close()
                return render_template_string(INDEX_HTML, error="Alias already taken!")
            short_code = alias
        else:
            short_code = generate_short_code()
            c.execute("SELECT short_code FROM links WHERE short_code = ?", (short_code,))
            while c.fetchone():
                short_code = generate_short_code()
                c.execute("SELECT short_code FROM links WHERE short_code = ?", (short_code,))
        preview = get_preview_data(long_url)
        preview_json = json.dumps(preview)
        c.execute("INSERT OR IGNORE INTO links (short_code, url, preview) VALUES (?, ?, ?)", 
                  (short_code, long_url, preview_json))
        conn.commit()
        conn.close()
        short_url = f"https://{request.host}/{short_code}"
        return render_template_string(RESULT_HTML, short_url=short_url, preview=preview)
    return render_template_string(INDEX_HTML)

@app.route('/<short_code>')
def redirect_link(short_code):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT url FROM links WHERE short_code = ?", (short_code,))
    result = c.fetchone()
    conn.close()
    if result:
        return redirect(result[0], code=302)
    return "Link not found", 404

# Vercel requires this to be named `app` for Python deployments
if __name__ == '__main__':
    app.run(debug=True)