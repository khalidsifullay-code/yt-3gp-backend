import os
import re
import json
import urllib.parse
import urllib.request
import subprocess
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# একাধিক অল্টারনেটিভ প্রক্সি সার্ভার লিস্ট (একটি ফেল করলে অন্যটি কাজ করবে)
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.privacydev.net",
    "https://pipedapi.mha.fi",
    "https://pipedapi.tokhmi.xyz"
]

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://yewtu.be",
    "https://invidious.nerdvpn.de",
    "https://invidious.privacydev.net"
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>YouTube Lite (3GP)</title>
    <style>
        body { font-family: sans-serif; font-size: 12px; margin: 5px; padding: 0; background: #fff; color: #000; }
        input, button { font-size: 12px; margin: 2px 0; }
        .item { border-bottom: 1px solid #ccc; padding: 6px 0; margin-bottom: 5px; }
        a { color: blue; text-decoration: underline; font-weight: bold; }
        .msg { color: green; font-weight: bold; }
    </style>
</head>
<body>
    <h3>YouTube Lite (3GP)</h3>
    <form action="/" method="GET">
        <input type="text" name="q" value="{{ query }}" placeholder="ভিডিও নাম লিখুন...">
        <button type="submit">Search</button>
    </form>
    <hr>
    {% if query %}
        {% if results %}
            {% for item in results %}
            <div class="item">
                <b>{{ item.title }}</b><br>
                <a href="/download?id={{ item.id }}">[ Download 3GP ]</a>
            </div>
            {% endfor %}
        {% else %}
            <p>কোনো ভিডিও পাওয়া যায়নি। অন্য কিছু লিখে চেষ্টা করুন।</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

# মাল্টি-সোর্স সার্চ ফাংশন
def search_videos(query):
    encoded = urllib.parse.quote(query)
    results = []

    # ১. Piped API দিয়ে সার্চ চেষ্টা
    for instance in PIPED_INSTANCES:
        try:
            url = f"{instance}/search?q={encoded}&filter=all"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                items = data.get('items', [])
                for item in items:
                    if item.get('type') == 'stream':
                        v_id = item.get('url', '').replace('/watch?v=', '')
                        if v_id:
                            results.append({'id': v_id, 'title': item.get('title')})
                    if len(results) >= 6:
                        break
                if results:
                    return results
        except Exception as e:
            print(f"Piped Search error on {instance}: {e}")

    # ২. Invidious API দিয়ে ব্যাকআপ সার্চ
    for instance in INVIDIOUS_INSTANCES:
        try:
            url = f"{instance}/api/v1/search?q={encoded}&type=video"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data[:6]:
                    results.append({'id': item.get('videoId'), 'title': item.get('title')})
                if results:
                    return results
        except Exception as e:
            print(f"Invidious Search error on {instance}: {e}")

    return results

# ভিডিও স্ট্রিম ইউআরএল বের করার ফাংশন
def get_stream_url(video_id):
    # Piped থেকে সরাসরি এমপি৪ লিংক নেওয়া
    for instance in PIPED_INSTANCES:
        try:
            url = f"{instance}/streams/{video_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                streams = data.get('videoStreams', [])
                for s in streams:
                    if s.get('url'):
                        return s.get('url')
        except Exception as e:
            print(f"Piped Stream fetch failed on {instance}: {e}")

    # Invidious ব্যাকআপ
    for instance in INVIDIOUS_INSTANCES:
        try:
            url = f"{instance}/api/v1/videos/{video_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                streams = data.get('formatStreams', [])
                if streams and streams[0].get('url'):
                    return streams[0].get('url')
        except Exception as e:
            print(f"Invidious Stream fetch failed on {instance}: {e}")

    return None

@app.route('/', methods=['GET'])
def index():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = search_videos(query)
    return render_template_string(HTML_TEMPLATE, query=query, results=results)

@app.route('/download', methods=['GET'])
def download():
    video_id = request.args.get('id')
    if not video_id:
        return "No video ID provided", 400
    
    stream_url = get_stream_url(video_id)
    if not stream_url:
        return "ভিডিও লিংক বের করা সম্ভব হয়নি। অনুগ্রহ করে অন্য ভিডিও ট্রাই করুন।", 500

    output_file = f"/tmp/{video_id}.3gp"

    if os.path.exists(output_file):
        os.remove(output_file)

    try:
        # ffmpeg সরাসরি অনলাইন ভিডিও স্ট্রিম ধরে Symphony B100 উপযোগী 3GP এ কনভার্ট করবে
        cmd = f'ffmpeg -y -i "{stream_url}" -t 600 -r 15 -s 176x144 -b:v 96k -ac 1 -ar 8000 -ab 12.2k -f 3gp "{output_file}"'
        subprocess.run(cmd, shell=True, check=True)

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        return "3GP রূপান্তর ব্যর্থ হয়েছে", 500
    except Exception as e:
        return f"Conversion error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
