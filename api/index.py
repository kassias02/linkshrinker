import os
from flask import Flask, request, redirect, render_template_string
import random
import string
import requests
from bs4 import BeautifulSoup
import json
import sqlite3

app = Flask(__name__)

INDEX_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Shrink long URLs instantly with LinkShrinker. Fast, free, and reliable link shortener with preview.">
    <meta name="keywords" content="best URL shortener, free link shrinker, shorten URL, link preview, fast URL shortener">
    <meta name="author" content="LinkShrinker Team">
    <meta name="robots" content="index, follow">
    <title>LinkShrinker - Free URL Shortener</title>
    <link rel="icon" href="https://via.placeholder.com/32?text=LS" type="image/png">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #6dd5fa, #2980b9);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.9);
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            width: 90%;
            max-width: 500px;
            text-align: center;
        }
        h1 {
            color: #2c3e50;
            font-size: 32px;
            margin-bottom: 10px;
        }
        p {
            color: #7f8c8d;
            font-size: 16px;
            margin-bottom: 20px;
        }
        input[type="url"], input[type="text"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-sizing: border-box;
        }
        button {
            background-color: #3498db;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #2980b9;
        }
        .error {
            color: #e74c3c;
            font-weight: bold;
            margin-top: 10px;
        }
        .stats {
            color: #7f8c8d;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>LinkShrinker</h1>
        <p>Shorten your URLs for free with a preview you can trust!</p>
        <form method="post">
            <input type="url" name="url" placeholder="Paste your long URL here" required>
            <input type="text" name="alias" placeholder="Custom alias (optional)">
            <button type="submit">Shrink It</button>
        </form>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        <p class="stats">Links shortened: {{ visitor_count }}</p>
    </div>
</body>
</html>
'''

RESULT_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Your shortened URL from LinkShrinker. Fast, free, and reliable with a preview.">
    <meta name="keywords" content="best URL shortener, free link shrinker, shorten URL, link preview">
    <meta name="author" content="LinkShrinker Team">
    <meta name="robots" content="index, follow">
    <title>Your Short Link - LinkShrinker</title>
    <link rel="icon" href="https://via.placeholder.com/32?text=LS" type="image/png">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #6dd5fa, #2980b9);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.9);
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            width: 90%;
            max-width: 500px;
            text-align: center;
        }
        h1 {
            color: #2c3e50;
            font-size: 28px;
            margin-bottom: 20px;
        }
        .short-link {
            background: #ecf0f1;
            padding: 10px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 20px;
        }
        a {
            color: #3498db;
            text-decoration: none;
            font-size: 18px;
        }
        a:hover {
            text-decoration: underline;
        }
        button {
            background-color: #3498db;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            margin: 5px;
            font-size: 14px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #2980b9;
        }
        .tooltip {
            position: relative;
            display: inline-block;
        }
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 300px;
            background-color: white;
            color: #333;
            text-align: left;
            border-radius: 8px;
            padding: 15px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -150px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            opacity: 0;
            transition: opacity 0.3s;
        }
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        .tooltiptext img {
            max-width: 100%;
            border-radius: 4px;
        }
        .share-options {
            display: none;
            margin-top: 10px;
        }
        .share-options button {
            background-color: #ecf0f1;
            color: #333;
            padding: 8px;
            margin: 5px;
        }
        .share-options button:hover {
            background-color: #dcdcdc;
        }
    </style>
    <script>
        function copyToClipboard() {
            navigator.clipboard.writeText("{{ short_url }}");
            alert("Link copied to clipboard!");
        }
        function toggleShareOptions() {
            var options = document.getElementById("share-options");
            options.style.display = options.style.display === "block" ? "none" : "block";
        }
        function shareTo(platform) {
            var url = "{{ short_url }}";
            var shareUrl;
            if (platform === "twitter") shareUrl = "https://twitter.com/intent/tweet?url=" + encodeURIComponent(url);
            else if (platform === "facebook") shareUrl = "https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(url);
            else if (platform === "linkedin") shareUrl = "https://www.linkedin.com/shareArticle?url=" + encodeURIComponent(url);
            window.open(shareUrl, "_blank", "width=600,height=400");
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>Your Short Link</h1>
        <div class="short-link tooltip">
            <a href="{{ short_url }}">{{ short_url }}</a>
            <div class="tooltiptext">
                <p><strong>Title:</strong> {{ preview.title }}</p>
                <p><strong>Description:</strong> {{ preview.description }}</p>
                {% if preview.image %}
                    <img src="{{ preview.image }}" alt="Preview Image">
                {% else %}
                    <img src="https://via.placeholder.com/150?text=No+Image" alt="No Image">
                {% endif %}
                {% if preview.error %}
                    <p style="color: #e74c3c;">Error: {{ preview.error }}</p>
                {% endif %}
            </div>
        </div>
        <div>
            <button onclick="copyToClipboard()">Copy</button>
            <button onclick="toggleShareOptions()">Share</button>
        </div>
        <div id="share-options" class="share-options">
            <button onclick="shareTo('twitter')">Twitter</button>
            <button onclick="shareTo('facebook')">Facebook</button>
            <button onclick="shareTo('linkedin')">LinkedIn</button>
        </div>
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
                     (short_code TEXT PRIMARY KEY, url TEXT, preview TEXT, visits INTEGER DEFAULT 0)''')
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"DB init failed: {e}")
    finally:
        conn.close()

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def get_visitor_count():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM links")
    count = c.fetchone()[0]
    conn.close()
    return count

# Initialize DB on first request
if not os.path.exists(DB_PATH):
    init_db()

def generate_short_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_preview_data(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; LinkShrinker/1.0)'}
        response = requests.get(url, timeout=5, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.find('meta', attrs={'property': 'og:title'})
        title = title['content'].strip() if title else soup.title.string.strip() if soup.title else "No Title"
        if len(title) > 100:
            title = title[:97] + "..."

        desc = soup.find('meta', attrs={'property': 'og:description'})
        if not desc:
            desc = soup.find('meta', attrs={'name': 'description'})
        desc = desc['content'].strip() if desc else soup.find('p').text.strip() if soup.find('p') else "No description available"
        if len(desc) > 200:
            desc = desc[:197] + "..."

        img = soup.find('meta', attrs={'property': 'og:image'})
        img = img['content'] if img else (soup.find('img')['src'] if soup.find('img') else None)

        return {'title': title, 'description': desc, 'image': img, 'error': None}
    except requests.RequestException as e:
        error_msg = f"Failed to fetch: {str(e)}"
        print(error_msg)
        return {'title': 'Error', 'description': 'Unable to load preview', 'image': None, 'error': error_msg}
    except Exception as e:
        error_msg = f"Parsing error: {str(e)}"
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
                return render_template_string(INDEX_HTML, error="Alias already taken!", visitor_count=get_visitor_count())
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
    return render_template_string(INDEX_HTML, visitor_count=get_visitor_count())

@app.route('/<short_code>')
def redirect_link(short_code):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT url FROM links WHERE short_code = ?", (short_code,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE links SET visits = visits + 1 WHERE short_code = ?", (short_code,))
        conn.commit()
        conn.close()
        return redirect(result[0], code=302)
    conn.close()
    return "Link not found", 404