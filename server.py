import os
import torch
from optparse import OptionParser, Values
from typing import Annotated
import json
import logging
import time
import re
import base64
import numpy as np
from fastapi import FastAPI, Response, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json, uvicorn
import soundfile as sf
import tempfile
from generate import KokoroTTS
from kokoro_utils import blend_voice, setup_logging, get_audio_duration


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Make einx happy
os.environ["EINX_FILTER_TRACEBACK"] = "false"


def decorate_word_timestamps(word_timestamps):
    if word_timestamps is None:
        return None
    for word_timestamp in word_timestamps:
        word_timestamp['text'] = re.sub(r'[^a-zA-Z0-9]+$', '', word_timestamp['text'])
    word_timestamps = [word_timestamp for word_timestamp in word_timestamps if word_timestamp['text']]
    return word_timestamps

def yield_sse_event(data):
    return "data: " +json.dumps(data) + "\n\n"


@app.get("/ping")
def ping():
    return {"status": "success"}


@app.get("/tts/blend")
def blend(
    reference_id: str,
    voice1: str,
    voice2: str,
    blend: float,
    
):
    blend_voice(reference_id, voice1, voice2, blend)
    return {"status": "success"}



@app.get("/tts/generate")
def tts(
    text: str,
    reference_id: str = "1",
    speed: float = 0.8,
    streaming: bool = False,
    align: bool = False,
    accept: Annotated[str | None, Header()] = None
):
    
    if accept == "text/event-stream":
        streaming = True
    kokoro:KokoroTTS = app.kokoro
    
    sample_rate = 24000
    dtype = 'int16'
    
    if not streaming:
        t1 = time.time()
        audio, info = kokoro.generate(reference_id, text, speed=speed, trim_silence=True, align=align)
        logging.info(f"Time taken: {time.time() - t1}")
        temp_file = tempfile.mktemp(suffix='.wav')
        try:    
            sf.write(temp_file, audio, sample_rate)
            with open(temp_file, 'rb') as f:
                return Response(content=f.read(), media_type="audio/wav")
        finally:
            os.remove(temp_file)
    else:
        def eventStream():
            
            yield yield_sse_event({"action": 'init', 
                                        'text':text,
                                        'samplerate':sample_rate, 
                                        'data_type': dtype, 
                                        'channels':1})

            start_time = time.time()
            try:
                prev_duration = 0
                for audio, info in kokoro.generate_stream(voice=reference_id, 
                                                          text=text, 
                                                          speed=speed, 
                                                          trim_silence=True, 
                                                          align=align):
                    if audio is None: #error
                        yield yield_sse_event({"action": 'error', 
                                                    'error': info.get("error", "Unknown error")})
                        return
                    assert info["sample_rate"] == sample_rate
                    logs = info.get("logs", None)
                    word_timestamps = info.get("word_timestamps", None)

                    #word wise steaming
                    if word_timestamps:
                        print(word_timestamps)

                        MAX_SEND_WORDS = 5
                        prev_sent = 0
                        word_timestamps = [word_timestamp for word_timestamp in word_timestamps if word_timestamp['index'] is not None]
                        for word_timestamp in word_timestamps:
                            word_timestamp['start'] += prev_duration
                            word_timestamp['end'] += prev_duration
                        for i in range(0, len(word_timestamps), MAX_SEND_WORDS):
                            word_timestamps_part = word_timestamps[i:i+MAX_SEND_WORDS]
                            if not word_timestamps_part:
                                continue
                                
                            end = word_timestamps_part[-1]['end']
                            end_frame = int(end * sample_rate)
                            audio_part:np.ndarray = audio[prev_sent:end_frame]
                            prev_sent = end_frame
                            assert info["dtype"] == dtype
                            
                            yield yield_sse_event({
                                "action": 'segment', 
                                'samplerate':sample_rate, 
                                'audio':base64.b64encode(audio_part.tobytes()).decode("utf-8"),
                                'word_timestamps':decorate_word_timestamps(word_timestamps_part)
                            })
                        if end_frame < len(audio):
                            audio_part:np.ndarray = audio[end_frame:]
                            yield yield_sse_event({
                                "action": 'segment', 
                                'samplerate':sample_rate, 
                                'audio':base64.b64encode(audio_part.tobytes()).decode("utf-8"),
                                'word_timestamps' : []
                            })
                    else:
                        yield yield_sse_event({
                            "action": 'segment', 
                            'samplerate':sample_rate, 
                            'audio':base64.b64encode(audio.tobytes()).decode("utf-8"),
                            'word_timestamps' : None
                        })
                    prev_duration += get_audio_duration(audio, sample_rate)
            except Exception as e:
                yield yield_sse_event({"action": 'error', 
                                                'error': str(e)})
                return
            yield yield_sse_event({"action": "final"})
        return StreamingResponse(eventStream(), media_type="text/event-stream")



inference_engine = None
def setup_app(opts):
    setup_logging(logging.INFO)
    torch.multiprocessing.set_start_method('spawn')
    
    kokoro = KokoroTTS(device='cuda')
    text = 'Please meet me at 7:30 PM at 42nd Street and 5th Avenue in 2024 COVID-19. I will be wearing a red shirt worth 1$ and a blue shirt worth 2 $.'

    for audio, info in kokoro.generate_stream("1", text, speed=0.6, trim_silence=True, align=True):
        pass
    app.kokoro = kokoro
    logging.info("Engine Setup Done")

if __name__ == "__main__":
    #Thread(target=ws_main_thread).start()
    optparser = OptionParser()
    optparser.add_option('-m', '--model', type='string', default=os.environ.get('MODEL_DIR', f'checkpoints/fish-speech-1.5'))
    optparser.add_option('-p', '--port', type='int', default=13256)
    optparser.add_option('-c', '--compile', default=False, action='store_true')
    opts, args = optparser.parse_args()
    setup_app(opts)
    uvicorn.run(app, host="0.0.0.0", port=opts.port)
else:
    opts = Values()
    opts.ensure_value('model', os.environ.get('MODEL_DIR', f'checkpoints/fish-speech-1.5'))
    opts.ensure_value('compile', True)
    setup_app(opts)
