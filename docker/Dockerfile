FROM    torch-2.5.1-cp310

RUN     apt update
RUN     apt install -y git build-essential make g++ gcc wget libssl-dev ninja-build ffmpeg
RUN     wget https://github.com/Kitware/CMake/releases/download/v3.31.6/cmake-3.31.6.zip -O /root/cmake-3.31.6.zip
WORKDIR /root
RUN     unzip cmake-3.31.6.zip
WORKDIR /root/cmake-3.31.6
RUN     ./bootstrap
RUN     make -j16
RUN     make install
WORKDIR /root
RUN     git clone https://github.com/PierrunoYT/Kokoro-TTS-Local.git
WORKDIR /root/Kokoro-TTS-Local
RUN     python3.10 -m pip install -r requirements.txt
RUN     python3.10 -c "from models import build_model;build_model(None, 'cpu');"
RUN     python3.10 -c "from models import download_voice_files;download_voice_files()"
RUN     python3.10 -m pip install git+https://github.com/MahmoudAshraf97/ctc-forced-aligner.git
RUN     python3.10 -c "from ctc_forced_aligner import load_alignment_model;import torch;load_alignment_model('cpu', dtype=torch.float32)"
#install manimgl
RUN     apt install -y xvfb libcairo2-dev libsdl-pango-dev 
RUN     python3.10 -m pip install manimgl
ENV     DISPLAY=:99
RUN     python3.10 -m pip install gunicorn
WORKDIR /root/


