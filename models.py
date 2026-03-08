from pydantic import BaseModel
from typing import Optional

# ! ----------------------------------- FIRST STEP -----------------------------------------

class VideoSettingsFirstStep(BaseModel):
    background_music_url: Optional[str] = None
    is_blur_background: bool

class ClipFirstStep(BaseModel):
    clip_url: str
    settings: VideoSettingsFirstStep



# ! ----------------------------------- SECOND STEP -----------------------------------------

class VideoSettingsSecondStep(BaseModel):
    voice:str
    language:str
    caption_color: Optional[str] = None


class SubtilteDict(BaseModel):
    text: str
    start: float
    duration: float

class ClipSecondStep(BaseModel):
    id: int
    clip_url: str
    settings: VideoSettingsSecondStep
    start_time: float
    end_time: float
    subtitles: list[SubtilteDict]

# * ----------------------- SECOND STEP - VOICEOVER --------------

class VoiceOverModel(BaseModel):
    voice: str
    language: str
    start_time: float
    end_time: float
    subtitles: list[SubtilteDict]

class KaraokeRequest(BaseModel):
    video_url: str
    audio_url: Optional[str] = None
    language: str = "fr"
    caption_color: Optional[str] = None