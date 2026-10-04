import os
import sys
import requests
import subprocess
import numpy as np
import librosa
from config import CHANNELS

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

def download_and_extract_audio(youtube_url):
    print("⬇️ جاري تنزيل الفيديو واستخراج الصوت...")
    subprocess.run(f'yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" -o "raw_match.mp4" {youtube_url}', shell=True, check=True)
    subprocess.run("ffmpeg -y -i raw_match.mp4 -vn -ar 22050 -ac 1 audio.wav", shell=True, check=True)

def find_highlight_timestamps(audio_file="audio.wav", threshold_ratio=0.85):
    print("🔍 تحليل قمم الصراخ والحماس الصوتي...")
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)
    
    threshold = np.max(rms) * threshold_ratio
    peaks = [times[i] for i in range(len(rms)) if rms[i] > threshold]
    
    highlights = []
    last_time = -10
    for t in peaks:
        if t - last_time > 15:
            start = max(0, t - 4)
            end = t + 5
            highlights.append((start, end))
            last_time = t
    return highlights[:5] # نأخذ أقوى 5 لحظات

def create_shorts(highlights):
    print("✂️ قص وتعديل الكادر لمقاس Shorts (9:16)...")
    clip_list = []
    for idx, (s, e) in enumerate(highlights):
        out_name = f"part_{idx}.mp4"
        cmd = f'ffmpeg -y -ss {s} -to {e} -i raw_match.mp4 -vf "crop=ih*(9/16):ih,scale=1080:1920" -c:v libx264 -crf 23 -c:a aac {out_name}'
        subprocess.run(cmd, shell=True, check=True)
        clip_list.append(out_name)
    
    # دمج الأجزاء في فيديو واحد
    with open("clips.txt", "w") as f:
        for c in clip_list:
            f.write(f"file '{c}'\n")
    
    subprocess.run("ffmpeg -y -f concat -safe 0 -i clips.txt -c copy final_shorts.mp4", shell=True, check=True)
    print("✅ تم تجهيز الفيديو النهائي: final_shorts.mp4")

def post_to_buffer(channel_key, video_url, caption):
    print(f"🚀 إرسال الفيديو إلى Buffer للقناة: {channel_key}...")
    channel = CHANNELS[channel_key]
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json"
    }

    full_text = f"{caption}\n\n{channel['hashtags']}"
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        post {
          id
          status
        }
      }
    }
    """
    variables = {
        "input": {
            "channelId": channel["channel_id"],
            "text": full_text,
            "media": [{"video": {"url": video_url}}],
            "schedulingType": "NOW"
        }
    }
    res = requests.post(url, json={"query": mutation, "variables": variables}, headers=headers)
    print("استجابة Buffer:", res.json())

if __name__ == "__main__":
    channel_key = sys.argv[1] # e.g. 90_plus, hattrick, crazy_skills
    match_url = sys.argv[2]   # رابط يوتيوب
    caption = sys.argv[3] if len(sys.argv) > 3 else "Crazy Match Highlights! 🔥"
    
    download_and_extract_audio(match_url)
    moments = find_highlight_timestamps()
    create_shorts(moments)
