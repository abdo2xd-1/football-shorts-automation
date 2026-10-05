import os
import sys
import re
import subprocess
import requests
import numpy as np
import librosa
from config import CHANNELS

BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

def clean_url(url: str) -> str:
    cleaned = url.strip().strip("'\"").replace(" ", "")
    regex = r'(?:v=|\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(regex, cleaned)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return cleaned

def download_and_extract_audio(raw_url: str):
    clean_link = clean_url(raw_url)
    print(f"⬇️ جاري سحب الفيديو المباشر: {clean_link}")

    cmd_download = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "-o", "raw_match.mp4",
        clean_link
    ]

    try:
        subprocess.run(cmd_download, check=True)
    except subprocess.CalledProcessError:
        print("⚠️ جاري المحاولة بنمط البث المباشر المتوافق...")
        cmd_fallback = [
            "yt-dlp",
            "--no-check-certificates",
            "--geo-bypass",
            "-f", "b/best",
            "-o", "raw_match.mp4",
            clean_link
        ]
        subprocess.run(cmd_fallback, check=True)

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
    """
    إنتاج كادر عمودي 1080x1920 احترافي:
    1. طبقة خلفية مكبرة ومضببة تملأ الشاشة بالكامل (منع القطع والحدود السوداء)
    2. لقطة المباراة الأصلية كاملة بدون أي قص لعناصر اللعب أو وجوه المدربين
    3. شريط علوي أنيق يعطي سياق المواجهة لتعزيز الـ Retention
    """
    print("🎬 مونتاج الشورتس بالخلفية الضبابية الذكية والشريط الإخباري...")
    clip_list = []
    safe_title = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', '', match_title)[:45]

    for idx, (s, e) in enumerate(highlights):
        out_name = f"part_{idx}.mp4"
        duration = e - s

        # فلتر يدمج خلفية ضبابية مع كادر نقي في المنتصف وشريط بيانات
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
            # فلتر بديل في حال تعذر رسم النصوص
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
