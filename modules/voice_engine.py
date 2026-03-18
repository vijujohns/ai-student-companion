
import sounddevice as sd
from scipy.io.wavfile import write
import whisper

model=None

def load_model():
    global model
    if model is None:
        model=whisper.load_model("base")
    return model

def record_voice():
    fs=16000
    seconds=5
    recording=sd.rec(int(seconds*fs),samplerate=fs,channels=1)
    sd.wait()
    file="voice.wav"
    write(file,fs,recording)
    return file

def speech_to_text(file):
    m=load_model()
    result=m.transcribe(file)
    return result["text"]
