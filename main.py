from services.functions.create_voiceover import create_voiceover
from models import ClipSecondStep, ClipFirstStep, VoiceOverModel

from services.functions.add_music import add_music
from services.functions.add_video import add_video
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
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
def create_video(request: ClipFirstStep):
  base_video_path = add_video(request.clip_url, request.settings.is_blur_background)

  final_video_path = base_video_path
  ## add music
  if request.settings.background_music_url:
    final_video_path = add_music(base_video_path, request.settings.background_music_url)

  url = upload_video(final_video_path)
  return {"message": "Output Generated! | First Step Done", "output": url, "success": True }


@app.post("/process-video-second")
def create_video_second(request: ClipSecondStep):
  # Création du payload pour create_voiceover
  voiceover_payload = VoiceOverModel(
      voice=request.settings.voice,
      language=request.settings.language,
      start_time=request.start_time,
      end_time=request.end_time,
      subtitles=request.subtitles
  )
  
  voiceover_path = create_voiceover(voiceover_payload)

  voiceover_url = upload_video(voiceover_path)

  return {
      "message": "Output Generated! | Second Step Done", 
      "success": True, 
      "output":voiceover_url
  }