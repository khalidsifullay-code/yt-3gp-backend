import os
import re
import json
import urllib.parse
import urllib.request
import subprocess
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)

# ব্যাকআপ প্রক্সি এপিআই লিস্ট
PIPED_APIS = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.privacydev.net",
    "https://pipedapi.mha.fi",
    "https://pipedapi.tokhmi.xyz"
]

INVIDIOUS_APIS = [
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

# ১. বহুস্তরীয় সার্চ ফাংশন
def search_videos(query):
    encoded = urllib.parse.quote(query)
    results = []
    
    # ধাপ ১: মোবাইল ইউটিউব স্ক্র্যাপিং
    try:
        url = f"https://www.youtube.com/results?search_query={encoded}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=6).read().decode('utf-8', errors='ignore')
        
        matches = re.findall(r'"videoRenderer":\{"videoId":"([^"]+)".*?"title":\{"runs":\[\{"text":"([^"]+)"\}', html)
        seen = set()
        for vid, title in matches:
            if vid not in seen:
                seen.add(vid)
                results.append({'id': vid, 'title': title})
            if len(results) >= 6:
                break
        if results:
            return results
    except Exception as e:
        print("Scrape Search Error:", e)

    # ধাপ ২: Piped API ব্যাকআপ
    for api in PIPED_APIS:
        try:
            url = f"{api}/search?q={encoded}&filter=all"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data.get('items', []):
                    if item.get('type') == 'stream':
                        v_id = item.get('url', '').replace('/watch?v=', '')
                        if v_id:
                            results.append({'id': v_id, 'title': item.get('title')})
                    if len(results) >= 6:
                        break
                if results:
                    return results
        except Exception as e:
            print("Piped Search Error:", e)

    # ধাপ ৩: Invidious API ব্যাকআপ
    for api in INVIDIOUS_APIS:
        try:
            url = f"{api}/api/v1/search?q={encoded}&type=video"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data[:6]:
                    results.append({'id': item.get('videoId'), 'title': item.get('title')})
                if results:
                    return results
        except Exception as e:
            print("Invidious Search Error:", e)

    return results

# ২. ভিডিও স্ট্রিম ও ডাউনলোড ব্যবস্থা
def get_stream_url(video_id):
    # Piped থেকে সরাসরি MP4 স্ট্রিম
    for api in PIPED_APIS:
        try:
            url = f"{api}/streams/{video_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for s in data.get('videoStreams', []):
                    if s.get('url'):
                        return s.get('url')
        except Exception as e:
            print("Piped Stream Error:", e)

    # Invidious ব্যাকআপ
    for api in INVIDIOUS_APIS:
        try:
            url = f"{api}/api/v1/videos/{video_id}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                streams = data.get('formatStreams', [])
                if streams and streams[0].get('url'):
                    return streams[0].get('url')
        except Exception as e:
            print("Invidious Stream Error:", e)

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

    input_file = f"/tmp/{video_id}.mp4"
    output_file = f"/tmp/{video_id}.3gp"

    if os.path.exists(input_file):
        os.remove(input_file)
    if os.path.exists(output_file):
        os.remove(output_file)

    downloaded = False

    # পদ্ধতি ১: Android Client দিয়ে yt-dlp ডাউনলোড
    try:
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'worst[ext=mp4]/worst',
            'nocheckcertificate': True,
            'quiet': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        if os.path.exists(input_file) and os.path.getsize(input_file) > 0:
            downloaded = True
    except Exception as e:
        print("yt-dlp Direct Download Failed:", e)

    # পদ্ধতি ২: প্রক্সি স্ট্রিম লিঙ্ক ধরে রূপান্তর
    if not downloaded:
        stream_url = get_stream_url(video_id)
        if stream_url:
            try:
                cmd = f'ffmpeg -y -i "{stream_url}" -t 600 -r 15 -s 176x144 -b:v 96k -ac 1 -ar 8000 -ab 12.2k -f 3gp "{output_file}"'
                subprocess.run(cmd, shell=True, check=True)
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
            except Exception as e:
                print("FFmpeg Direct Stream Failed:", e)

    # যদি পদ্ধতি ১ এ ডাউনলোড সফল হয়ে থাকে তবে ফাইল থেকে 3GP তে কনভার্ট
    if downloaded:
        try:
            cmd = f'ffmpeg -y -i "{input_file}" -t 600 -r 15 -s 176x144 -b:v 96k -ac 1 -ar 8000 -ab 12.2k -f 3gp "{output_file}"'
            subprocess.run(cmd, shell=True, check=True)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        except Exception as e:
            return f"Conversion Error: {str(e)}", 500

    return "ইউটিউব সার্ভার আইপি সাময়িকভাবে ব্লক করেছে। ১ মিনিট পর অন্য ভিডিও চেষ্টা করুন।", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
