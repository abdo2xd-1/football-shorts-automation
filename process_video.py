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

def extract_audio_highlights_90s(audio_file="audio.wav"):
    """تحديد أفضل 6 إلى 8 لقطات لبناء ملخص متكامل مدته 90 ثانية (دقيقة ونصف)"""
    y, sr = librosa.load(audio_file, sr=22050)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr)

    # تخطي أول 75 ثانية لضمان استبعاد مراسم النشيد الوطني
    valid_indices = [i for i, t in enumerate(times) if t > 75]
    if not valid_indices:
        return [(75 + i * 12, 87 + i * 12) for i in range(7)]

    valid_rms = rms[valid_indices]
    threshold = np.percentile(valid_rms, 78)
    peaks = [times[i] for i in valid_indices if rms[i] > threshold]

    clips = []
    last_end = -30

    for p in peaks:
        if p - last_end > 14:
            start = max(0, p - 4.5)
            end = p + 7.5  # لقطة مدتها 12 ثانية (بناء الهجمة + الهدف + الفرحة)
            clips.append((start, end))
            last_end = end
            if len(clips) >= 7:  # 7 لقطات × ~13 ثانية = ~90 ثانية (دقيقة ونصف)
                break

    if len(clips) < 4:
        base = 80
        clips = [(base + i * 12, base + (i + 1) * 12) for i in range(7)]

    return clips

def render_multi_clip_short(raw_video, clips, raw_title, output_file):
    # تنظيف العنوان واختصار كلماته الأساسية فقط ليظهر منسقاً
    clean_title = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', ' ', raw_title)
    words = [w for w in clean_title.split() if w not in ["ملخص", "مباراة", "وأهداف", "اهداف", "اليوم", "شاهد", "كاملة", "HD"]]
    header_title = " ".join(words[:4]) if words else "ملخص وأهداف المباراة"

    clip_files = []
    for idx, (s, e) in enumerate(clips):
        part_name = f"part_{idx}.mp4"
        duration = e - s

        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]drawbox=y=130:color=black@0.65:width=iw:height=120:t=fill,"
            f"drawtext=text='{header_title}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=170[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(s),
            "-t", str(duration),
            "-i", raw_video,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",
            "-af", f"afade=t=in:ss=0:d=0.25,afade=t=out:st={duration - 0.25}:d=0.25",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            part_name
        ]
        subprocess.run(cmd, check=True)
        clip_files.append(part_name)

    # دمج اللقطات في ملف نهائي مدته 90 ثانية
    with open("concat_list.txt", "w", encoding="utf-8") as f:
        for p in clip_files:
            f.write(f"file '{p}'\n")

    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", output_file], check=True)

    # تنظيف الملفات المؤقتة
    for p in clip_files:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists("concat_list.txt"):
        os.remove("concat_list.txt")

def process_all():
    if not os.path.exists("matches_queue.json"):
        print("ℹ لا يوجد ملف matches_queue.json")
        return

    with open("matches_queue.json", "r", encoding="utf-8") as f:
        queue = json.load(f)

    if not queue:
        print("ℹ لم يتم العثور على مباريات مطابقة للشروط لهذه القناة اليوم.")
        return

    os.makedirs("output_shorts", exist_ok=True)

    for idx, match in enumerate(queue):
        url = match["url"]
        title = match.get("title", f"مباراة_{idx+1}")

        print(f"\n🎬 إنتاج ملخص دقيقة ونصف (90s): {title}")
        raw_name = f"raw_{idx}.mp4"
        audio_name = f"audio_{idx}.wav"
        out_short = f"output_shorts/short_{idx+1}.mp4"

        try:
            download_video(url, raw_name)
            subprocess.run(["ffmpeg", "-y", "-i", raw_name, "-vn", "-ar", "22050", "-ac", "1", audio_name], check=True)
            clips = extract_audio_highlights_90s(audio_name)
            render_multi_clip_short(raw_name, clips, title, out_short)
            print(f"✅ تم إنتاج الملخص النهائي بنجاح: {out_short}")
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
