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

def prepare_cookies():
    cookie_path = os.path.abspath("cookies.txt")
    if YOUTUBE_COOKIES_DATA and len(YOUTUBE_COOKIES_DATA.strip()) > 30:
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES_DATA.strip() + "\n")
        return cookie_path
    if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 30:
        return cookie_path
    return None

def download_and_extract_audio(raw_url: str):
    clean_link = clean_url(raw_url)
    print(f"⬇️ جاري سحب الفيديو المباشر: {clean_link}")

    cookie_file = prepare_cookies()
    if cookie_file:
        print("🔑 تم تفعيل ملف الكوكيز بنجاح.")

    cmd_download = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "--extractor-args", "youtube:player_client=web,web_embedded",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "-o", "raw_match.mp4"
    ]

    if cookie_file:
        cmd_download.extend(["--cookies", cookie_file])

    cmd_download.append(clean_link)

    res = subprocess.run(cmd_download, capture_output=True, text=True)
    if res.returncode != 0:
        print("⚠️️ المحاولة الأولى تعثرت، تفاصيل السجل:")
        print(res.stderr)
        print("🔄 جاري تجربة النمط المباشر السريع...")
        fallback_cmd = [
            "yt-dlp",
            "--no-check-certificates",
            "--geo-bypass",
            "-f", "b/best",
            "-o", "raw_match.mp4"
        ]
        if cookie_file:
            fallback_cmd.extend(["--cookies", cookie_file])
        fallback_cmd.append(clean_link)
        res_fb = subprocess.run(fallback_cmd, capture_output=True, text=True)
        if res_fb.returncode != 0:
            print("❌ رسالة الخطأ الصريحة:")
            print(res_fb.stderr)
            raise RuntimeError(res_fb.stderr)

    print("🎵 استخراج الصوت لتحليل ذروة الحماس...")
    cmd_audio = [
        "ffmpeg", "-y", "-i", "raw_match.mp4",
        "-vn", "-ar", "22050", "-ac", "1", "audio.wav"
    ]
    subprocess.run(cmd_audio, check=True)

def find_highlight_timestamps(audio_file="audio.wav", threshold_ratio=0.82):
    print("🔍 تحليل قمم الصراخ وانفجار الأهداف...")
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    threshold = np.max(rms) * threshold_ratio
    peaks = [times[i] for i in range(len(rms)) if rms[i] > threshold]

    highlights = []
    last_time = -20
    for t in peaks:
        if t - last_time > 15:
            start = max(0, t - 4)
            end = t + 6
            highlights.append((start, end))
            last_time = t

    selected = highlights[:5]
    print(f"🎯 المقاطع المختارة: {selected}")
    return selected

def create_shorts_with_blur_layout(highlights, match_title="Match Highlights"):
    print("🎬 مونتاج الشورتس بالخلفية الضبابية الذكية والشريط الإخباري...")
    clip_list = []
    safe_title = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', '', match_title)[:45]

    for idx, (s, e) in enumerate(highlights):
        out_name = f"part_{idx}.mp4"
        duration = e - s

        filter_str = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]drawbox=y=120:color=black@0.6:width=iw:height=140:t=fill,"
            f"drawtext=text='{safe_title}':fontsize=42:fontcolor=white:x=(w-text_w)/2:y=165[v]"
        )

        cmd = [
            "ffmpeg", "-y", "-ss", str(s), "-t", str(duration),
            "-i", "raw_match.mp4",
            "-filter_complex", filter_str,
            "-map", "[v]",
            "-map", "0:a",
            "-af", "afade=t=in:ss=0:d=0.3,afade=t=out:st=" + str(duration - 0.3) + ":d=0.3",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", out_name
        ]
        
        try:
            subprocess.run(cmd, check=True)
            clip_list.append(out_name)
        except subprocess.CalledProcessError:
            simple_filter = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
                "[0:v]scale=1080:-2[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )
            fallback_cmd = [
                "ffmpeg", "-y", "-ss", str(s), "-t", str(duration),
                "-i", "raw_match.mp4",
                "-filter_complex", simple_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", out_name
            ]
            subprocess.run(fallback_cmd, check=True)
            clip_list.append(out_name)

    with open("clips.txt", "w", encoding="utf-8") as f:
        for c in clip_list:
            f.write(f"file '{c}'\n")

    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "final_shorts.mp4"], check=True)
    print("🎉 تم استخراج الفيديو بأبعاد Shorts سينمائية: final_shorts.mp4")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("الاستخدام: python process_video.py <channel_key> <youtube_url> [caption]")
        sys.exit(1)

    channel_arg = sys.argv[1]
    url_arg = sys.argv[2]
    caption_arg = sys.argv[3] if len(sys.argv) > 3 else "ملخص وأهداف المباراة 🔥⚽"

    download_and_extract_audio(url_arg)
    moments = find_highlight_timestamps()
    if not moments:
        moments = [(0, 30)]
    create_shorts_with_blur_layout(moments, caption_arg)
    print("✅ تم المونتاج بنجاح وتلافي كافة أخطاء الكادر والصوت.")
