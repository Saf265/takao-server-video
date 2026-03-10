from models import ClipSecondStep, ClipFirstStep, VoiceOverModel, KaraokeRequest
import anyio

from services.functions.add_music import add_music
from services.functions.add_video import add_video
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
from services.functions.add_subtitle import add_karaoke_subtitles
from services.functions.create_voiceover import create_voiceover
from services.functions.r2.r2_upload import upload_video

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://takao.app",
    "https://www.takao.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/process-video-first")
async def create_video(request: ClipFirstStep):
    
  # Exécution du traitement dans un thread séparé
  base_video_path = await anyio.to_thread.run_sync(add_video, request.clip_url, request.settings.is_blur_background)

  final_video_path = base_video_path
  ## add music
  if request.settings.background_music_url:
    final_video_path = await anyio.to_thread.run_sync(add_music, base_video_path, request.settings.background_music_url)

  # Upload asynchrone pour ne pas bloquer
  url = await anyio.to_thread.run_sync(upload_video, final_video_path)
  return {"message": "Output Generated! | First Step Done", "output": url, "success": True }


@app.post("/process-video-second")
async def create_video_second(request: ClipSecondStep, background_tasks: BackgroundTasks):
  # Création du payload pour create_voiceover
  voiceover_payload = VoiceOverModel(
      voice=request.settings.voice,
      language=request.settings.language,
      start_time=request.start_time,
      end_time=request.end_time,
      subtitles=request.subtitles
  )
  
  # Generation de l'audio dans un thread
  voiceover_result = await anyio.to_thread.run_sync(create_voiceover, voiceover_payload)
  
  # create_voiceover returns a dict with 'output' key
  if isinstance(voiceover_result, dict) and "output" in voiceover_result:
      voiceover_path = voiceover_result["output"]
  else:
      voiceover_path = voiceover_result

  # On uploade l'audio pour avoir une URL publique
  voiceover_url = await anyio.to_thread.run_sync(upload_video, voiceover_path)

  # On prépare la requête pour les sous-titres karaoké
  karaoke_request = KaraokeRequest(
      video_url=request.clip_url,
      audio_url=voiceover_url,
      language=request.settings.language,
      caption_color=request.settings.caption_color
  )

  # On génère la vidéo finale avec sous-titres (add_karaoke_subtitles est deja async)
  final_local_video = await add_karaoke_subtitles(karaoke_request, background_tasks)

  # Gérer les potentielles erreurs retournées au format dictionnaire par add_karaoke_subtitles
  if isinstance(final_local_video, dict) and "error" in final_local_video:
      return final_local_video

  # On upload la vidéo du karaoké sur R2 au lieu de renvoyer le fichier brut
  final_url = await anyio.to_thread.run_sync(upload_video, final_local_video)

  return {
      "message": "Output Generated! | Second Step Done", 
      "success": True, 
      "output": final_url
  }