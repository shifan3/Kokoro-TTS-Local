import re
from num2words import num2words as _num2words
from typing import Callable
import numpy as np
import os
import torch
import logging
import csv

def setup_logging(level=logging.INFO):
    logging.getLogger().setLevel(level)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s;%(process)d;%(levelname)s;%(message)s", "%Y-%m-%d %H:%M:%S")
    ch.setFormatter(formatter)
    logging.getLogger().handlers = [ch]

with open('data/words.txt', 'r') as f:
    ALL_WORDS = set(w.strip() for w in f.readlines())



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


def num2words(x:str|float|int, to:str='cardinal') -> str:
    if isinstance(x, str):
        x = x.replace(' ', '')
        if '.' in x:
            x = float(x)
        else:
            x = int(x)
    return _num2words(x, to=to).replace(',', '')

def fraction_to_words(numerator, denominator):
    if denominator == 2:
        if numerator == 1:
            denominator = 'half'
        else:
            denominator = 'halves'
    else:
        denominator = num2words(denominator, to="ordinal")
        if numerator > 1:
            denominator += "s" 
    numerator = num2words(numerator)
    return f"{numerator} {denominator}"



punkts = '.,!?;:"'

norm_text_for_split_replacements = {
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

norm_text_for_split_replacements_rev = {v: k for k, v in norm_text_for_split_replacements.items()}


#注意，改了这个函数，要同步修改align_words_to_raw_input
def norm_text_for_split(text:str) -> str:
    lines = []
    for text in text.split('\n'):

        for key, value in norm_text_for_split_replacements.items():
            text = text.replace(key, value)

        for c in '=+-*/×÷':
            text = text.replace(c, f' {c} ')
        
        text = re.sub(r'([a-zA-Z0-9_.]+)\@([a-zA-Z0-9_.]+)', lambda x : f"{x.group(1).replace('.', '[dot]')}@{x.group(2).replace('.', '[dot]')}", text)
        text = re.sub(r'(\d)\.(\d)', r'\1[dot]\2', text)
        text = re.sub(rf'\s*([{punkts}])', r'\1 ', text)
        text = re.sub(r'[-]', ' - ', text)

        
        
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('<br>', '\n')
        #text = text.replace('[dot]', '.')
        lines.append(text.strip())
    return '\n'.join(lines).strip()

def normalize_text_one(words:list[str], pattern:str|Callable[[str], list[re.Match[str]]], replacement:Callable[[re.Match[str]], str], projections:list[tuple[int, list[str], int, list[str]]]) -> str:
    new_words = []
    matches:list[re.Match[str]] = []
    text = ' '.join(words)
    if isinstance(pattern, str):
        find_func = lambda text: list(re.finditer(pattern, text))
    else:
        find_func = pattern
    for match in find_func(text):
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

abbreviations = {}
with open('data/所有要支持的缩写.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i == 0:
            continue
        def re_key(c, cased, last:bool, first:bool):
            if c.isalpha():
                if cased == '0':
                    return f'[{c.lower()}{c.upper()}]'
                elif first and c.islower():
                    return f'[{c}{c.upper()}]'
                else:
                    return f'[{c}]'
            elif c == '.':
                return f'[.]' if last else f'[.]\s*'
            else:
                return f'[{c}]'
        short, long, cased, enable = row
        if enable == '0':
            continue
        abbreviations[''.join(re_key(c, cased, i == len(short) - 1, i == 0) for i, c in enumerate(short))] = long


def convert_date(year:int, month:int, day:int) -> str:
    if month > 12 and day <= 12:
        month, day = day, month
    year_s = num2words(year, to='year')
    if month <= 12 and month > 0:
        month_s = [
            'January',
            'February',
            'March',
            'April',
            'May',
            'June',
            'July',
            'August',
            'September',
            'October',
            'November',
            'December',
        ][month - 1]
    else:
        month_s = num2words(month, to='ordinal')
    day_s = num2words(day, to='ordinal')
    return f"{year_s} {month_s} the {day_s}"

def convert_power(base:float, power:float) -> str:
    base_s = num2words(base)
    if power == 2:
        return f"{base_s} squared"
    elif power == 3:
        return f"{base_s} cubed"
    else:
        return f"{base_s} to the power of {num2words(power)}"


def convert_time(hour:int, minute:int) -> str:
    if minute == 0:
        return f"{num2words(hour)} o clock"
    else:
        return f"{num2words(hour)} {num2words(minute)}"

def normalize_text(text:str) -> str:
    text = text.replace('[dot]', '.')
    projections = []
    words = text.split(' ')
    #regex_url = r'(?:https?://)?(?:[-\w.]|(?:%[\da-fA-F]{2}))*'
    words, projections = normalize_text_one(words, r'([a-zA-Z0-9_.]+)\s*\@\s*([a-zA-Z0-9_.]+)', lambda x : f"{x.group(1).replace('.', ' dot ')} at {x.group(2).replace('.', ' dot ')}", projections)
    words, projections = normalize_text_one(words, r'1\s*\$', lambda x : r"one dollar", projections)
    words, projections = normalize_text_one(words, r'(\d+\.?\d*)\s*\$', lambda x : f"{num2words(x.group(1))} dollars", projections)
    words, projections = normalize_text_one(words, r'\$\s*(\d+\.?\d*)', lambda x : f"{num2words(x.group(1))} dollars", projections)
    words, projections = normalize_text_one(words, r'(\d\d\d\d)\s*[\\/]\s*(\d\d?)\s*[\\/]\s*(\d\d?)', lambda x : convert_date(int(x.group(1)), int(x.group(2)), int(x.group(3))), projections)
    words, projections = normalize_text_one(words, r'(\d\d?)\s*[\\/]\s*(\d\d?)\s*[\\/]\s*(\d\d\d\d)', lambda x : convert_date(int(x.group(3)), int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'\d\d\d\d', lambda x : f"{num2words(int(x.group(0)), to='year')}", projections)
    words, projections = normalize_text_one(words, r'\\frac{(\d+)}{(\d+)}', lambda x : fraction_to_words(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'`(\d+)\s*/\s*(\d+)`', lambda x : fraction_to_words(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'(\d+)\s*/\s*(\d+)', lambda x : fraction_to_words(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'(\d+)\s*:\s*(\d+)', lambda x : convert_time(int(x.group(1)), int(x.group(2))), projections)
    words, projections = normalize_text_one(words, r'(\d+)(nd|th|st|rd)', lambda x : f"{num2words(int(x.group(1)), to='ordinal')}", projections)
    words, projections = normalize_text_one(words, r'\#\s*(\d+)', lambda x : f"number {num2words(int(x.group(1)))}", projections)
    words, projections = normalize_text_one(words, r'(\d+(\.\d+)?)\%', lambda x : f"{num2words(float(x.group(1)))} percent", projections)
    words, projections = normalize_text_one(words, r'(([+-]\s*)?\d+(\.\d+)?)\s*℃', lambda x : f"{num2words(x.group(1))} degree Celsius", projections)
    words, projections = normalize_text_one(words, r'(([+-]\s*)?\d+(\.\d+)?)\s*°C', lambda x : f"{num2words(x.group(1))} degree Celsius", projections)
    words, projections = normalize_text_one(words, r'(([+-]\s*)?\d+(\.\d+)?)\s*℉', lambda x : f"{num2words(x.group(1))} degree Fahrenheit", projections)
    words, projections = normalize_text_one(words, r'(([+-]\s*)?\d+(\.\d+)?)\s*°F', lambda x : f"{num2words(x.group(1))} degree Fahrenheit", projections)
    words, projections = normalize_text_one(words, r'(([+-]\s*)?\d+(\.\d+)?)°', lambda x : f"{num2words(float(x.group(1)))} degree", projections)
    words, projections = normalize_text_one(words, r'(\d+)s', lambda x : num2words(int(x.group(1)))+'s', projections)
    words, projections = normalize_text_one(words, r'\\sqrt\{([^}]*)\}', lambda x : f'the square root of {x.group(1)}', projections)
    words, projections = normalize_text_one(words, r'(\d+\.?\d*)\^(\d+\.?\d*)', lambda x : convert_power(float(x.group(1)), float(x.group(2))), projections)
    
    words, projections = normalize_text_one(words, r'<=', lambda x : 'less than or equal to', projections)
    words, projections = normalize_text_one(words, r'>=', lambda x : 'greater than or equal to', projections)
    words, projections = normalize_text_one(words, r'=', lambda x : 'equals', projections)
    words, projections = normalize_text_one(words, r'<', lambda x : 'less than', projections)
    words, projections = normalize_text_one(words, r'>', lambda x : 'greater than', projections)

    #words, projections = normalize_text_one(words, r'&', lambda x : 'and', projections)

    words, projections = normalize_text_one(words, r'([^ ]*)&([^ ]*)', lambda x : f'{x.group(1)} and {x.group(2)}', projections)
    
    words, projections = normalize_text_one(words, r'\+', lambda x : 'plus', projections)
    words, projections = normalize_text_one(words, r'(\d+(\.\d+)?)\s*\-\s*(\d+(\.\d+)?)', lambda x : f"{x.group(1)} minus {x.group(3)}", projections)
    words, projections = normalize_text_one(words, r'×', lambda x : 'times', projections)
    
    words, projections = normalize_text_one(words, r'\\times', lambda x : 'times', projections)
    words, projections = normalize_text_one(words, r'÷', lambda x : 'divided by', projections)
    words, projections = normalize_text_one(words, r'\\div', lambda x : 'divided by', projections)

    words, projections = normalize_text_one(words, r'([-]\s*)?\d+\.\d+', lambda x : num2words(x.group(0)), projections)
    words, projections = normalize_text_one(words, r'\-\s*(\d+)', lambda x : f'minus {num2words(int(x.group(1)))}', projections)
    words, projections = normalize_text_one(words, r'\d+', lambda x : num2words(int(x.group(0))), projections)


    words, projections = normalize_text_one(words, r'([^0-9 ]*)(\d+)([^0-9 ]*)', lambda x : f"{x.group(1)} {num2words(int(x.group(2)))} {x.group(3)}", projections)
    
    for k, v in abbreviations.items():
        words, projections = normalize_text_one(words, k, lambda x : v, projections)
    words, projections = normalize_text_one(words, r'([^ ]*)[^a-zA-Z\' "]+([^ ]*)', lambda x : re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z\',.!?:; "]+', ' ', x.group(0))), projections)
    
    words, projections = normalize_text_one(words, r'[^a-zA-Z0-9 ,!.?\'; "]+', lambda x : '', projections)

    
    
        

    ret =  ' '.join(words)
    def replace_cap_word(x:str):
        if x.lower() in ALL_WORDS and x != 'A':
            return x.lower()
        return x
    ret = re.sub(r'(\b)([A-Z_]+)(\b)', lambda x : x.group(1) + replace_cap_word(x.group(2)) + x.group(3), ret)

    
    
    return ret, projections


def reverse_normalized_text(words:list[dict], projections:list[tuple[list[str], int, list[str]]], create_new_words:Callable[[list[str], list[str]], list[str]]) -> str:
    for replaced, after_i, replace_to in reversed(projections):
        after_part = words[after_i:after_i+len(replace_to)]
        new_part = create_new_words(after_part, replaced)

        words = words[:after_i] + new_part + words[after_i + len(replace_to):]

    return words

def get_audio_duration(audio:np.ndarray, sample_rate:int) -> float:
    return audio.shape[0] / sample_rate


def split_sentences(text, predefined_words):
    for text1 in _split_sentences_1(text):
        texts = list(_split_sentences_2(text1))
        prev = 0
        for i in range(len(texts)):
            if not texts[i].rstrip(',').lower() in predefined_words:
                continue
            else:
                if prev < i:
                    yield ''.join(texts[prev:i])
                yield texts[i]
                prev = i + 1
        if prev < len(texts):
            yield ' '.join(texts[prev:])
            

def _split_sentences_1(text):
    text = re.sub(r'(\d)\.(\d)', r'\1[dot]\2', text)
    replaces = []
    def replace_abbreviations(k, before, after):
        replaces.append(k)
        return f'{before}_REPLACE_{len(replaces) - 1}_{after}'
    for i, (k, v) in enumerate(abbreviations.items()):
        text = re.sub(r'(\b|\s)' + k + r'(\b|\s)', lambda x : replace_abbreviations(x.group(0), x.group(1), x.group(2)), text)
    matches = []
    for m in re.finditer(r'([.!?;\n]+)', text):
        matches.append((m.start(), m.end(), m.group()))
    if not matches or matches[-1][1] != len(text):
        matches.append((len(text), len(text), ''))
    prev = 0
    for start, end, delimiter in matches:
        text1 = text[prev:end].strip()
        prev = end
        if text1:
            text1 = text1.replace('[dot]', '.')
            for i, k in enumerate(replaces):
                text1 = text1.replace(f'_REPLACE_{i}_', k.replace(' ', ''))
            yield text1
       
def _split_sentences_2(text):
    matches = []
    for m in re.finditer(r'([,]+)', text):
        matches.append((m.start(), m.end(), m.group()))
    if not matches or matches[-1][1] != len(text):
        matches.append((len(text), len(text), ''))
    prev = 0
    for start, end, delimiter in matches:
        text1 = text[prev:end].strip()
        prev = end
        if text1:
            yield text1

def split_sentences_old(text, max_words=20):
    text = text.strip()
    if len(text.split(' ')) <= max_words and text:
        yield text
        return
    matches = []
    for m in re.finditer(r'([.!?;\n]+)', text):
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
    for i_w, word in enumerate(words):
        w = re.sub(r'[^a-zA-Z0-9]+$', '', word['text']).lower()
        w = re.sub(r'^[^a-zA-Z0-9]+', '', word['text']).lower()
        w = w.replace(' ', '')
        

        pattern = ''
        for i in range(len(w)):
            c = w[i]
            if c in norm_text_for_split_replacements.keys():
                c1 = norm_text_for_split_replacements[c]
                c = f'[{c}{c1}]'
            elif c in norm_text_for_split_replacements_rev.keys():
                c1 = norm_text_for_split_replacements_rev[c]
                c = f'[{c}{c1}]'
            else:
                c = re.escape(c)
            pattern += c + r'\s*'
        #print('FIND', w, input_text[p:])
        p1 = re.search(pattern, input_text[p:])
        if p1 is None:
            word['index'] = 0 if i_w == 0 else words[i_w - 1]['index'] + len(words[i_w - 1]['text']) + 1
        else:
            word['index'] = p + p1.start()
            p = p + p1.end()
    return words, p

NORMALIZE_TESTCASES:list[tuple[str, list[str]]] = [
    
    ('Sth. is wrong', ['Something is wrong']),
    ('R&D', ['R and D']),
    ('R& D', ['R and D']),
    ('R & D', ['R and D']),
    ('R &D', ['R and D']),
    ('Can you give me sth.?', ['Can you give me something ?']),
    ('I need sth. to write with', ['I need something to write with']),
    ('Sb gave me sth, I really need it', ['Somebody gave me something, I really need it']),
    ('Sb. left their phone at home', ['Somebody left their phone at home']),
    ('Can sb. help me? I need help', ['Can somebody help me?', 'I need help']),
    ('Please tell sb to call me back', ['Please tell somebody to call me back']),
    ('The water freezes at 0°C', ['The water freezes at zero degree Celsius']),
    ('The temperature is -20.5°C', ['The temperature is minus twenty point five degree Celsius']),
    ('The discount is 20% off', ['The discount is twenty percent off']),
    ('The battery is at 80.5%', ['The battery is at eighty point five percent']),
    ('He is #1 tennis player in the world', ['He is number one tennis player in the world']),
    ('Please go to room #345', ['Please go to room number three hundred and forty five']),
    ('The meeting starts at 10:00 AM', ['The meeting starts at ten o clock am']),
    ('I wake up at 7:45 in the morning', ['I wake up at seven forty five in the morning']),
    ('She lives on the 1st floor', ['She lives on the first floor']),
    ('He lives on the 2nd floor', ['He lives on the second floor']),
    ('he finish 5th in the race', ['he finish fifth in the race']),
    ('this is my 3rd visit to London', ['this is my third visit to London']),
    ('3^4=81', ['three to the power of four equals eighty one']),
    ('2^2 is same as 2 times 2', ['two squared is same as two times two']),
    ('2^2=4', ['two squared equals four']),
    ('2.5^2=6.25', ['two point five squared equals six point two five']),
    ('6.25^0.5=2.5', ['six point two five to the power of zero point five equals two point five']),
    ('\\sqrt{6.25}=2.5', ['the square root of six point two five equals two point five']),
    ('Add `1/2` teaspoons of salt', ['Add one half teaspoons of salt']),
    ('the jar is `3/4` full', ['the jar is three fourths full']),
    ('She ate 3/4 of the pizza', ['She ate three fourths of the pizza']),
    ('the recipe calls for 1/3 cup of sugar', ['the recipe calls for one third cup of sugar']),
    ('1/2 of the cake is gone', ['One half of the cake is gone']),
    ('I have \\frac{1}{2} of the cake', ['I have one half of the cake']),
    ('\\frac{4}{3} \\times 3 = 4', ['four thirds times three equals four']),
    ('\\frac{4}{3}×3=4', ['four thirds times three equals four']),
    ('He was born in 1990', ['He was born in nineteen ninety']),
    ('He was born in 1990/03/04', ['He was born in nineteen ninety March the fourth']),
    ('He was born in 1990\\11\\24', ['He was born in nineteen ninety November the twenty fourth']),
    ('She earned $1600 last month', ['She earned one thousand six hundred dollars last month']),
    ('The price is 20$', ['The price is twenty dollars']),
    ('The price is $20.5', ['The price is twenty point five dollars']),
    ('please send an email to support@company.com', ['please send an email to support at company dot com']),
    ('you can reach me at john.doe@gmail.com', ['you can reach me at john dot doe at gmail dot com']),
    ('Contact us at info@website.org for more information', ['Contact us at info at website dot org for more information']),
    
]

def test_normalize_testcases():
    for s, expected in NORMALIZE_TESTCASES:
        text = norm_text_for_split(s)
        normalized_texts = []
        expected = list(map(lambda x: x.lower(), expected))
        text1s = []
        for text in split_sentences(text, {}):
            text, projections = normalize_text(text)
            normalized_texts.append(text.lower())
            text1 = reverse_normalized_text(text.split(' '), projections, lambda old_part, new_words : new_words)
            text1 = ' '.join(text1)
            text1s.append(text1)
        text1s = ' '.join(text1s)
        assert normalized_texts == expected, f'{normalized_texts} != {expected}'
        assert text1s.replace(' ', '').lower() == s.replace(' ', '').lower(), f'{text1s} != {s}'


ALIGN_TESTCASES:list[tuple[str, list[str]]] = [
    ("a@b.c", [{"text": "a@b.c", "index": 0}], [{'text': 'a@b.c', 'index': 0}]),
    ("align \"", [{"text": "align\"", "index": 0}], [{'text': 'align\"', 'index': 0}]),
    ("align？", [{"text": "align?", "index": 0}], [{'text': 'align?', 'index': 0}]),
]

def test_align_testcases():
    for s, words, expected in ALIGN_TESTCASES:
        aligned, _ = align_words_to_raw_input(s, words)
        assert aligned == expected, f'{aligned} != {expected}'


if __name__ == "__main__":
    test_align_testcases()
    test_normalize_testcases()
    