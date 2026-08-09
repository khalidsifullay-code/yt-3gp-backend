import os
import subprocess
import json
import urllib.request
import urllib.parse
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Lite (3GP)</title>
    <style>
        body { font-family: sans-serif; font-size: 13px; margin: 8px; padding: 0; background: #fff; color: #000; }
        input[type="text"] { font-size: 13px; padding: 5px; width: 60%; }
        button { font-size: 13px; padding: 5px 10px; }
        .item { border-bottom: 1px solid #ccc; padding: 8px 0; margin-bottom: 4px; }
        .title { font-weight: bold; display: block; margin-bottom: 4px; }
        a { color: blue; text-decoration: underline; font-weight: bold; }
        .error { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h3>YouTube Lite (3GP)</h3>
    <form action="/" method="GET">
        <input type="text" name="q" value="{{ query }}" placeholder="ভিডিওর নাম লিখুন..." required>
        <button type="submit">Search</button>
    </form>
    <hr>
    {% if query %}
        {% if results %}
            {% for item in results %}
            <div class="item">
                <span class="title">{{ item.title }}</span>
                <a href="/download?id={{ item.id }}">[ Download 3GP ]</a>
            </div>
            {% endfor %}
        {% else %}
            <p class="error">কোনো ভিডিও পাওয়া যায়নি। আবার চেষ্টা করুন।</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

def search_videos(query):
    results = []

    # পদ্ধতি ১: YouTube Android Innertube API (বট ব্লক বাইপাস করতে সক্ষম)
    try:
        url = "https://www.youtube.com/youtubei/v1/search"
        payload = {
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "19.02.34",
                    "hl": "en",
                    "gl": "US"
                }
            },
            "query": query
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'com.google.android.youtube/19.02.34 (Linux; U; Android 11; en_US)'
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            contents = data.get('contents', {}).get('sectionListRenderer', {}).get('contents', [])
            for content in contents:
                item_section = content.get('itemSectionRenderer', {}).get('contents', [])
                for item in item_section:
                    v_info = item.get('videoRenderer', {})
                    v_id = v_info.get('videoId')
                    title_text = ""
                    runs = v_info.get('title', {}).get('runs', [])
                    if runs:
                        title_text = runs[0].get('text', '')
                    if v_id and title_text:
                        results.append({'id': v_id, 'title': title_text})
                    if len(results) >= 6:
                        break
                if len(results) >= 6:
                    break
            if results:
                return results
    except Exception as e:
        print("Innertube search failed:", e)

    # পদ্ধতি ২: yt-dlp flat extraction (ব্যাকআপ সার্চ)
    try:
        ydl_opts = {
            'extract_flat': True,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch6:{query}", download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry and entry.get('id'):
                        results.append({
                            'id': entry.get('id'),
                            'title': entry.get('title', f"Video {entry.get('id')}")
                        })
                if results:
                    return results
    except Exception as e:
        print("yt-dlp search failed:", e)

    return results

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

    input_file = f"/tmp/{video_id}.mp4"
    output_file = f"/tmp/{video_id}.3gp"

    if os.path.exists(input_file):
        os.remove(input_file)
    if os.path.exists(output_file):
        os.remove(output_file)

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    download_success = False

    # yt-dlp দিয়ে এমপি৪ ডাউনলোড
    try:
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'worst[ext=mp4]/worst',
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb']}}
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if os.path.exists(input_file) and os.path.getsize(input_file) > 0:
            download_success = True
    except Exception as e:
        print("Download failed:", e)

    if not download_success:
        return "ভিডিওটি ডাউনলোড করা সম্ভব হয়নি। অন্য ভিডিও চেষ্টা করুন।", 500

    # Symphony B100 উপযোগী 3GP এ রূপান্তর
    try:
        cmd = f'ffmpeg -y -i "{input_file}" -r 15 -s 176x144 -b:v 96k -ac 1 -ar 8000 -ab 12.2k -f 3gp "{output_file}"'
        subprocess.run(cmd, shell=True, check=True)

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            if os.path.exists(input_file):
                os.remove(input_file)
            return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        return "3GP রূপান্তর ব্যর্থ হয়েছে", 500
    except Exception as e:
        return f"Conversion Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
