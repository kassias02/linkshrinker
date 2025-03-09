import os
from flask import Flask, request, redirect, render_template_string
import random
import string
import requests
from bs4 import BeautifulSoup
import json
import sqlite3

app = Flask(__name__)

# Inline templates with corrected colors and styling
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>LinkShrinker</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #e0f7fa; }
        h1 { color: #333; font-weight: bold; }
        input[type="url"], input[type="text"] { padding: 8px; margin: 5px; width: 250px; }
        button { padding: 8px 16px; background-color: #00ff00; color: #000; border: none; cursor: pointer; }
        button:hover { background-color: #00cc00; }
        .error { color: #ff0000; font-weight: bold; }
    </style>
</head>
<body>
    <h1>LinkShrinker</h1>
    <form method="post">
        <input type="url" name="url" placeholder="Enter URL" required>
        <br>
        <input type="text" name="alias" placeholder="Custom Alias (optional)">
        <br>
        <button type="submit">Shrink</button>
    </form>
    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}
</body>
</html>
'''

RESULT_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Shortened URL</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #e0f7fa; }
        h1 { color: #333; font-weight: bold; }
        a { color: #0000ff; text-decoration: none; font-size: 18px; }
        a:hover { text-decoration: underline; }
        .preview { margin-top: 20px; }
        .preview img { max-width: 300px; }
        button { padding: 8px 16px; background-color: #00ff00; color: #000; border: none; cursor: pointer; }
        button:hover { background-color: #00cc00; }
    </style>
    <script>
        function copyToClipboard() {
            navigator.clipboard.writeText("{{ short_url }}");
            alert("Copied to clipboard!");
        }
    </script>
</head>
<body>
    <h1>Your Shortened URL</h1>
    <p><a href="{{ short_url }}" target="_blank">{{ short_url }}</a></p>
    <button onclick="copyToClipboard()">Share</button>
    <div class="preview">
        <p><strong>Title:</strong> {{ preview.title }}</p>
        <p><strong>Description:</strong> {{ preview.description }}</p>
        {% if preview.image %}
            <img src="{{ preview.image }}" alt="Preview Image">
        {% endif %}
    </div>
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
        title = soup.title.string.strip() if soup.title else "No Title"
        desc = soup.find('meta', attrs={'name': 'description'})
        desc = desc['content'].strip() if desc else "No description available"
        img = soup.find('meta', attrs={'property': 'og:image'})
        img = img['content'] if img else None
        return {'title': title, 'description': desc, 'image': img}
    except Exception as e:
        print(f"Preview error: {e}")
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