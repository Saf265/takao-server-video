import subprocess
from services.functions.add_video import download_file
import uuid
import os
def add_voiceover(voiceover_tmp: str, base_video_url: str):
  uid = uuid.uuid4().hex
  base_video_tmp = f"tmp/base_video_{uid}.mp4"
  output_path = f"tmp/final_with_voiceover_{uid}.mp4"

  try:
    # 1. Télécharger la musique
    download_file(base_video_url, base_video_tmp)
        
    volume = 0.8
    audio_filter = f"[1:a]volume={volume}[voice];[0:a][voice]amix=inputs=2:duration=first[a]"

    # 2. Mixer l'audio et la vidéo
    cmd = [
    "ffmpeg",
    "-i", base_video_tmp,
    "-i", voiceover_tmp,
    "-filter_complex", audio_filter,
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
    if os.path.exists(voiceover_tmp):
        os.remove(voiceover_tmp)
    return output_path

  except Exception as e:
      print(f"Erreur lors du mixage audio : {e}")
      return None

  finally:
      # La musique temporaire est supprimée quoi qu'il arrive
      if os.path.exists(base_video_tmp):
          os.remove(base_video_tmp)