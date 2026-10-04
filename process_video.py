def download_and_extract_audio(raw_url: str):
    clean_link = clean_url(raw_url)
    print(f"⬇️ جاري تنزيل الفيديو من الرابط: {clean_link}")

    cmd_download = [
        "yt-dlp",
        "--no-check-certificates",
        "--js-runtimes", "node",
        "-f", "best[ext=mp4]/best",
        "-o", "raw_match.mp4"
    ]

    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
        print("🔑 استخدام Cookies لتسجيل الدخول...")
        cmd_download.extend(["--cookies", "cookies.txt"])

    cmd_download.append(clean_link)
    subprocess.run(cmd_download, check=True)

    print("🎵 استخراج الصوت لتحليله...")
    cmd_audio = [
        "ffmpeg", "-y", "-i", "raw_match.mp4",
        "-vn", "-ar", "22050", "-ac", "1", "audio.wav"
    ]
    subprocess.run(cmd_audio, check=True)
