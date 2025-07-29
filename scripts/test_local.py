import json
import sseclient

import base64
import urllib.parse
from threading import Thread
from queue import Queue
import time
import os

text = """Please meet me at 7:30 PM at 42nd Street and 5th Avenue in 2024 COVID-19."""

text_long = text + """I will be wearing a red shirt worth 1$ and a blue shirt worth 2 $. my email address is shi.fan@gmail.com."""
text_long += 'In early 2000s, Jia took his street smarts to Taiyuan, the provincial capital city, where he be-gan to do business in electronic devices under various companies, all which were named around "Xi Bei Er" or "Sinotel".'
text_long += "science, museum, bookstore, cinema, hospital, crossing, turn, left, straight, right, by, bus, plane, taxi, ship, subway, train, slow, down, stop, visit, film, trip, supermarket, word, evening, tonight, tomorrow, dictionary, comic, postcard."
text_long += "ask, sir, interesting, Italian, restaurant, pizza, street, get, GPS, , gave, feature, follow, far, tell, Mrs, early, helmet, must, wear, attention, traf- fic, Munich, Germany, Alaska, sled, fast, ferry, Papa Westray, Scot- land, lesson, space, travel, half, price, together, mooncake, poem, moon."
speed = 0.8 
align=1

#text = "The post has just arrived and in it a very nice surprise"
text = urllib.parse.quote(text_long)
url = 'http://localhost:13256/tts/generate'
headers = {'Accept': 'text/event-stream'}

#reference_id = "1"
#text  = 'TEST_ERROR_TRIGGER'
url = url + f"?text={text}&speed={speed}&align={align}"
#if reference_id:
#    url = url + f"&reference_id={reference_id}"

#response = with_requests(url, headers)
if os.name == 'nt':
    import pyaudio
    p = pyaudio.PyAudio()  
else:
    p = None



stream = None
queue = Queue()

def watch_queue():
    while True:
        segment = queue.get()
        if segment is None:
            print("stopping stream", time.time() - start_time)
            if stream:
                stream.stop_stream()
                stream.close()
            if p:
                p.terminate()
            return
        if p and stream:
            stream.write(segment)
    

thread = Thread(target=watch_queue)
thread.start()

start_time = time.time()
client = sseclient.SSEClient(url, headers=headers)
print("connection created", time.time() - start_time)
start_time = time.time()

try:
    print('start')
    buffer = b''
    for event in client:
        BRK = False
        for line in event.data.split('\n'):
            if not line:
                continue
            data = json.loads(line)
            if data['action'] == 'segment':
                print('segment', time.time() - start_time)
                #samplerate = data['samplerate']
                audio = base64.b64decode(data['audio'])
                word_timestamps = data.get('word_timestamps', None)
                if word_timestamps:
                    for word_timestamp in word_timestamps:
                        print(word_timestamp) #这个就是文本对齐
                buffer += audio
                if len(buffer) > 65535:
                    queue.put(buffer)
                    buffer = b''
                    print('push', time.time() - start_time)
            elif data['action'] == 'final':
                print('final', time.time() - start_time)
                if len(buffer) > 0:
                    queue.put(buffer)
                    buffer = b''
                    print('push', time.time() - start_time)
                queue.put(None)
                BRK = True
                break
            elif data['action'] == 'init':
                print('init', time.time() - start_time)
                channels = data['channels']
                samplerate = data['samplerate']
                if p:
                    if data['data_type'] == 'int16':
                        format = pyaudio.paInt16
                    elif data['data_type'] == 'int32':
                        format = pyaudio.paInt32
                    elif data['data_type'] == 'float32':
                        format = pyaudio.paFloat32
                    else:
                        raise Exception("Unknown data type")
                    
                    stream = p.open(format = format,  
                        channels = channels,  
                        rate = samplerate,  
                        frames_per_buffer = 4096,
                        output = True, start=True)  
            elif data['action'] == 'error':
                print("ERROR:" + data['error'])
                queue.put(None)
                BRK = True
                break
            else:
                print("UNKNOWN ACTION:" + data['action'])

        if BRK:
            break
except Exception as e:
    import traceback
    traceback.print_exc()
    queue.put(None)
    exit(1)
print("done")