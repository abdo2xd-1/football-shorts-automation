import os
import sys
import subprocess
import requests
import numpy as np
import librosa
from config import CHANNELS

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

def clean_url(url: str) -> str:
    """تنظيف الرابط وإزالة أي مسافات أو علامات تنصيص"""
    cleaned = url.strip().strip("'\"")
    # استبدال المسافة بالشرطة السفلية إذا كانت في معرّف يوتيوب
    return cleaned.replace(" ", "_")

def download_and_extract_audio(youtube_url: str):
    """تنزيل الفيديو واستخراج مسار الصوت"""
    clean_link = clean_url(youtube_url)
    print(f"⬇️ جاري تنزيل الفيديو من الرابط: {clean_link}")

    cmd_download = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "--extractor-args", "youtube:player_client=ios,mweb",
        "-f", "b/best",
        "-o", "raw_match.mp4",
        clean_link
    ]
    subprocess.run(cmd_download, check=True)

    print("🎵 استخراج ملف الصوت لتحليله...")
    cmd_audio = [
        "ffmpeg", "-y", "-i", "raw_match.mp4",
        "-vn", "-ar", "22050", "-ac", "1", "audio.wav"
    ]
    subprocess.run(cmd_audio, check=True)

def find_highlight_timestamps(audio_file="audio.wav", threshold_ratio=0.80):
    """تحليل قمم الحماس الصوتي للمعلق والجماهير"""
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
    """قص وتغيير أبعاد الكادر لمقاس Shorts (9:16)"""
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
    """إرسال الفيديو إلى بافر عبر GraphQL API"""
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
    url_arg = clean_url(sys.argv[2])
    caption_arg = sys.argv[3] if len(sys.argv) > 3 else "Insane Football Highlights! 🔥⚽"

    download_and_extract_audio(url_arg)
    moments = find_highlight_timestamps()
    if not moments:
        moments = [(0, 35)]
    create_shorts(moments)
    print("✅ اكتمل المونتاج واستخراج الفيديو بنجاح.")
