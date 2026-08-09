import os
import subprocess
from flask import Flask, request, jsonify, send_file
from yt_dlp import YoutubeDL

app = Flask(__name__)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'default_search': 'ytsearch5'
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(query, download=False)
            results = []
            for entry in res.get('entries', []):
                if entry:
                    results.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'duration': entry.get('duration')
                    })
            return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

        # Convert to 3GP (176x144 resolution) for keypad phones
        cmd = f"ffmpeg -y -i {input_file} -r 15 -s 176x144 -b:v 128k -ac 1 -ar 8000 -ab 12.2k {output_file}"
        subprocess.run(cmd, shell=True, check=True)

        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True, download_name=f"{video_id}.3gp")
        return "Conversion failed", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
