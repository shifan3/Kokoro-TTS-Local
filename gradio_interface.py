"""
Kokoro-TTS Local Generator
-------------------------
A Gradio interface for the Kokoro-TTS-Local text-to-speech system.
Supports multiple voices and audio formats, with cross-platform compatibility.

Key Features:
- Multiple voice models support (26+ voices)
- Real-time generation with progress logging
- WAV, MP3, and AAC output formats
- Network sharing capabilities
- Cross-platform compatibility (Windows, macOS, Linux)

Dependencies:
- kokoro: Official Kokoro TTS library
- gradio: Web interface framework
- soundfile: Audio file handling
- pydub: Audio format conversion
"""

import gradio as gr
import torch
from generate import KokoroTTS, SAMPLE_RATE
import soundfile as sf
import uuid
import time
import tempfile
import os
import shutil
from utils import norm_text_for_split, blend_voice

def generate_align_video(align_words:list[dict], uid):
    with open('manim_template.py', 'r', encoding='utf-8') as f:
        template = f.read()
    template = template.replace('{align_words}', str(align_words))

    with open(f'outputs/{uid}_manim.py', 'w') as f:
        f.write(template)
    if os.system(f'manimgl outputs/{uid}_manim.py TextHighlightAnimation -w --file_name {uid}.mp4 --video_dir outputs/') != 0:
        return None
    if os.system(f'ffmpeg -i outputs/{uid}.mp4 -i outputs/{uid}.wav -c:v copy -c:a aac outputs/{uid}_audio.mp4 > /dev/null 2>&1') != 0:
        return None
    return f'outputs/{uid}_audio.mp4'
    

def generate_audio(voice1, voice2, blend, reference_id, text, speed, sample_rate, trim_silence, align, align_video):
    t1 = time.time()
    need_delete = False
    if not reference_id:
        reference_id = str(uuid.uuid4())
        blend_voice(reference_id, voice1, voice2, blend)
        need_delete = True
    try:
        audio, info = model.generate(reference_id, text, speed=speed, sample_rate=sample_rate, trim_silence=trim_silence, align=align)
    finally:
        if need_delete:
            os.remove(f'references/{reference_id}.pt')
    uid = str(uuid.uuid4())
    path = f"outputs/{uid}.wav"
    logs = info["logs"]
    
    sf.write(path, audio, info["sample_rate"])
    t2 = time.time()
    logs += f"Time taken: {t2 - t1} seconds\n"
    if align:
        align_output = info["word_timestamps"]
    else:
        align_output = []
    align_str = ''
    for align_item in align_output:
        align_str += f"{align_item['text']} {align_item['start']} {align_item['end']} {align_item['end'] - align_item['start']} {align_item['index']}\n"
    print(logs)
    if align_video:
        align_video_path = generate_align_video(align_output, uid)
    else:
        align_video_path = None
    return path, align_str, align_video_path, logs

# Initialize model globally
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = KokoroTTS(device)

def create_interface(server_name="0.0.0.0", server_port=7861):
    """Create and launch the Gradio interface."""
    
    # Get available voices
    voices = model.get_available_voices()
    if not voices:
        print("No voices found! Please check the voices directory.")
        return
        
    # Create interface
    with gr.Blocks(title="Kokoro TTS Generator") as interface:
        gr.Markdown("# Kokoro TTS Generator")
        
        with gr.Row():
            with gr.Column():
                voice1 = gr.Dropdown(
                    choices=voices,
                    value=voices[0] if voices else None,
                    label="Voice1"
                )
                voice2 = gr.Dropdown(
                    choices=voices,
                    value=voices[1] if voices else None,
                    label="Voice2"
                )
                blend = gr.Slider(
                    minimum=0,
                    maximum=1,
                    step=0.01,
                    value=0,
                    label="Blend"
                )
                reference_id = gr.Textbox(
                    lines=1,
                    placeholder="Enter reference id",
                    label="Reference ID",
                    value="1"
                )
                text = gr.Textbox(
                    lines=3,
                    placeholder="Enter text to convert to speech...",
                    label="Text",
                    value="Please meet me at 7:30 PM at 42nd Street and 5th Avenue in 2024 during COVID-19. I will be wearing a red shirt worth 1$ and a blue shirt worth 2 $. my email address is shi.fan@gmail.com"
                )
                speed = gr.Slider(
                    minimum=0.2,
                    maximum=5,
                    step=0.01,
                    value=1,
                    label="speed"
                )
                sample_rate = gr.Slider(
                    minimum=10000,
                    maximum=48000,
                    step=1000,
                    value=SAMPLE_RATE,
                    label="Sample Rate"
                )
                trim_silence = gr.Checkbox(
                    value=True,
                    label="Trim Silence"
                )
                align = gr.Checkbox(
                    value=False,
                    label="Align"
                )
                align_video = gr.Checkbox(
                    value=False,
                    label="Align Video"
                )
                generate = gr.Button("Generate Speech")
            
            with gr.Column():
                output = gr.Audio(label="Generated Audio")
                align_output = gr.Textbox(label="Align Output")
                align_video_output = gr.Video(label="Align Video")
                logs = gr.Textbox(label="Logs")
                
        generate.click(
            fn=generate_audio,
            inputs=[voice1, voice2, blend, reference_id, text, speed, sample_rate, trim_silence, align, align_video],
            outputs=[output, align_output, align_video_output, logs]
        )
    generate_audio(voices[0], voices[1], 1, '1', 'Please meet me at 7:30 PM at 42nd Street and 5th Avenue in 2024 during COVID-19. I will be wearing a red shirt worth 1$ and a blue shirt worth 2 $. my email address is shi.fan@gmail.com', 1, 24000, True, True, False)
    # Launch interface
    interface.launch(
        server_name=server_name,
        server_port=server_port,
        share=False
    )

if __name__ == "__main__":
    os.system("Xvfb :99 -screen 0 1920x1080x24 &>/dev/null &")
    create_interface()
