from flask import Flask, 
request, redirect, render_template
import random
import string
import requests
from bs4 import BeautifulSoup
import json
import sqlite3

app = Flask(__name__, template_folder='templates')

DB_PATH = 'links.db'  # Ephemeral on Vercel

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS links 
                 (short_code TEXT PRIMARY KEY, url TEXT, preview TEXT)''')
    conn.commit()
    conn.close()

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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if alias:
            c.execute("SELECT short_code FROM links WHERE short_code = ?", (alias,))
            if c.fetchone():
                conn.close()
                return render_template('index.html', error="Alias already taken!")
            short_code = alias
        else:
            short_code = generate_short_code()
            c.execute("SELECT short_code FROM links WHERE short_code = ?", (short_code,))
            while c.fetchone():
                short_code = generate_short_code()
                c.execute("SELECT short_code FROM links WHERE short_code = ?", (short_code,))
        preview = get_preview_data(long_url)
        preview_json = json.dumps(preview)
        c.execute("INSERT INTO links (short_code, url, preview) VALUES (?, ?, ?)", 
                  (short_code, long_url, preview_json))
        conn.commit()
        conn.close()
        short_url = f"https://{request.host}/{short_code}"
        return render_template('result.html', short_url=short_url, preview=preview, preview_json=preview_json)
    return render_template('index.html')

@app.route('/<short_code>')
def redirect_link(short_code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT url FROM links WHERE short_code = ?", (short_code,))
    result = c.fetchone()
    conn.close()
    if result:
        return redirect(result[0], code=302)
    return "Link not found", 404

# Vercel serverless handler
def handler(request):
    return app(request.environ, lambda status, headers: request.send_response(status, headers))
