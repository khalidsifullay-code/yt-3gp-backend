import os
import urllib.parse
import urllib.request
import json
import subprocess
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.privacydev.net",
    "https://inv.tux.pizza"
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>YouTube Lite 3GP</title>
    <style>
        body { font-family: sans-serif; font-size: 12px; margin: 5px; padding: 0; background: #fff; color: #000; }
        input, button { font-size: 12px; margin: 2px 0; }
        .item { border-bottom: 1px solid #ccc; padding: 5px 0; margin-bottom: 5px; }
        a { color: blue; text-decoration: underline; font-weight: bold; }
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
            <p>কোনো ভিডিও পাওয়া যায়নি। আবার চেষ্টা করুন।</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

def search_invidious(query):
    encoded = urllib.parse.quote(query)
    results = []
    for instance in INVIDIOUS_INSTANCES:
        try:
            url = f"{instance}/api/v1/search?q={encoded}&type=video"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data[:6]:
                    results.append({
                        'id': item.get('videoId'),
                        'title': item.get('title')
                    })
                if results:
                    break
        except Exception as e:
            print(f"Search failed on {instance}: {e}")
            continue
    return results

def get_stream_url(video_id):
    for instance in INVIDIOUS_INSTANCES:
        try:
            url = f"{instance}/api/v1/videos/{video_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                format_streams = data.get('formatStreams', [])
                if format_streams:
                    return format_streams[0].get('url')
        except Exception as e:
            print(f"Stream fetch failed on {instance}: {e}")
            continue
    return None

@app.route('/', methods=['GET'])
def index():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = search_invidious(query)
    return render_template_string(HTML_TEMPLATE, query=query, results=results)

@app.route('/download', methods=['GET'])
def download():
    video_id = request.args.get('id')
    if not video_id:
        return "No video ID provided", 400
    
    stream_url = get_stream_url(video_id)
    if not stream_url:
        return "প্রক্সি সার্ভার থেকে ভিডিওর লিংক পাওয়া যায়নি। অন্য ভিডিও চেষ্টা করুন।", 500

    output_file = f"/tmp/{video_id}.3gp"

    if os.path.exists(output_file):
        os.remove(output_file)

    try:
        # Stream directly from proxy URL and convert to 176x144 3GP using ffmpeg
        cmd = f'ffmpeg -y -i "{stream_url}" -r 15 -s 176x144 -b:v 128k -ac 1 -ar 8000 -ab 12.2k "{output_file}"'
        subprocess.run(cmd, shell=True, check=True)

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        return "3GP কনভার্সন ব্যর্থ হয়েছে", 500
    except Exception as e:
        return f"Error converting video: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
