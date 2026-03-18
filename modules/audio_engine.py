
from gtts import gTTS
import os

def text_to_speech(text):
    file="answer.mp3"
    tts=gTTS(text=text,lang="en")
    tts.save(file)
    if not os.path.exists(file):
        raise Exception("Audio generation failed")
    return file
