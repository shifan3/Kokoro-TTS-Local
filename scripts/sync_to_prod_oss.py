import os
from tqdm import tqdm
from optparse import OptionParser
import glob
import csv
import time
import hashlib
import re
import zipfile
import sys
sys.path.append(os.getcwd())
from deploy.aliyun_oss import AliyunOss
from deploy.tencent_oss import TencentOss

parser = OptionParser()
parser.add_option('', '--provider', dest = 'provider', type=str, default = 'tencent')
opts, args = parser.parse_args()

with open('configs/version.txt', 'r') as f:
    version = f.read().strip()

f_out = open('configs/file.list', 'w', encoding='utf-8')
writer = csv.writer(f_out)

if opts.provider == 'aliyun':
    oss = AliyunOss(os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'], os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'], bucket = 'danacommon', external = True)
elif opts.provider == 'tencent':
    oss = TencentOss(os.environ['TENCENTCLOUD_SECRET_ID'], os.environ['TENCENTCLOUD_SECRET_KEY'], bucket = 'engine-1328913057', region='ap-shanghai')
else:
    raise ValueError(f'unknown provider: {opts.provider}')

rows = []

ckpt = 'pretrained_local'
for fname in glob.glob(f'{ckpt}/**/*', recursive=True):
    if os.path.isdir(fname):
        continue
    
    rel_path = os.path.relpath(fname, ckpt)
    to_path = f'kokoro/{version}/pretrained_local/{rel_path}'
    rows.append([to_path, fname, fname, ''])
rows.append([f'kokoro/{version}/kokoro-v1_0.pth', 'kokoro-v1_0.pth', f'kokoro-v1_0.pth', ''])

rows.append([f'kokoro/{version}/data/tts_wav.zip', 'data/tts_wav.zip', f'data/tts_wav.zip', 'rm {}.tmp -rf && mv {} {}.tmp && unzip -o -q {}.tmp -d data/ && mv {}.tmp {}'])






image_file = f'/mnt/data5/docker/kokoro_{version}.image'
rows.append([f'kokoro/{version}/configs/images', image_file, f'configs/kokoro_{version}.image', ''])

for row in rows:
    writer.writerow([row[0], row[2], row[3]])
f_out.close()


for row in rows:
    assert len(row) == 4, row
    to_path, fname, remote_path, cmd = row
    md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        md5.update(f.read())
    md5 = md5.hexdigest()

    exist = oss.object_exists(to_path + '.hash')
    if exist:
        uploaded_md5 = oss.get_object_content(to_path + '.hash')
        if isinstance(uploaded_md5, bytes):
            uploaded_md5 = uploaded_md5.decode()
        if uploaded_md5 == md5:
            print(f'{fname} exists and md5 verified, skip')
            continue

    if not oss.upload(fname, to_path):
        raise Exception(f'failed to upload {fname}')
    oss.put_object(to_path + '.hash', md5)


        
print('done', flush=True)