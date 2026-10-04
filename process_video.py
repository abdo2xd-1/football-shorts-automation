import os
import sys
import re
import subprocess
import requests
import numpy as np
import librosa
from config import CHANNELS

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
YOUTUBE_COOKIES_DATA = os.getenv("YOUTUBE_COOKIES")

def clean_url(url: str) -> str:
    cleaned = url.strip().strip("'\"").replace(" ", "")
    regex = r'(?:v=|\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(regex, cleaned)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return cleaned

def setup_cookies_file():
    cookie_path = os.path.abspath("cookies.txt")
    if YOUTUBE_COOKIES_DATA and len(YOUTUBE_COOKIES_DATA.strip()) > 50:
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES_DATA.strip() + "\n")
        print(f"✅ تم إنشاء ملف الكوكيز بنجاح في: {cookie_path}")
        return cookie_path
    elif os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 50:
        return cookie_path
    return None

def download_and_extract_audio(raw_url: str):
    clean_link = clean_url(raw_url)
    print(f"⬇️ جاري تنزيل الفيديو من الرابط: {clean_link}")

    cookie_file = setup_cookies_file()

    cmd_download = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", "raw_match.mp4"
    ]

    if cookie_file:
        cmd_download.extend(["--cookies", cookie_file])

    cmd_download.append(clean_link)

    try:
        subprocess.run(cmd_download, check=True)
    except subprocess.CalledProcessError:
        print("⚠️ جاري المحاولة بصيغة بديلة...")
        cmd_fallback = [
            "yt-dlp",
            "--no-check-certificates",
            "--geo-bypass",
            "-f", "b/best",
            "-o", "raw_match.mp4"
        ]
        if cookie_file:
            cmd_fallback.extend(["--cookies", cookie_file])
        cmd_fallback.append(clean_link)
        subprocess.run(cmd_fallback, check=True)

    print("🎵 استخراج الصوت لتحليله...")
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
    print("✂️️ قص وتعديل الكادر لمقاس Shorts (1080x1920)...")
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
