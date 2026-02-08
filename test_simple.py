import fal_client
import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
os.environ["FAL_KEY"] = os.getenv("FAL_API_KEY", "")

VIDEO_PATH = "./"
OUTPUT_ROOT = "./output"
START = 3.0  # def start frame
END = 7.0  # def end frame


def extract_clip(input_path, start, end, output_path):
    duration = end - start
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            input_path,
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-avoid_negative_ts",
            "make_zero",
            output_path,
        ],
        check=True,
        capture_output=True,
    )


def stitch_videos(before, edited, after, output, run_dir):
    concat_list = os.path.join(run_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for clip in [before, edited, after]:
            if clip and os.path.exists(clip):
                f.write(f"file '{clip}'\n")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output,
        ],
        check=True,
        capture_output=True,
    )


def get_duration(video_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def main():
    print("=" * 60)
    print("VIDEO INTERVAL EDITOR")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(OUTPUT_ROOT, f"{timestamp}_v2v_edit")
    os.makedirs(run_dir, exist_ok=True)

    print(f"\nVideo: {VIDEO_PATH}")
    print(f"Interval: {START}s → {END}s")
    print(f"Output: {run_dir}\n")

    prompt = input("Edit prompt: ").strip()

    print("\n[1/5] Extracting clips...")
    video_duration = get_duration(VIDEO_PATH)

    clip_before = os.path.join(run_dir, "before.mp4")
    clip_interval = os.path.join(run_dir, "interval.mp4")
    clip_after = os.path.join(run_dir, "after.mp4")

    extract_clip(VIDEO_PATH, 0, START, clip_before)
    extract_clip(VIDEO_PATH, START, END, clip_interval)
    extract_clip(VIDEO_PATH, END, video_duration, clip_after)

    print("[2/5] Uploading interval clip...")
    interval_url = fal_client.upload_file(clip_interval)

    print("[3/5] Running Kling O1 V2V Edit...")
    print(f"Prompt: {prompt}")

    result = fal_client.subscribe(
        "fal-ai/kling-video/o1/video-to-video/edit",
        arguments={
            "prompt": prompt,
            "video_url": interval_url,
        },
        with_logs=True,
    )

    edited_url = result["video"]["url"]

    print("[4/5] Downloading edited clip")
    edited_clip = os.path.join(run_dir, "edited.mp4")
    subprocess.run(["curl", "-sL", "-o", edited_clip, edited_url], check=True)

    print("[5/5] Stitching vid")
    final_output = os.path.join(run_dir, "final.mp4")
    stitch_videos(clip_before, edited_clip, clip_after, final_output, run_dir)

    print("DONE!")
    print(f"Output folder: {run_dir}")


if __name__ == "__main__":
    main()
