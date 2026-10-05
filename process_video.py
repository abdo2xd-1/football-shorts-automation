import os
import sys
import re
import json
import subprocess
import numpy as np
import librosa

YOUTUBE_COOKIES_DATA = os.getenv("YOUTUBE_COOKIES")

def clean_url(url: str) -> str:
    cleaned = url.strip().strip("'\"").replace(" ", "")
    match = re.search(r'(?:v=|\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})', cleaned)
    return f"https://www.youtube.com/watch?v={match.group(1)}" if match else cleaned

def prepare_cookies():
    cookie_path = os.path.abspath("cookies.txt")
    if YOUTUBE_COOKIES_DATA and len(YOUTUBE_COOKIES_DATA.strip()) > 30:
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES_DATA.strip() + "\n")
        return cookie_path
    return None

def download_video(raw_url: str, output_raw="match_raw.mp4"):
    clean_link = clean_url(raw_url)
    cookie_file = prepare_cookies()

    cmd = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "--extractor-args", "youtube:player_client=web,web_embedded",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "-o", output_raw
    ]
    if cookie_file:
        cmd.extend(["--cookies", cookie_file])
    cmd.append(clean_link)

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        cmd_fallback = [
            "yt-dlp",
            "--no-check-certificates",
            "--geo-bypass",
            "-f", "b/best",
            "-o", output_raw
        ]
        if cookie_file:
            cmd_fallback.extend(["--cookies", cookie_file])
        cmd_fallback.append(clean_link)
        subprocess.run(cmd_fallback, check=True)

def find_best_90s_window(audio_file="audio.wav"):
    """تحديد أفضل وأقوى نافذة متصلة مدتها 90 ثانية (دقيقة ونصف) تشمل أقصى حماس وأهداف"""
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    # تخطي أول 60 ثانية لاستبعاد المراسم والنشيد الوطني
    valid_indices = [i for i, t in enumerate(times) if t > 60]
    if not valid_indices or times[-1] < 150:
        return 60, 150

    total_len = len(times)
    window_frames = int(90 * sr / 512)

    # البحث عن النافذة التي تحوي أعلى طاقة صوتية متراكمة (أكبر عدد من الأهداف والهجمات)
    best_start_idx = valid_indices[0]
    max_energy = -1

    step = int(5 * sr / 512)  # فحص كل 5 ثوانٍ لتسريع العملية
    for i in range(valid_indices[0], total_len - window_frames, max(1, step)):
        window_energy = np.sum(rms[i:i + window_frames])
        if window_energy > max_energy:
            max_energy = window_energy
            best_start_idx = i

    start_time = max(60, times[best_start_idx])
    end_time = start_time + 90
    return start_time, end_time

def render_90s_short(raw_video, start_time, duration, title_clean, output_file):
    header_title = title_clean.strip()

    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]drawbox=y=130:color=black@0.65:width=iw:height=120:t=fill,"
        f"drawtext=text='{header_title}':fontsize=38:fontcolor=white:x=(w-text_w)/2:y=170[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", raw_video,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a",
        "-af", f"afade=t=in:ss=0:d=0.5,afade=t=out:st={duration - 0.5}:d=0.5",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ]
    subprocess.run(cmd, check=True)

def process_all():
    if not os.path.exists("matches_queue.json"):
        print("ℹ لا يوجد ملف matches_queue.json")
        return

    with open("matches_queue.json", "r", encoding="utf-8") as f:
        queue = json.load(f)

    if not queue:
        print("ℹ لا توجد مباريات مسجلة في القائمة اليوم.")
        return

    os.makedirs("output_shorts", exist_ok=True)

    for idx, match in enumerate(queue):
        url = match["url"]
        title = match.get("title", f"مباراة {idx+1}")
        teams = match.get("teams", f"Match_{idx+1}")

        print(f"\n🎬 معالجة ملخص دقيقة ونصف (90 ثانية): {title}")
        raw_name = f"raw_{idx}.mp4"
        audio_name = f"audio_{idx}.wav"
        safe_name = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '_', teams)
        out_short = f"output_shorts/short_{idx+1}_{safe_name}.mp4"

        try:
            download_video(url, raw_name)
            subprocess.run(["ffmpeg", "-y", "-i", raw_name, "-vn", "-ar", "22050", "-ac", "1", audio_name], check=True)
            s, e = find_best_90s_window(audio_name)
            render_90s_short(raw_name, s, 90, title, out_short)
            print(f"✅ تم إنتاج الملخص بنجاح (90s): {out_short}")
        except Exception as e:
            print(f"❌ تعثر إنتاج هذه المباراة: {e}")
        finally:
            for tmp in [raw_name, audio_name]:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except:
                        pass

if __name__ == "__main__":
    process_all()
