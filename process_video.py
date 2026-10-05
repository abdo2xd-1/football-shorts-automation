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

def find_best_goal_moment(audio_file="audio.wav"):
    """تحديد لقطة الهدف وتفادي البدايات والمراسم"""
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    # تخطي أول 90 ثانية لضمان استبعاد النشيد الوطني والمراسم
    total_duration = times[-1] if len(times) > 0 else 0
    skip_start = min(90.0, total_duration * 0.2)
    valid_indices = [i for i, t in enumerate(times) if t > skip_start]

    if not valid_indices:
        return 90, 120

    # البحث عن أعلى قمة صوتية (صراخ الهدف)
    max_idx = valid_indices[np.argmax(rms[valid_indices])]
    peak_time = times[max_idx]

    # أخذ 12 ثانية قبل الصراخ (الهجمة والتسديد) و18 ثانية بعده (الاحتفال)
    start_time = max(0, peak_time - 12)
    end_time = start_time + 30
    return start_time, end_time

def render_clean_short(raw_video, start_time, duration, title_text, output_file):
    # تنظيف العنوان ليبقى مختصراً داخل الشريط
    clean_title = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', '', title_text)
    clean_title = " ".join(clean_title.split()[:5])

    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]drawbox=y=140:color=black@0.65:width=iw:height=120:t=fill,"
        f"drawtext=text='{clean_title}':fontsize=36:fontcolor=white:x=(w-text_w)/2:y=180[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", raw_video,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a",
        "-af", f"afade=t=in:ss=0:d=0.4,afade=t=out:st={duration - 0.4}:d=0.4",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ]
    subprocess.run(cmd, check=True)

def process_all_matches():
    if not os.path.exists("matches_queue.json"):
        print("ℹ لا يوجد ملف مهام matches_queue.json")
        return

    with open("matches_queue.json", "r", encoding="utf-8") as f:
        queue = json.load(f)

    if not queue:
        print("ℹ قائمة المباريات فارغة لليوم.")
        return

    os.makedirs("output_shorts", exist_ok=True)

    for idx, match in enumerate(queue):
        url = match["url"]
        title = match["title"]
        teams = match.get("teams", f"Match_{idx+1}")
        print(f"\n🎬 [{idx+1}/{len(queue)}] معالجة: {teams}")

        raw_name = f"raw_{idx}.mp4"
        audio_name = f"audio_{idx}.wav"
        safe_teams = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '_', teams)
        out_short = f"output_shorts/short_{idx+1}_{safe_teams}.mp4"

        try:
            download_video(url, raw_name)
            subprocess.run(["ffmpeg", "-y", "-i", raw_name, "-vn", "-ar", "22050", "-ac", "1", audio_name], check=True)
            s, e = find_best_goal_moment(audio_name)
            render_clean_short(raw_name, s, 30, title, out_short)
            print(f"✅ تم إنتاج: {out_short}")
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
    process_all_matches()
