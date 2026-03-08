import os
import uuid
import subprocess
import requests

def download_file(url, path):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def add_video(video_url: str, use_blur: bool = False):
    os.makedirs("tmp", exist_ok=True)
    uid = uuid.uuid4().hex
    input_path = f"tmp/input_{uid}.mp4"
    output_path = f"tmp/final_{uid}.mp4"

    try:
        download_file(video_url, input_path)

        # Calcul : 1920 * 0.70 = 1344 pixels de haut
        if use_blur:
            # Fond flou (100% hauteur) + Vidéo nette (70% hauteur soit 1344px)
            filter_complex = (
                "[0:v]scale=-2:1920,crop=1080:1920,gblur=sigma=15[bg]; "
                "[0:v]scale=-2:1344,crop=1080:1344[inner]; "
                "[bg][inner]overlay=(W-w)/2:(H-h)/2:shortest=1"
            )
            inputs = ["-i", input_path]
        else:
            # Correction : on enlève :d=1 pour que le fond noir ne limite pas la vidéo
            filter_complex = (
                "[1:v]scale=-2:1344,crop=1080:1344[inner]; "
                "[0:v][inner]overlay=(W-w)/2:(H-h)/2:shortest=1"
            )
            inputs = [
                "-f", "lavfi", "-i", "color=c=black:s=1080x1920", # Fond infini
                "-i", input_path
            ]

        cmd = [
            "ffmpeg",
            *inputs,
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-an", 
            "-y",
            output_path
        ]

        subprocess.run(cmd, check=True)
        return output_path

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)