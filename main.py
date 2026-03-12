from models import ClipSecondStep, ClipFirstStep, VoiceOverModel, KaraokeRequest
import anyio
import httpx

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

async def notify_webhook(webhook_url: str, job_id: str, success: bool, output: str = None, message: str = None):
    async with httpx.AsyncClient() as client:
        payload = {
            "job_id": job_id,
            "success": success,
            "output": output,
            "message": message
        }
        try:
            response = await client.post(webhook_url, json=payload)
            print(f"Webhook sent to {webhook_url}, status: {response.status_code}")
        except Exception as e:
            print(f"Error sending webhook to {webhook_url}: {e}")

async def process_video_first_task(request: ClipFirstStep):
  try:
    # Exécution du traitement dans un thread séparé
    base_video_path = await anyio.to_thread.run_sync(add_video, request.clip_url, request.settings.is_blur_background)

    final_video_path = base_video_path
    ## add music
    if request.settings.background_music_url:
      final_video_path = await anyio.to_thread.run_sync(add_music, base_video_path, request.settings.background_music_url)

    # Upload asynchrone pour ne pas bloquer
    url = await anyio.to_thread.run_sync(upload_video, final_video_path)
    
    if request.webhook_url:
      await notify_webhook(request.webhook_url, request.job_id, True, url, "Output Generated! | First Step Done")
    return url
  except Exception as e:
    print(f"Error in process_video_first_task: {e}")
    if request.webhook_url:
      await notify_webhook(request.webhook_url, request.job_id, False, None, str(e))
    return None

async def process_video_second_task(request: ClipSecondStep, background_tasks: BackgroundTasks):
  try:
    voiceover_payload = VoiceOverModel(
        voice=request.settings.voice,
        language=request.settings.language,
        start_time=request.start_time,
        end_time=request.end_time,
        subtitles=request.subtitles
    )
    
    voiceover_result = await anyio.to_thread.run_sync(create_voiceover, voiceover_payload)
    
    if isinstance(voiceover_result, dict) and "output" in voiceover_result:
        voiceover_path = voiceover_result["output"]
    else:
        voiceover_path = voiceover_result

    voiceover_url = await anyio.to_thread.run_sync(upload_video, voiceover_path)

    karaoke_request = KaraokeRequest(
        video_url=request.clip_url,
        audio_url=voiceover_url,
        language=request.settings.language,
        caption_color=request.settings.caption_color
    )

    final_local_video = await add_karaoke_subtitles(karaoke_request, background_tasks)

    if isinstance(final_local_video, dict) and "error" in final_local_video:
        if request.webhook_url:
          await notify_webhook(request.webhook_url, request.job_id, False, None, final_local_video["error"])
        return

    final_url = await anyio.to_thread.run_sync(upload_video, final_local_video)

    if request.webhook_url:
      await notify_webhook(request.webhook_url, request.job_id, True, final_url, "Output Generated! | Second Step Done")
    return final_url
  except Exception as e:
    print(f"Error in process_video_second_task: {e}")
    if request.webhook_url:
      await notify_webhook(request.webhook_url, request.job_id, False, None, str(e))
    return None

@app.post("/process-video-first")
async def create_video(request: ClipFirstStep, background_tasks: BackgroundTasks):
  if request.webhook_url:
    background_tasks.add_task(process_video_first_task, request)
    return {"message": "Processing started in background", "job_id": request.job_id, "success": True}
    
  url = await process_video_first_task(request)
  return {"message": "Output Generated! | First Step Done", "output": url, "success": True if url else False }


@app.post("/process-video-second")
async def create_video_second(request: ClipSecondStep, background_tasks: BackgroundTasks):
  if request.webhook_url:
    background_tasks.add_task(process_video_second_task, request, background_tasks)
    return {"message": "Processing started in background", "job_id": request.job_id, "success": True}

  final_url = await process_video_second_task(request, background_tasks)
  return {
      "message": "Output Generated! | Second Step Done", 
      "success": True if final_url else False, 
      "output": final_url
  }