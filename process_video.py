import os
import sys
import re
import subprocess
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
    return None

def download_and_extract_audio(raw_url: str):
    clean_link = clean_url(raw_url)
    print(f"⬇️ جاري سحب مباراة المنتخب: {clean_link}")

    cookie_file = prepare_cookies()
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
        print("⚠️ جاري المحاولة بنمط البث العام المباشر...")
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
        subprocess.run(fallback_cmd, check=True)

    print("🎵 استخراج الصوت لتحديد اللحظة الأكثر حماساً...")
    cmd_audio = [
        "ffmpeg", "-y", "-i", "raw_match.mp4",
        "-vn", "-ar", "22050", "-ac", "1", "audio.wav"
    ]
    subprocess.run(cmd_audio, check=True)

def find_best_single_highlight(audio_file="audio.wav"):
    """تحديد أفضل وأقوى لقطة هدف متصلة واحدة في المباراة بالكامل"""
    print("🔍 البحث عن أعلى قمة حماس وصراخ (الهدف الحاسم)...")
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    # تجاهل أول 45 ثانية لتفادي النشيد الوطني والبدايات الفارغة
    valid_indices = [i for i, t in enumerate(times) if t > 45]
    if not valid_indices:
        return 45, 75

    max_idx = valid_indices[np.argmax(rms[valid_indices])]
    peak_time = times[max_idx]

    # أخذ 12 ثانية قبل الهدف (بناء الهجمة) و 16 ثانية بعده (الاحتفال)
    start_time = max(0, peak_time - 12)
    end_time = start_time + 30

    print(f"🎯 اللقطة الذهبية المحددة: من {start_time:.1f} إلى {end_time:.1f} ثانية")
    return start_time, end_time

def render_vertical_short(start_time, end_time, title="مباراة اليوم"):
    """إنتاج كادر عمودي سينمائي 9:16 بدون تقطيع وبصوت متصل"""
    duration = end_time - start_time
    clean_title = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', '', title)[:40]
    print(f"🎬 تصيير الفيديو النهائي بدقة 1080x1920 (مدة {duration} ثانية)...")

    # تكبير خلفية ضبابية مع وضع كادر اللعب كامل في المنتصف وشريط علوي أنيق
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]drawbox=y=140:color=black@0.65:width=iw:height=130:t=fill,"
        f"drawtext=text='{clean_title}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=185[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", "raw_match.mp4",
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a",
        "-af", "afade=t=in:ss=0:d=0.5,afade=t=out:st=" + str(duration - 0.5) + ":d=0.5",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "final_shorts.mp4"
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        simple_filter = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        cmd_fallback = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-t", str(duration),
            "-i", "raw_match.mp4",
            "-filter_complex", simple_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac",
            "final_shorts.mp4"
        ]
        subprocess.run(cmd_fallback, check=True)

    print("🎉 تم استخراج شورتس المباراة بجودة عالية: final_shorts.mp4")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("الاستخدام: python process_video.py <channel_key> <youtube_url> [title]")
        sys.exit(1)

    channel_arg = sys.argv[1]
    url_arg = sys.argv[2]
    title_arg = sys.argv[3] if len(sys.argv) > 3 else "أقوى لقطات المنتخبات 🔥⚽"

    download_and_extract_audio(url_arg)
    s, e = find_best_single_highlight()
    render_vertical_short(s, e, title_arg)
    print("✅ اكتمل المونتاج بنجاح.")
