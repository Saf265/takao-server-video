import os
import uuid
import requests
import subprocess
import shutil
import json
import traceback
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# --- CONFIG ---
LEMONFOX_API_KEY = os.environ["LEMONFOX_API_KEY"] 
client = OpenAI(
    api_key=LEMONFOX_API_KEY,
    base_url="https://api.lemonfox.ai/v1"
)

# --- Models ---
class WordItem(BaseModel):
    text: str
    start: float
    duration: float

class KaraokeRequest(BaseModel):
    video_url: str
    audio_url: Optional[str] = None

# --- Utils ---
def format_ass_timestamp(seconds: float) -> str:
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    m = int((seconds // 60) % 60)
    s = int(seconds % 60)
    c = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"

def hex_to_ass_color(hex_color: Optional[str]) -> str:
    if not hex_color:
        return "00FF00"  # default green
    clean_hex = hex_color.lstrip('#')
    if len(clean_hex) == 6:
        # rrggbb -> bbggrr
        return f"{clean_hex[4:6]}{clean_hex[2:4]}{clean_hex[0:2]}"
    elif len(clean_hex) == 3:
        # rgb -> bbggrr
        r = clean_hex[0] * 2
        g = clean_hex[1] * 2
        b = clean_hex[2] * 2
        return f"{b}{g}{r}"
    return "00FF00"

def cleanup_dir(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)
    print(f"Cleaned up: {path}")

def get_video_dimensions(video_path: str):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return int(data["streams"][0]["width"]), int(data["streams"][0]["height"])
    except:
        return 1080, 1920 # Default vertical

def has_audio(file_path: str) -> bool:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "json", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        return len(data.get("streams", [])) > 0
    except:
        return False

async def add_karaoke_subtitles(request: KaraokeRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())
    work_dir = os.path.join(os.getcwd(), "tmp", f"karaoke_{session_id}")
    os.makedirs(work_dir, exist_ok=True)

    video_path = os.path.join(work_dir, "video.mp4")
    audio_path = os.path.join(work_dir, "audio.wav")
    ass_path = os.path.join(work_dir, "subtitles.ass")
    output_path = os.path.join(work_dir, "output.mp4")

    try:
        # 1. Téléchargement
        rv = requests.get(request.video_url, stream=True, timeout=60)
        with open(video_path, "wb") as f:
            for chunk in rv.iter_content(8192): f.write(chunk)
        
        target_audio_file = video_path
        has_external_audio = False
        if request.audio_url:
            ra = requests.get(request.audio_url, stream=True, timeout=60)
            with open(audio_path, "wb") as f:
                for chunk in ra.iter_content(8192): f.write(chunk)
            target_audio_file = audio_path
            has_external_audio = True

        # 2. Transcription Whisper
        with open(target_audio_file, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                language=request.language,
                timestamp_granularities=["word"]
            )

        words: List[WordItem] = []
        raw_data = transcript if isinstance(transcript, dict) else transcript.model_dump()
        segments = raw_data.get('segments', [])
        
        all_words = []
        if segments:
            for s in segments:
                all_words.extend(s.get('words', []))
        else:
            all_words = raw_data.get('words', [])

        for w in all_words:
            words.append(WordItem(
                text=w.get('word', '').strip(),
                start=float(w.get('start', 0)),
                duration=max(0.05, float(w.get('end', 0)) - float(w.get('start', 0)))
            ))

        if not words:
            raise ValueError("Aucun mot trouvé.")

        # 3. Dimensions & Style (Calcul Font Size & Alignement 2)
        w_vid, h_vid = get_video_dimensions(video_path)
        # On baisse la taille : h / 22 au lieu de 15 ou 18
        font_size = int(h_vid / 26) 

        content = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {w_vid}",
            f"PlayResY: {h_vid}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            # Alignment 2 = Milieu Bas | MarginV 80 pour pas que ce soit collé au bord
            f"Style: Default,Arial,{font_size},&HFFFFFF&,&H0000FF&,&H000000&,&H000000&,1,0,0,0,100,100,0,0,1,3,2,2,30,30,80,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        # 4. Génération des lignes synchronisées
        chunk_size = 7
        ass_highlight_color = hex_to_ass_color(request.caption_color)
        
        for i in range(len(words)):
            start_chunk = (i // chunk_size) * chunk_size
            end_chunk = min(len(words), start_chunk + chunk_size)
            phrase_words = words[start_chunk:end_chunk]

            t_start = format_ass_timestamp(words[i].start)
            # Fin au début du mot suivant ou fin du mot actuel
            if i + 1 < len(words) and (i + 1) < end_chunk:
                t_end = format_ass_timestamp(words[i+1].start)
            else:
                t_end = format_ass_timestamp(words[i].start + words[i].duration)

            line_parts = []
            for idx, w_item in enumerate(phrase_words):
                if (start_chunk + idx) == i:
                    line_parts.append(f"{{\\c&H{ass_highlight_color}&}}{w_item.text}{{\\c&HFFFFFF&}}")
                else:
                    line_parts.append(w_item.text)
            
            text_line = " ".join(line_parts)
            content.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{text_line}")

        with open(ass_path, "w", encoding="utf-8") as f:
            f.writelines(l + "\n" for l in content)

        # 5. FFmpeg (Mapping Video + Audio)
        clean_ass_path = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", video_path]
        
        if has_external_audio:
            # On ajoute l'audio externe comme 2ème input
            ffmpeg_cmd += ["-i", audio_path]
            
            # On vérifie si la vidéo originale a du son
            if has_audio(video_path):
                # On mixe l'audio original (0:a) avec l'audio externe (1:a)
                # Et on applique le sous-titre karaoké dans le même filter_complex
                ffmpeg_cmd += [
                    "-filter_complex", 
                    f"[0:v]ass='{clean_ass_path}'[v];[0:a][1:a]amix=inputs=2:duration=first[a]",
                    "-map", "[v]", 
                    "-map", "[a]"
                ]
            else:
                # La vidéo n'a pas de son, on utilise uniquement l'audio externe
                ffmpeg_cmd += [
                    "-filter_complex", 
                    f"[0:v]ass='{clean_ass_path}'[v]",
                    "-map", "[v]", 
                    "-map", "1:a"
                ]
        else:
            # On prend TOUT l'audio du fichier original (0:a?) 
            # Le '?' évite que ça crash si la vidéo n'a pas de son du tout
            ffmpeg_cmd += [
                "-vf", f"ass='{clean_ass_path}'",
                "-map", "0:v:0", 
                "-map", "0:a?"
            ]

        ffmpeg_cmd += [
            "-c:v", "libx264", 
            "-preset", "ultrafast",
            "-c:a", "aac", 
            "-b:a", "192k",
            "-ac", "2", # Force en stéréo pour éviter les problèmes de compatibilité
            "-map_metadata", "0", # Garde les métadonnées originales (date, rotation, etc.)
            "-shortest", 
            output_path
        ]

        process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {process.stderr}")

        background_tasks.add_task(cleanup_dir, work_dir)
        return output_path

    except Exception as e:
        traceback.print_exc()
        cleanup_dir(work_dir)
        return {"error": str(e)}
