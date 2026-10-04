import os
import sys
import subprocess
import requests
import numpy as np
import librosa
from config import CHANNELS

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

def clean_url(url: str) -> str:
    """تنظيف الرابط وإزالة المسافات والمعاملات الإضافية"""
    url = url.strip()
    # لو كان رابط مختصر وفيه مسافة بالخطأ
    if " " in url:
        url = url.replace(" ", "_")
    return url

def download_and_extract_audio(youtube_url: str):
    """تنزيل الفيديو واستخراج مسار الصوت بأعلى استقرار ممكن في بيئات السحاب"""
    clean_link = clean_url(youtube_url)
    print(f"⬇️ جاري تنزيل الفيديو من: {clean_link}")

    cmd_download = (
        f'yt-dlp --no-check-certificates '
        f'--extractor-args "youtube:player_client=android,web" '
        f'-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" '
        f'-o "raw_match.mp4" "{clean_link}"'
    )
    subprocess.run(cmd_download, shell=True, check=True)

    print("🎵 استخراج ملف الصوت لتحليله...")
    cmd_audio = "ffmpeg -y -i raw_match.mp4 -vn -ar 22050 -ac 1 audio.wav"
    subprocess.run(cmd_audio, shell=True, check=True)

def find_highlight_timestamps(audio_file="audio.wav", threshold_ratio=0.82):
    """رصد قمم صراخ المعلق والجمهور لاستخراج اللقطات الحماسية"""
    print("🔍 تحليل قمم الصراخ والحماس الصوتي...")
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    threshold = np.max(rms) * threshold_ratio
    peaks = [times[i] for i in range(len(rms)) if rms[i] > threshold]

    highlights = []
    last_time = -15
    for t in peaks:
        if t - last_time > 12:  # فاصل 12 ثانية بين اللقطة والأخرى
            start = max(0, t - 3)
            end = t + 5
            highlights.append((start, end))
            last_time = t

    # أخذ أفضل 5-6 لقطات لا تتعدى مدتها الإجمالية 50 ثانية
    selected = highlights[:6]
    print(f"🎯 تم تحديد {len(selected)} لقطة حماسية: {selected}")
    return selected

def create_shorts(highlights):
    """قص اللقطات وتحويل الكادر لنسبة 9:16 ودمجها"""
    print("✂️ قص وتعديل الكادر لمقاس Shorts (1080x1920)...")
    clip_list = []
    for idx, (s, e) in enumerate(highlights):
        out_name = f"part_{idx}.mp4"
        duration = e - s
        cmd = (
            f'ffmpeg -y -ss {s} -t {duration} -i raw_match.mp4 '
            f'-vf "crop=ih*(9/16):ih,scale=1080:1920" '
            f'-c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k {out_name}'
        )
        subprocess.run(cmd, shell=True, check=True)
        clip_list.append(out_name)

    with open("clips.txt", "w", encoding="utf-8") as f:
        for c in clip_list:
            f.write(f"file '{c}'\n")

    subprocess.run("ffmpeg -y -f concat -safe 0 -i clips.txt -c copy final_shorts.mp4", shell=True, check=True)
    print("🎉 تم إنتاج الفيديو النهائي بنجاح: final_shorts.mp4")

def upload_to_buffer(channel_key: str, video_url: str, caption: str):
    """إرسال المنشور إلى Buffer عبر الـ GraphQL API"""
    if not BUFFER_API_KEY:
        print("⚠️ لم يتم العثور على BUFFER_API_KEY، سيتم تجاوز مرحلة الرفع.")
        return

    channel = CHANNELS.get(channel_key)
    if not channel:
        raise ValueError(f"Unknown channel: {channel_key}")

    print(f"🚀 إرسال الفيديو لـ Buffer -> القناة: {channel['name']} ({channel['target_country']})...")
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
    if len(sys.argv) < 3:
        print("الاستخدام: python process_video.py <channel_key> <youtube_url> [caption]")
        sys.exit(1)

    channel_arg = sys.argv[1]
    url_arg = sys.argv[2]
    caption_arg = sys.argv[3] if len(sys.argv) > 3 else "Insane Football Highlights! 🔥⚽"

    download_and_extract_audio(url_arg)
    moments = find_highlight_timestamps()
    create_shorts(moments)
    print("✅ اكتملت المعالجة المحلية بنجاح.")
