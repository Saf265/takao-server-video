import uuid
from services.functions.r2.r2_upload import upload_video
from models import VoiceOverModel
import os
from google import genai
from google.genai import types
import wave

GEN_AI_API_KEY= os.environ["GEN_AI_API_KEY"]

def create_voiceover(data: VoiceOverModel):
  # On récupère les captions qui sont entre start_time et end_time inclus
  filtered_subtitles = []

  for subtitle in data.subtitles:
      subtitle_end = subtitle.start + subtitle.duration
      if subtitle.start <= data.end_time and subtitle_end >= data.start_time:
          filtered_subtitles.append(subtitle.text)
  clip_text = " ".join(filtered_subtitles)
  full_text = " ".join([s.text for s in data.subtitles])

  prompt = f"""
You are a viral short-form video writer.

Your job is to create a viral voice over for a clip.

Rules:
- The voice over must be between 190 and 210 words
- The tone must be engaging and emotional
- Make it optimized for TikTok / Reels / Shorts
- Use strong hooks and curiosity
- Short sentences
- No emojis
- No explanations
- Keep sentences under 12 words
- Use natural pauses

Full video subtitles (context):
{full_text}

Clip subtitles (important part):
{clip_text}

Write the final voice over narration.
"""
  client = genai.Client(api_key=GEN_AI_API_KEY)

  response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
  )

  print(response)
  if not response.text:
    raise ValueError("Gemini did not return a script")
  script = response.text

  response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=script,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=data.voice   # ta voix préselectionnée
                )
            )
        )
    )
  )
  audio_bytes = response.candidates[0].content.parts[0].inline_data.data

  filename = f"voiceover_{uuid.uuid4()}.wav"
  filepath = os.path.join("tmp", filename)
  os.makedirs("tmp", exist_ok=True)
  with wave.open(filepath, "wb") as wf:
      wf.setnchannels(1)
      wf.setsampwidth(2)
      wf.setframerate(24000)
      wf.writeframes(audio_bytes)



  return {"success": True, "output": filepath}

    