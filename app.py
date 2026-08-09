import os
import subprocess
import json
import urllib.request
import urllib.parse
from flask import Flask, request, send_file, render_template_string

from yt_dlp import YoutubeDL

app = Flask(__name__)

# একাধিক অল্টারনেটিভ প্রক্সি স্ট্রিম সার্ভার (একটি কাজ না করলে অন্যটি অটো বেছে নেবে)
PIPED_STREAM_APIS = [
    "https://pipedapi.adminforge.de",
    "https://api.piped.privacydev.net",
    "https://pipedapi.mha.fi",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.palvelu.org",
    "https://piped-api.garudalinux.org"
]

INVIDIOUS_STREAM_APIS = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yewtu.be",
    "https://invidious.drgns.space",
    "https://invidious.privacydev.net"
]

SEARCH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Lite (3GP)</title>
    <style>
        body { font-family: sans-serif; font-size: 13px; margin: 8px; padding: 0; background: #fff; color: #000; }
        input[type="text"] { font-size: 13px; padding: 6px; width: 60%; }
        button { font-size: 13px; padding: 6px 10px; }
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
                <a href="/convert?id={{ item.id }}">[ Download 3GP ]</a>
            </div>
            {% endfor %}
        {% else %}
            <p class="error">কোনো ভিডিও পাওয়া যায়নি। অন্য কিছু লিখে চেষ্টা করুন।</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

CONVERT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3GP Processing...</title>
    <style>
        body { font-family: sans-serif; font-size: 13px; margin: 15px; background: #fff; color: #000; text-align: center; }
        .box { border: 1px solid #000; padding: 15px; margin-top: 20px; background: #f9f9f9; }
        .loader { font-weight: bold; color: green; font-size: 14px; margin: 10px 0; }
        a { color: blue; font-weight: bold; }
    </style>
</head>
<body>
    <h3>YouTube Lite (3GP)</h3>
    <div class="box">
        <p class="loader">⏳ আপনার ভিডিওটি 3GP ফরম্যাটে প্রসেস করা হচ্ছে...</p>
        <p>অনুগ্রহ করে ৩-৫ সেকেন্ড অপেক্ষা করুন। কনভার্ট সম্পন্ন হওয়া মাত্রই অটোমেটিক ডাউনলোড শুরু হবে।</p>
        <p>যদি অটোমেটিক ডাউনলোড শুরু না হয়, তবে <a href="/process?id={{ video_id }}">এখানে ক্লিক করুন</a>।</p>
    </div>
    <script>
        setTimeout(function() {
            window.location.href = "/process?id={{ video_id }}";
        }, 1500);
    </script>
</body>
</html>
"""

def search_videos(query):
    results = []
    # YouTube Android Innertube API
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
        with urllib.request.urlopen(req, timeout=6) as resp:
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

    # yt-dlp flat search backup
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

def get_stream_url(video_id):
    # ১. Piped API Stream
    for api in PIPED_STREAM_APIS:
        try:
            url = f"{api}/streams/{video_id}"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                streams = data.get('videoStreams', [])
                for s in streams:
                    if s.get('url'):
                        return s.get('url')
        except Exception as e:
            print(f"Piped Stream failed on {api}:", e)

    # ২. Invidious API Stream
    for api in INVIDIOUS_STREAM_APIS:
        try:
            url = f"{api}/api/v1/videos/{video_id}"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                streams = data.get('formatStreams', [])
                if streams:
                    for s in streams:
                        if s.get('url'):
                            return s.get('url')
        except Exception as e:
            print(f"Invidious Stream failed on {api}:", e)

    # ৩. yt-dlp Raw Stream URL Extraction
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'format': 'worst[ext=mp4]/worst',
            'extractor_args': {'youtube': {'player_client': ['ios', 'mweb', 'android']}}
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if info and info.get('url'):
                return info.get('url')
    except Exception as e:
        print("yt-dlp stream extraction failed:", e)

    return None

@app.route('/', methods=['GET'])
def index():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = search_videos(query)
    return render_template_string(SEARCH_TEMPLATE, query=query, results=results)

@app.route('/convert', methods=['GET'])
def convert_page():
    video_id = request.args.get('id')
    if not video_id:
        return "No video ID provided", 400
    return render_template_string(CONVERT_TEMPLATE, video_id=video_id)

@app.route('/process', methods=['GET'])
def process_video():
    video_id = request.args.get('id')
    if not video_id:
        return "No video ID provided", 400

    output_file = f"/tmp/{video_id}.3gp"

    if os.path.exists(output_file):
        os.remove(output_file)

    # সরাসরি অনলাইন স্ট্রিম থেকে FFmpeg কনভার্ট
    stream_url = get_stream_url(video_id)

    if stream_url:
        try:
            # Symphony B100 বাটন ফোন ফরম্যাট: 176x144 QCIF, 15fps, 8kHz Mono Audio
            cmd = f'ffmpeg -y -i "{stream_url}" -t 600 -r 15 -s 176x144 -b:v 96k -ac 1 -ar 8000 -ab 12.2k -f 3gp "{output_file}"'
            subprocess.run(cmd, shell=True, check=True)

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        except Exception as e:
            print("FFmpeg Direct Stream conversion failed:", e)

    # ব্যাকআপ পদ্ধতি: yt-dlp দিয়ে ছোট ফরম্যাট নামিয়ে কনভার্ট
    input_file = f"/tmp/{video_id}.mp4"
    if os.path.exists(input_file):
        os.remove(input_file)

    try:
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'worst[ext=mp4]/worst',
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'mweb', 'android']}}
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        if os.path.exists(input_file) and os.path.getsize(input_file) > 0:
            cmd = f'ffmpeg -y -i "{input_file}" -t 600 -r 15 -s 176x144 -b:v 96k -ac 1 -ar 8000 -ab 12.2k -f 3gp "{output_file}"'
            subprocess.run(cmd, shell=True, check=True)
            if os.path.exists(input_file):
                os.remove(input_file)

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
    except Exception as e:
        print("yt-dlp fallback error:", e)

    return "ভিডিও স্ট্রিম লিঙ্ক পাওয়া যায়নি। ১ মিনিট পর অন্য ভিডিও চেষ্টা করুন।", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
