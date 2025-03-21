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

import os
from datetime import datetime
import shutil
#from pathlib import Path
import soundfile as sf
import torch
import numpy as np
from num2words import num2words
import time
import tempfile
import logging
from models import (
    list_available_voices, build_model,
    generate_speech, download_voice_files
)
from alignment import Alignment
from utils import align_words_to_raw_input, get_audio_duration, reverse_normalized_text, get_voice_path, split_sentences, norm_text_for_split, normalize_text

# Global configuration
CONFIG_FILE = "tts_config.json"  # Stores user preferences and paths
DEFAULT_OUTPUT_DIR = "outputs"    # Directory for generated audio files
SAMPLE_RATE = 24000  # Updated from 22050 to match new model


        

class KokoroTTS:
    def __init__(self, device: str):
        self.model = build_model(None, device)
        self.alignment = Alignment(device)
        self.device = device
        self.voices = list_available_voices()
        self.output_dir = "outputs"

    def get_available_voices(self):
        """Get list of available voice models."""
        try:
            # Initialize model to trigger voice downloads
            if self.model is None:
                logging.info("Initializing model and downloading voices...")
                self.model = build_model(None, self.device)
            
            voices = list_available_voices()
            if not voices:
                logging.info("No voices found after initialization. Attempting to download...")
                download_voice_files()  # Try downloading again
                voices = list_available_voices()
                
            logging.info(f"Available voices: {voices}")
            return voices
        except Exception as e:
            logging.info(f"Error getting voices: {e}")
            return []

    def generate_stream(self,voice, text, speed=1.0, sample_rate=SAMPLE_RATE, trim_silence=False, align=False):
        """Generate TTS audio with progress logging."""
        
        raw_input = text
        text = norm_text_for_split(text)
        logs = ""
        if 'TEST_ERROR_TRIGGER' == text:
            raise Exception("test error")
        # Create output directory
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        
        # Generate base filename from text
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"tts_{timestamp}"
        
        
        # Generate speech
        logging.info(f"Generating speech for: '{text}'")
        logging.info(f"Using voice: {voice}")
        align_p = 0
        temp_dir = tempfile.mkdtemp()
        try:
            
            speed1 = speed if speed >= 1 else 1
            speed2 = speed / speed1
            for i_text, text in enumerate(split_sentences(text)):
                t1 = time.time()
                logging.info(f'text {i_text}: {text}')
                text, projections = normalize_text(text)
                logging.info(f'normalized text {i_text}: {text}')
                generator = self.model(text, voice=get_voice_path(voice), speed=speed1, split_pattern=r'\n+')
                
                all_audio = []
                for gs, ps, audio in generator:
                    if audio is not None:
                        if isinstance(audio, np.ndarray):
                            audio = torch.from_numpy(audio).float()
                        all_audio.append(audio)
                        logging.debug(f"Generated segment: {gs}")
                        logging.debug(f"Phonemes: {ps}")
                        logs += f"Generated segment: {gs}\n"
                        logs += f"Phonemes: {ps}\n"
                
                if not all_audio:
                    raise Exception("No audio generated")
                
                # Combine audio segments and save
                final_audio = torch.cat(all_audio, dim=0).numpy()
                wav_path = os.path.join(temp_dir, f"{base_name}.{i_text}.wav")
                sf.write(wav_path, final_audio, sample_rate)
                if speed2 < 1:
                    logging.debug(f"use ffmpeg to slow down audio by {speed2}x")
                    logs += f"use ffmpeg to slow down audio by {speed2}x\n"
                    
                    cmd = f"ffmpeg -i {wav_path} -af \"atempo={speed2}\" {wav_path}.1.wav > {wav_path}.log 2>&1"
                    if os.system(cmd) != 0:
                        raise Exception("Failed to slow down audio")
                    #with open(wav_path + ".log", "r") as f:
                    #    logs += f.read() + "\n"
                    
                    wav_path = wav_path + ".1.wav"
                    
                
                if trim_silence:
                    logging.debug(f"trimming silence from audio")
                    logs += f"trimming silence from audio\n"
                    cmd = f'ffmpeg -i {wav_path} -af "silenceremove=start_periods=1:start_duration=0.1:start_silence=0.1:start_threshold=0.001,areverse,silenceremove=start_periods=1:start_duration=0.1:start_silence=0.1:start_threshold=0.001,areverse,aformat=sample_fmts=s32:channel_layouts=mono" {wav_path}.2.wav > {wav_path}.log 2>&1 '
                    
                    if os.system(cmd) != 0:
                        raise Exception("Failed to remove silence from audio")
                    #with open(wav_path + ".log", "r") as f:
                    #    logs += f.read() + "\n"
                    wav_path = wav_path + ".2.wav"
                if align:
                    try:
                        logging.debug(f"aligning audio")
                        logs += f"aligning audio\n"
                        word_timestamps = self.alignment.align(wav_path, text)
                        #logs += f"Word timestamps: {word_timestamps}\n"
                    except Exception as e:
                        logging.error(f"Error aligning audio: {e}")
                        logs += f"Error aligning audio: {e}\n"
                        import traceback
                        traceback.print_exc()
                        word_timestamps = None
                
                final_audio, sample_rate = sf.read(wav_path, dtype='int16')

                info = {
                    "sample_rate": sample_rate,
                    "dtype" : 'int16'
                }
                if align and word_timestamps:
                    for w in word_timestamps:
                        w.pop('score')
                    def create_new_words(old_part, new_words):
                        if not old_part:
                            return [{
                                'start' : -1,
                                'end' : -1,
                                'text' : new_word,
                            } for new_word in new_words]
                        
                        start = old_part[0]['start']
                        end = old_part[-1]['end']
                        duration = end - start
                        new_parts = [{
                            'start' : start + duration * i / len(new_words),
                            'end' : start + duration * (i + 1) / len(new_words),
                            'text' : new_word,
                        } for i, new_word in enumerate(new_words)]
                        return new_parts
                    word_timestamps = reverse_normalized_text(word_timestamps, projections, create_new_words)
                    word_timestamps, align_p = align_words_to_raw_input(raw_input, word_timestamps, align_p)
                    for i in range(1, len(word_timestamps)):
                        prev = word_timestamps[i-1]
                        cur = word_timestamps[i]
                        if cur['start'] == -1 and cur['end'] == -1:
                            cur['start'] = prev['end']
                            cur['end'] = prev['end']
                    info["word_timestamps"] = word_timestamps
                log = f"{i_text+1}{'st' if i_text == 0 else 'nd' if i_text == 1 else 'rd' if i_text == 2 else 'th'} piece Time taken: {time.time() - t1} seconds"
                logging.debug(log)
                logs += log + "\n"
                info['logs'] = logs
                yield final_audio, info
                
        finally:
            shutil.rmtree(temp_dir)
            
         


    def generate(self, voice, text, speed=1.0, sample_rate=SAMPLE_RATE, trim_silence=False, align=False):
        full_audio = []
        prev_duration = 0
        full_word_timestamps = []
        for audio, info in self.generate_stream(voice, text, speed=speed, sample_rate=sample_rate, trim_silence=trim_silence, align=align):
            full_audio.append(audio)
            word_timestamps = info.get("word_timestamps", None)
            if word_timestamps is not None:
                for word_timestamp in word_timestamps:
                    word_timestamp['start'] += prev_duration
                    word_timestamp['end'] += prev_duration
                    full_word_timestamps.append(word_timestamp)
                prev_duration += get_audio_duration(audio, sample_rate)
        full_audio = np.concatenate(full_audio) 
        info['word_timestamps'] = full_word_timestamps
        return full_audio, info

