import os
from flask import Flask, request, redirect, render_template_string
import random
import string
import requests
from bs4 import BeautifulSoup
import json
import sqlite3

app = Flask(__name__)

# Inline templates with improved preview
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
        .preview { margin-top: 20px; max-width: 500px; margin-left: auto; margin-right: auto; }
        .preview img { max-width: 300px; border: 1px solid #ccc; }
        .preview p { margin: 5px 0; word-wrap: break-word; }
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
        {% else %}
            <img src="https://via.placeholder.com/150?text=No+Image" alt="No Image Available">
        {% endif %}
        {% if preview.error %}
            <p style="color: #ff0000;">Preview Error: {{ preview.error }}</p>
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
        # Set a user-agent to avoid blocks
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; LinkShrinker/1.0)'}
        response = requests.get(url, timeout=5, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        soup = BeautifulSoup(response.text, 'html.parser')

        # Title: OG or HTML fallback
        title = soup.find('meta', attrs={'property': 'og:title'})
        title = title['content'].strip() if title else soup.title.string.strip() if soup.title else "No Title"
        if len(title) > 100:
            title = title[:97] + "..."

        # Description: OG, meta, or first paragraph
        desc = soup.find('meta', attrs={'property': 'og:description'})
        if not desc:
            desc = soup.find('meta', attrs={'name': 'description'})
        if desc:
            desc = desc['content'].strip()
        else:
            p = soup.find('p')
            desc = p.text.strip() if p else "No description available"
        if len(desc) > 200:
            desc = desc[:197] + "..."

        # Image: OG or first img tag
        img = soup.find('meta', attrs={'property': 'og:image'})
        if img:
            img = img['content']
        else:
            img_tag = soup.find('img')
            img = img_tag['src'] if img_tag else None

        return {'title': title, 'description': desc, 'image': img, 'error': None}
    except requests.RequestException as e:
        error_msg = f"Failed to fetch preview: {str(e)}"
        print(error_msg)
        return {'title': 'Error', 'description': 'Unable to load preview', 'image': None, 'error': error_msg}
    except Exception as e:
        error_msg = f"Preview parsing error: {str(e)}"
        print(error_msg)
        return {'title': 'Error', 'description': 'Unable to load preview', 'image': None, 'error': error_msg}

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