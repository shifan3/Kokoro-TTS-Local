import os

from optparse import OptionParser
import hashlib
import csv
import logging
import sys
import os
sys.path.append(os.getcwd())
from deploy.aliyun_oss import AliyunOss
from deploy.tencent_oss import TencentOss
from deploy import get_md5


def main():
    parser = OptionParser()
    parser.add_option('-v', '--version', dest = 'version', type=str, default = None)
    parser.add_option('', '--oss-access-key', dest = 'oss_access_key', type=str, default = None)
    parser.add_option('', '--oss-access-secret', dest = 'oss_access_secret', type=str, default = None)
    parser.add_option('', '--provider', dest = 'provider', type=str, default = 'tencent')
    opts, args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

    version = opts.version or open('configs/version.txt', 'r').read().strip()
    if opts.provider == 'aliyun':
        oss = AliyunOss(opts.oss_access_key or os.environ['ALIYUN_OSS_ACCESS_KEY'], opts.oss_access_secret or os.environ['ALIYUN_OSS_ACCESS_SECRET'], bucket = 'danacommon', external = False)
    elif opts.provider == 'aliyun-external':
        oss = AliyunOss(opts.oss_access_key or os.environ['ALIYUN_OSS_ACCESS_KEY'], opts.oss_access_secret or os.environ['ALIYUN_OSS_ACCESS_SECRET'], bucket = 'danacommon', external = True)
    elif opts.provider == 'tencent':
        oss = TencentOss(opts.oss_access_key or os.environ['TENCENTCLOUD_SECRET_ID'], opts.oss_access_secret or os.environ['TENCENTCLOUD_SECRET_KEY'], bucket = 'engine-1328913057', region='ap-shanghai')
    else:
        raise ValueError(f'unknown provider: {opts.provider}')
    

    f_in = open('configs/file.list', 'r', encoding='utf-8')
    reader = list(csv.reader(f_in))
    

    print('sync started', flush=True)
    try:
        for oss_path, local_path, cmd in reader:
                
            #local_path = local_path.replace(f'deploy-data/tiku1600w/{version}/', f'deploy-data/tiku1600w/current/')
            if os.path.dirname(local_path):
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
            #bucket.get_object_to_file(oss_path, local_path)
            uploaded_md5 = oss.get_object_content(oss_path + '.hash')
            if isinstance(uploaded_md5, bytes):
                uploaded_md5 = uploaded_md5.decode()
            if os.path.exists(local_path):
                md5 = get_md5(local_path)
                if md5 == uploaded_md5:
                    print('skip', local_path, flush=True)
                    continue
                else:
                    os.remove(local_path)
            
            
            if not oss.download(oss_path, local_path, uploaded_md5):
                raise Exception(f'failed to download {oss_path}')
            if cmd:
                cmd = cmd.replace('{}', local_path)
                print(f'running {cmd}', flush=True)
                os.system(cmd)
        
        print('all done', flush=True)
    except:
        print('sync failed', flush=True)
        raise

if __name__ == '__main__':
    main()