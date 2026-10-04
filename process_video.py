import os
import sys
import re
import subprocess
import requests
import numpy as np
import librosa
from config import CHANNELS

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

def extract_video_id(url: str) -> str:
    """استخراج المعرف النقي للفيديو من أي رابط يوتيوب مهما كان شكله"""
    url = url.strip().strip("'\"").replace(" ", "")
    regex = r'(?:v=|\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(regex, url)
    if match:
        return match.group(1)
    return url

def download_and_extract_audio(raw_url: str):
    video_id = extract_video_id(raw_url)
    clean_link = f"https://www.youtube.com/watch?v={video_id}"
    print(f"⬇️ جاري التنزيل للفيديو (ID: {video_id}) من الرابط: {clean_link}")

    # استراتيجية تنزيل مصممة لكسر حظر سيرفرات السحاب (GitHub Datacenter IPs)
    cmd_download = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "--add-header", "Accept-Language:en-US,en;q=0.9",
        "--extractor-args", "youtube:player_client=android_embedded,web_embedded",
        "-f", "best[ext=mp4]/best",
        "-o", "raw_match.mp4",
        clean_link
    ]
    
    try:
        subprocess.run(cmd_download, check=True)
    except subprocess.CalledProcessError:
        print("⚠️ المحاولة الأولى تعثرت، جاري التحويل إلى عميل ios_embedded البديل...")
        fallback_cmd = [
            "yt-dlp",
            "--no-check-certificates",
            "--geo-bypass",
            "--extractor-args", "youtube:player_client=ios_embedded",
            "-f", "b/best",
            "-o", "raw_match.mp4",
            clean_link
        ]
        subprocess.run(fallback_cmd, check=True)

    print("🎵 استخراج الصوت لتحليله بواسطة librosa...")
    cmd_audio = [
        "ffmpeg", "-y", "-i", "raw_match.mp4",
        "-vn", "-ar", "22050", "-ac", "1", "audio.wav"
    ]
    subprocess.run(cmd_audio, check=True)

def find_highlight_timestamps(audio_file="audio.wav", threshold_ratio=0.80):
    print("🔍 تحليل قمم الصراخ والحماس الصوتي...")
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    threshold = np.max(rms) * threshold_ratio
    peaks = [times[i] for i in range(len(rms)) if rms[i] > threshold]

    highlights = []
    last_time = -15
    for t in peaks:
        if t - last_time > 12:
            start = max(0, t - 3)
            end = t + 5
            highlights.append((start, end))
            last_time = t

    selected = highlights[:6]
    print(f"🎯 تم تحديد {len(selected)} لقطة حماسية: {selected}")
    return selected

def create_shorts(highlights):
    print("✂️ قص وتعديل الكادر لمقاس Shorts (1080x1920)...")
    clip_list = []
    for idx, (s, e) in enumerate(highlights):
        out_name = f"part_{idx}.mp4"
        duration = e - s
        cmd = [
            "ffmpeg", "-y", "-ss", str(s), "-t", str(duration),
            "-i", "raw_match.mp4",
            "-vf", "crop=ih*(9/16):ih,scale=1080:1920",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", out_name
        ]
        subprocess.run(cmd, check=True)
        clip_list.append(out_name)

    with open("clips.txt", "w", encoding="utf-8") as f:
        for c in clip_list:
            f.write(f"file '{c}'\n")

    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "final_shorts.mp4"], check=True)
    print("🎉 تم إنتاج الفيديو النهائي بنجاح: final_shorts.mp4")

def upload_to_buffer(channel_key: str, video_url: str, caption: str):
    if not BUFFER_API_KEY:
        print("⚠️ لم يتم العثور على BUFFER_API_KEY.")
        return

    channel = CHANNELS.get(channel_key)
    if not channel:
        raise ValueError(f"Unknown channel: {channel_key}")

    print(f"🚀 إرسال الفيديو إلى Buffer -> القناة: {channel['name']}...")
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
    if not moments:
        moments = [(0, 35)]
    create_shorts(moments)
    print("✅ اكتمل المونتاج واستخراج الفيديو بنجاح.")
