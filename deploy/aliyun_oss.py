import os
import oss2
from tqdm import tqdm
import time
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider
from deploy import get_md5
import logging

class AliyunOss:
    def __init__(self, access_key, access_secret, bucket, external:bool):
        if 'OSS_ACCESS_KEY_ID' not in os.environ or 'OSS_ACCESS_KEY_SECRET' not in os.environ:
            os.environ['OSS_ACCESS_KEY_ID'] = access_key
            os.environ['OSS_ACCESS_KEY_SECRET'] = access_secret
            
        auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
        # 填写Bucket所在地域对应的Endpoint。以华东1（杭州）为例，Endpoint填写为https://oss-cn-hangzhou.aliyuncs.com。
        # yourBucketName填写存储空间名称。
        endpoint = 'https://oss-cn-hangzhou.aliyuncs.com' if external else 'oss-cn-hangzhou-internal.aliyuncs.com'
        self.bucket = oss2.Bucket(auth, endpoint, bucket)
        print(f'aliyun oss endpoint: {endpoint}')

    def get_object_content(self, oss_path):
        return self.bucket.get_object(oss_path).read()
            
    def download(self, oss_path, local_path, expect_md5 = None):
        succ = False
        retry = 1000
        part_size = 1024 * 1024 * 10
        pbar:tqdm = None
        while not succ and retry > 0:
            retry -= 1
            try:
                def progress_callback(bytes_consumed, total_bytes):
                    nonlocal pbar
                    unit = 1024 * 1024
                    bytes_consumed = bytes_consumed // unit
                    total_bytes = total_bytes // unit
                    if pbar is None:
                        pbar = tqdm(total = total_bytes, desc = local_path, unit = 'M',initial = bytes_consumed)
                    pbar.n = bytes_consumed
                    pbar.update(0)
                    
                oss2.resumable_download(self.bucket, 
                                        oss_path, 
                                        local_path,
                                        store=oss2.ResumableStore(root='./.cache'),
                                        multiget_threshold=part_size, 
                                        part_size=part_size, 
                                        progress_callback=progress_callback)
                if pbar is not None:
                    pbar.close()
                    pbar = None
                if expect_md5 is not None:
                    md5 = get_md5(local_path)
                    if md5 != expect_md5:
                        logging.warning(f'md5 mismatch, expect {expect_md5}, got {md5}')
                        os.remove(local_path)
                        continue
                succ = True
                print('downloaded', local_path, flush=True)
            except oss2.exceptions.RequestError as e:
                import traceback
                traceback.print_exc()
                print('retry!')
                time.sleep(2)
                continue
        return succ

    def object_exists(self, oss_path):
        return self.bucket.object_exists(oss_path)

    def put_object(self, oss_path, content):
        self.bucket.put_object(oss_path, content)


    def upload(self, fname, oss_path):
        part_size = 1024 * 1024 * 100
        succ = False
        retry = 1000
        pbar:tqdm = None
        while not succ and retry > 0:
            retry -= 1
            try:
                def progress_callback(bytes_consumed, total_bytes):
                    nonlocal pbar
                    unit = 1024 * 1024
                    bytes_consumed = bytes_consumed // unit
                    total_bytes = total_bytes // unit
                    if pbar is None:
                        pbar = tqdm(total = total_bytes, desc = fname, unit = 'M',initial = bytes_consumed)
                    pbar.n = bytes_consumed
                    pbar.update(0)
                #bucket.put_object_from_file(to_path, fname, progress_callback=progress_callback)
                oss2.resumable_upload(self.bucket, oss_path, fname, progress_callback=progress_callback,
                                        store=oss2.ResumableStore(root='/tmp'),
                                        multipart_threshold=part_size,
                                        part_size = part_size,
                                        num_threads=1)
                
                if pbar is not None:
                    pbar.close()
                    pbar = None
                succ = True
            except oss2.exceptions.RequestError as e:
                print('retry!')
                time.sleep(2)
                continue
        return succ