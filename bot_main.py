# ✅ Telegram Bot for Removing Vocals from Videos (5-Minute Chunks)
# 🔒 Secure: Loads TOKEN from .env
# ☁️ Ready for Render.com (no requirements.txt needed)
# 📦 Auto-installs dependencies with --only-binary to avoid build errors

import subprocess, sys, os, shutil, uuid

# === Auto-install required packages ===
required = ['python-telegram-bot==13.15', 'moviepy', 'spleeter', 'ffmpeg-python', 'python-dotenv']
for pkg in required:
    try:
        __import__(pkg.split('==')[0].replace('-', '_'))
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", pkg,
            "--only-binary", ":all:"
        ])

# === Imports after installation ===
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from moviepy.editor import VideoFileClip, AudioFileClip
from dotenv import load_dotenv

# === Load secure environment variables ===
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHUNK_DURATION = 300  # 5 minutes

# === Video processing function ===
def process_video(input_path: str, session_dir: str) -> list:
    from subprocess import run
    os.makedirs(session_dir, exist_ok=True)
    video = VideoFileClip(input_path)
    total_duration = int(video.duration)
    result_clips = []

    for i in range(0, total_duration, CHUNK_DURATION):
        start, end = i, min(i + CHUNK_DURATION, total_duration)
        name = f"chunk_{i//60:02d}_{(i%60):02d}"
        chunk_vid = os.path.join(session_dir, f"{name}.mp4")
        chunk_wav = os.path.join(session_dir, f"{name}.wav")

        clip = video.subclip(start, end)
        clip.write_videofile(chunk_vid, audio=True)
        clip.audio.write_audiofile(chunk_wav)

        os.system(f'python -m spleeter separate "{chunk_wav}" -p spleeter:2stems -o "{session_dir}"')
        accompaniment = os.path.join(session_dir, name, "accompaniment.wav")
        cleaned = os.path.join(session_dir, name, "cleaned.wav")

        if not os.path.exists(accompaniment): continue

        run(["ffmpeg", "-y", "-i", accompaniment,
             "-af", "afftdn=nf=-25,highpass=f=100,lowpass=f=12000",
             cleaned])

        if not os.path.exists(cleaned): continue

        new_vid = VideoFileClip(chunk_vid)
        new_audio = AudioFileClip(cleaned)
        if new_audio.duration > new_vid.duration:
            new_audio = new_audio.subclip(0, new_vid.duration)

        final = new_vid.set_audio(new_audio)
        out_path = os.path.join(session_dir, f"{name}_no_vocal.mp4")
        final.write_videofile(out_path)
        result_clips.append(out_path)

    return result_clips

# === Telegram Handlers ===
def start(update: Update, context: CallbackContext):
    update.message.reply_text("📥 Send me a video (.mp4), I’ll remove vocals and return 5-min clean chunks.")

def handle_video(update: Update, context: CallbackContext):
    file = update.message.video.get_file()
    uid = str(uuid.uuid4())[:8]
    workdir = f"session_{uid}"
    os.makedirs(workdir, exist_ok=True)
    input_path = f"{workdir}/input.mp4"
    file.download(input_path)
    update.message.reply_text("⚙️ Processing video...")

    try:
        clips = process_video(input_path, workdir)
        if clips:
            for c in clips:
                update.message.reply_video(video=open(c, 'rb'))
        else:
            update.message.reply_text("❌ Failed to process.")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {e}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# === Start Bot ===
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.video, handle_video))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
