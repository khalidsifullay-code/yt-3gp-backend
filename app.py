import os
import subprocess
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)

# বাটন ফোনের উপযোগী একদম হালকা HTML টেমপ্লেট (জিরো জাভাস্ক্রিপ্ট)
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
        a { color: blue; text-decoration: underline; }
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
                <b>{{ item.title }}</b> [{{ item.duration }}m]<br>
                <a href="/download?id={{ item.id }}">[ Download 3GP ]</a>
            </div>
            {% endfor %}
        {% else %}
            <p>কোনো ভিডিও পাওয়া যায়নি।</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'default_search': 'ytsearch5'
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(query, download=False)
                for entry in res.get('entries', []):
                    if entry:
                        dur = entry.get('duration')
                        dur_str = f"{int(dur // 60)}" if dur else "N/A"
                        results.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'duration': dur_str
                        })
        except Exception as e:
            print("Error:", e)
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
        'format': 'worst[ext=mp4]/worst'
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Convert to 3GP format (176x144 resolution) for keypad phones
        cmd = f"ffmpeg -y -i {input_file} -r 15 -s 176x144 -b:v 128k -ac 1 -ar 8000 -ab 12.2k {output_file}"
        subprocess.run(cmd, shell=True, check=True)

        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        return "Conversion failed", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
