from services.functions.add_video import download_file
import os
import uuid
import subprocess
def add_music(video_path: str, music_url: str):
    uid = uuid.uuid4().hex
    music_tmp = f"tmp/music_{uid}.mp3"
    output_path = f"tmp/final_with_audio_{uid}.mp4"

    try:
        # 1. Télécharger la musique
        download_file(music_url, music_tmp)
        
        volume = 0.5
        audio_filter = f"volume={volume},afade=t=in:st=0:d=1"

        # 2. Mixer l'audio et la vidéo
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", music_tmp,
            "-filter_complex", f"[1:a]{audio_filter}[a]",
            "-map", "0:v:0",
            "-map", "[a]",
            "-c:v", "copy", 
            "-c:a", "aac",
            "-shortest",
            "-y",
            output_path
        ]

        subprocess.run(cmd, check=True)

        # SI ET SEULEMENT SI subprocess a réussi, on supprime la vidéo intermédiaire
        if os.path.exists(video_path):
            os.remove(video_path)

        return output_path

    except Exception as e:
        print(f"Erreur lors du mixage audio : {e}")
        return None

    finally:
        # La musique temporaire est supprimée quoi qu'il arrive
        if os.path.exists(music_tmp):
            os.remove(music_tmp)