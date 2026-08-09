import os
import re
import urllib.parse
import urllib.request
import subprocess
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)

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

def search_youtube(query):
    encoded = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
    )
    results = []
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        matches = re.findall(r'"videoRenderer":\{"videoId":"([^"]+)".*?"title":\{"runs":\[\{"text":"([^"]+)"\}', html)
        seen_ids = set()
        for vid, title in matches:
            if vid not in seen_ids:
                seen_ids.add(vid)
                results.append({'id': vid, 'title': title})
            if len(results) >= 6:
                break
    except Exception as e:
        print("Search error:", e)

    if not results:
        try:
            vids = re.findall(r"watch\?v=(\S{11})", html)
            seen_ids = set()
            for vid in vids:
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    results.append({'id': vid, 'title': f"YouTube Video ({vid})"})
                if len(results) >= 6:
                    break
        except Exception as e:
            print("Fallback error:", e)

    return results

@app.route('/', methods=['GET'])
def index():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = search_youtube(query)
    return render_template_string(HTML_TEMPLATE, query=query, results=results)

@app.route('/download', methods=['GET'])
def download():
    video_id = request.args.get('id')
    if not video_id:
        return "No video ID provided", 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    input_file = f"/tmp/{video_id}.mp4"
    output_file = f"/tmp/{video_id}.3gp"

    if os.path.exists(input_file):
        os.remove(input_file)
    if os.path.exists(output_file):
        os.remove(output_file)

    ydl_opts = {
        'outtmpl': input_file,
        'format': 'worst[ext=mp4]/worst',
        'nocheckcertificate': True
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        cmd = f"ffmpeg -y -i {input_file} -r 15 -s 176x144 -b:v 128k -ac 1 -ar 8000 -ab 12.2k {output_file}"
        subprocess.run(cmd, shell=True, check=True)

        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        return "Conversion failed", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
