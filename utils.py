import re
from num2words import num2words
from typing import Callable
import numpy as np
import os
import torch



LHan = [[0x2E80, 0x2E99],    # Han # So  [26] CJK RADICAL REPEAT, CJK RADICAL RAP
        [0x2E9B, 0x2EF3],    # Han # So  [89] CJK RADICAL CHOKE, CJK RADICAL C-SIMPLIFIED TURTLE
        [0x2F00, 0x2FD5],    # Han # So [214] KANGXI RADICAL ONE, KANGXI RADICAL FLUTE
        0x3005,              # Han # Lm       IDEOGRAPHIC ITERATION MARK
        0x3007,              # Han # Nl       IDEOGRAPHIC NUMBER ZERO
        [0x3021, 0x3029],    # Han # Nl   [9] HANGZHOU NUMERAL ONE, HANGZHOU NUMERAL NINE
        [0x3038, 0x303A],    # Han # Nl   [3] HANGZHOU NUMERAL TEN, HANGZHOU NUMERAL THIRTY
        0x303B,              # Han # Lm       VERTICAL IDEOGRAPHIC ITERATION MARK
        [0x3400, 0x4DB5],    # Han # Lo [6582] CJK UNIFIED IDEOGRAPH-3400, CJK UNIFIED IDEOGRAPH-4DB5
        [0x4E00, 0x9FC3],    # Han # Lo [20932] CJK UNIFIED IDEOGRAPH-4E00, CJK UNIFIED IDEOGRAPH-9FC3
        [0xF900, 0xFA2D],    # Han # Lo [302] CJK COMPATIBILITY IDEOGRAPH-F900, CJK COMPATIBILITY IDEOGRAPH-FA2D
        [0xFA30, 0xFA6A],    # Han # Lo  [59] CJK COMPATIBILITY IDEOGRAPH-FA30, CJK COMPATIBILITY IDEOGRAPH-FA6A
        [0xFA70, 0xFAD9],    # Han # Lo [106] CJK COMPATIBILITY IDEOGRAPH-FA70, CJK COMPATIBILITY IDEOGRAPH-FAD9
        [0x20000, 0x2A6D6],  # Han # Lo [42711] CJK UNIFIED IDEOGRAPH-20000, CJK UNIFIED IDEOGRAPH-2A6D6
        [0x2F800, 0x2FA1D]]  # Han # Lo [542] CJK COMPATIBILITY IDEOGRAPH-2F800, CJK COMPATIBILITY IDEOGRAPH-2FA1D


def build_hanzi_re():
    L = []
    for i in LHan:
        if isinstance(i, list):
            f, t = i
            try: 
                f = chr(f)
                t = chr(t)
                L.append('%s-%s' % (f, t))
            except: 
                pass # A narrow python build, so can't use chars > 65535 without surrogate pairs!

        else:
            try:
                L.append(chr(i))
            except:
                pass

    RE = '[%s、]' % ''.join(L)
    return RE

hanzi_re = build_hanzi_re()

def get_voice_path(voice_name):
    fname1 = f"voices/{voice_name}.pt"
    fname2 = f"references/{voice_name}.pt"
    if os.path.exists(fname1):
        return fname1
    elif os.path.exists(fname2):
        return fname2
    else:
        raise ValueError(f"Voice {voice_name} not found")   


def blend_voice(
    reference_id: str,
    voice1: str,
    voice2: str,
    blend: float,
    
):
    os.makedirs('references', exist_ok=True)
    blend_path = os.path.join('references', f"{reference_id}.pt")
    voice1_model = torch.load(get_voice_path(voice1))
    voice2_model = torch.load(get_voice_path(voice2))
    voice_blended = (voice2_model * blend) + (voice1_model * (1 - blend))
    torch.save(voice_blended, blend_path)

def fraction_to_words(numerator, denominator):
    
    denominator = num2words(denominator, to="ordinal")
    if numerator > 1:
        denominator += "s" 
    numerator = num2words(numerator)
    return f"{numerator} {denominator}"

punkts = '.,!?;:"/'

def norm_text_for_split(text:str) -> str:
    replacements = {
        '。': '.',
        '，': ',',
        '！': '!',
        '？': '?',
        '；': ';',
        '：': ':',
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
    }
    for key, value in replacements.items():
        text = text.replace(key, value)

    
    text = re.sub(r'([a-zA-Z0-9_.]+)\@([a-zA-Z0-9_.]+)', lambda x : f"{x.group(1).replace('.', '[dot]')}@{x.group(2).replace('.', '[dot]')}", text)

    text = re.sub(rf'\s*([{punkts}])', r'\1 ', text)
    text = re.sub(r'[-]', ' - ', text)
    
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def normalize_text_one(words:list[str], pattern:str, replacement:Callable[[re.Match[str]], str], projections:list[tuple[int, list[str], int, list[str]]]) -> str:
    new_words = []
    matches:list[re.Match[str]] = []
    text = ' '.join(words)
    for match in re.finditer(pattern, text):
        if match.start() > 0 and text[match.start()-1] != ' ':
            continue
        if match.end() < len(text) and text[match.end()] not in punkts + ' ':
            continue
        matches.append(match)
    prev = 0
    for i, match in enumerate(matches):
        prev_text = text[prev:match.start()].strip()
        if prev_text:
            new_words += prev_text.split(' ')
        next_char = text[match.end()] if match.end() < len(text) else ''
        if next_char == ' ':
            next_char = ''
        replace_from = (match.group().strip() + next_char).strip()
        replace_to = (replacement(match) + next_char).strip()
        prev_old_text = text[:match.start()].strip()
        projections.append((replace_from.split(' '), len(new_words), replace_to.split(' ') if replace_to else []))
        new_words += replace_to.split(' ') if replace_to else []
        prev = match.end() + len(next_char)
    if prev < len(text):
        after = text[prev:].strip()
        if after:
            new_words += after.split(' ')
    return new_words, projections

def normalize_text(text:str) -> str:
    text = text.replace('[dot]', '.')
    projections = []
    words = text.split(' ')
    words, projections = normalize_text_one(words, r'([a-zA-Z0-9_.]+)\s*\@\s*([a-zA-Z0-9_.]+)', lambda x : f"{x.group(1).replace('.', ' dot ')} at {x.group(2).replace('.', ' dot ')}", projections)
    words, projections = normalize_text_one(words, r'1\s*\$', lambda x : r"one dollar", projections)
    words, projections = normalize_text_one(words, r'(\d+)\s*\$', lambda x : f"{num2words(int(x.group(1)))} dollars", projections)
    words, projections = normalize_text_one(words, r'\d\d\d\d', lambda x : f"{num2words(int(x.group(0)), to='year')}", projections)
    words, projections = normalize_text_one(words, r'\\frac{(\d+)}{(\d+)}', lambda x : fraction_to_words(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'`(\d+)s*/s*(\d+)`', lambda x : fraction_to_words(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'(\d+)/(\d+)', lambda x : fraction_to_words(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'(\d+)\s*:\s*(\d+)', lambda x : f"{num2words(int(x.group(1)))} {num2words(int(x.group(2)))}", projections)
    words, projections = normalize_text_one(words, r'(\d+)(nd|th|st)', lambda x : f"{num2words(int(x.group(1)), to='ordinal')}", projections)
    words, projections = normalize_text_one(words, r'(\d+)s', lambda x : num2words(int(x.group(1)))+'s', projections)
    words, projections = normalize_text_one(words, r'\d+', lambda x : num2words(int(x.group(0))), projections)
    words, projections = normalize_text_one(words, r'([^0-9 ]*)(\d+)([^0-9 ]*)', lambda x : f"{x.group(1)} {num2words(int(x.group(2)))} {x.group(3)}", projections)
    
    
    words, projections = normalize_text_one(words, r'([^ ]*)[^a-zA-Z\' "]+([^ ]*)', lambda x : re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z\' "]+', ' ', x.group(0))), projections)
    
    words, projections = normalize_text_one(words, r'[^a-zA-Z0-9 ,!.?\'; "]+', lambda x : '', projections)
    return ' '.join(words), projections


def reverse_normalized_text(words:list[dict], projections:list[tuple[list[str], int, list[str]]], create_new_words:Callable[[list[str], list[str]], list[str]]) -> str:
    for replaced, after_i, replace_to in reversed(projections):
        after_part = words[after_i:after_i+len(replace_to)]
        new_part = create_new_words(after_part, replaced)

        words = words[:after_i] + new_part + words[after_i + len(replace_to):]

    return words

def get_audio_duration(audio:np.ndarray, sample_rate:int) -> float:
    return audio.shape[0] / sample_rate



def split_sentences(text, max_words=20):
    text = text.strip()
    if len(text.split(' ')) <= max_words and text:
        yield text
        return
    matches = []
    for m in re.finditer(r'([.!?;]+)', text):
        matches.append((m.start(), m.end(), m.group()))
    if not matches or matches[-1][1] != len(text):
        matches.append((len(text), len(text), ''))
    
    prev = 0
    for start, end, delimiter in matches:
        text1 = text[prev:end].strip()
        ws1 = text1.split(' ') if text1 else []
        prev = end
        if text1 and len(ws1) <= max_words:
            yield text1
        else:
            matches1 = []
            for m in re.finditer(r'([,]+)', text1):
                matches1.append((m.start(), m.end(), m.group()))
            if not matches1 or matches1[-1][1] != len(text1):
                matches1.append((len(text1), len(text1), ''))
            prev1 = 0
            for start1, end1, delimiter1 in matches1:
                text2 = text1[prev1:end1].strip()
                prev1 = end1
                if text2:
                    yield text2


def align_words_to_raw_input(input_text:str, words:list[dict], p = 0) -> list[dict]:
    input_text = input_text.strip().lower()
    for word in words:
        w = re.sub(r'[^a-zA-Z0-9]+$', '', word['text']).lower()
        w = re.sub(r'^[^a-zA-Z0-9]+', '', word['text']).lower()
        #print('FIND', w, input_text[p:])
        p1 = input_text.find(w, p)
        if p1 == -1:
            word['index'] = None
        else:
            word['index'] = p1
        p = p1 + len(word['text'])
    return words, p

if __name__ == "__main__":

    s = 'Please 你好 meet me at 7:30 PM at 42nd Street and 5th Avenue in 2024s during COVID-19. I will be wearing a red shirt worth 1$ and a blue shirt worth 2 $, my email address is shi.fan@gmail.com'
    text = norm_text_for_split(s)
    print(text)
    text1s = []
    for text in split_sentences(text):
        text, projections = normalize_text(text)
        print(text)
        text1 = reverse_normalized_text(text.split(' '), projections, lambda old_part, new_words : new_words)
        text1 = ' '.join(text1)
        print(text1)
        text1s.append(text1)
    text1s = ' '.join(text1s)
    print(text1s)
    print(s)
    assert text1s.replace(' ', '') == s.replace(' ', '')
