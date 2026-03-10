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

        # Utilisation de force_original_aspect_ratio=increase pour garantir que l'image
        # remplit TOUJOURS la zone de crop, peu importe le ratio d'entrée.
        if use_blur:
            filter_complex = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=15[bg]; "
                "[0:v]scale=1080:1344:force_original_aspect_ratio=increase,crop=1080:1344[inner]; "
                "[bg][inner]overlay=(W-w)/2:(H-h)/2:shortest=1"
            )
            inputs = ["-i", input_path]
        else:
            filter_complex = (
                "[1:v]scale=1080:1344:force_original_aspect_ratio=increase,crop=1080:1344[inner]; "
                "[0:v][inner]overlay=(W-w)/2:(H-h)/2:shortest=1"
            )
            inputs = [
                "-f", "lavfi", "-i", "color=c=black:s=1080x1920",
                "-i", input_path
            ]

        cmd = [
            "ffmpeg",
            *inputs,
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p", # Assure la compatibilité maximale
            "-an", 
            "-y",
            output_path
        ]

        # On capture stderr pour voir exactement pourquoi FFmpeg râle si ça échoue
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg Standard Error: {result.stderr}")
            raise Exception(f"FFmpeg failed with return code {result.returncode}")

        return output_path

    except Exception as e:
        print(f"Erreur lors de add_video: {e}")
        raise e

    finally:
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except:
                pass