from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos.streambody import StreamBody
from qcloud_cos.cos_exception import CosClientError, CosServiceError
from deploy import get_md5
import os
from tqdm import tqdm
import time
from io import BytesIO
import logging

class TencentOss:
    def __init__(self, access_key, access_secret, bucket, region='ap-nanjing'):
        if 'COS_SECRET_ID' not in os.environ or 'COS_SECRET_KEY' not in os.environ:
            os.environ['COS_SECRET_ID'] = access_key
            os.environ['COS_SECRET_KEY'] = access_secret
        secret_id = os.environ['COS_SECRET_ID'] 
        secret_key = os.environ['COS_SECRET_KEY'] 
        token = None               # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
        scheme = 'https'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
        self.client = CosS3Client(config)
        self.bucket = bucket

    def get_object_to_fp(self, oss_path, fp):
        stream:StreamBody = self.client.get_object(Bucket=self.bucket, Key=oss_path)['Body']
        stream._read_len = 0
        auto_decompress = False
        while 1:
            chunk = stream.read(1024)
            if not chunk:
                break
            stream._read_len += len(chunk)
            fp.write(chunk)

        if not stream._use_chunked and not (
                stream._use_encoding and auto_decompress) and stream._read_len != stream._content_len:
            
            raise IOError("download failed with incomplete file")
        

    def get_object_content(self, oss_path):
        output = BytesIO()
        self.get_object_to_fp(oss_path, output)
        return output.getvalue()
    
            
    def download(self, oss_path, local_path, expect_md5 = None):

        succ = False
        retry = 1000
        pbar:tqdm = None
        while not succ and retry > 0:
            retry -= 1
            try:    
                #with open(local_path, 'wb') as f:
                #    self.get_object_to_fp(oss_path, f)
                #    print('downloaded', local_path, flush=True)
                #    succ = True
                #    break
                def download_percentage(bytes_consumed, total_bytes):
                    nonlocal pbar
                    unit = 1024 * 1024
                    bytes_consumed = bytes_consumed // unit
                    total_bytes = total_bytes // unit
                    if pbar is None:
                        pbar = tqdm(total = total_bytes, desc = local_path, unit = 'M',initial = bytes_consumed)
                    pbar.n = bytes_consumed
                    pbar.update(0)

                self.client.download_file(
                    Bucket=self.bucket,
                    Key=oss_path,
                    DestFilePath=local_path,
                    PartSize=10,
                    MAXThread=10,
                    EnableCRC=False,
                    progress_callback=download_percentage
                )
                if pbar is not None:
                    pbar.close()
                    pbar = None
                if expect_md5 is not None:
                    md5 = get_md5(local_path)
                    if md5 != expect_md5:
                        logging.warning(f'md5 mismatch, expect {expect_md5}, got {md5}')
                        os.remove(local_path)
                        continue
                print('downloaded', local_path, flush=True)
                succ = True
                break
            except CosClientError or CosServiceError as e:
                import traceback
                traceback.print_exc()
                print('retry!')
                time.sleep(2)
                continue
        return succ
    def object_exists(self, oss_path):
        return self.client.object_exists(Bucket=self.bucket, Key=oss_path)

    def put_object(self, oss_path, content):
        self.client.put_object(Bucket=self.bucket, Key=oss_path, Body=content)

    def upload(self, fname, oss_path):
        succ = False
        retry = 1000
        pbar:tqdm = None
        while not succ and retry > 0:
            retry -= 1
            try:    
                def upload_percentage(bytes_consumed, total_bytes):
                    nonlocal pbar
                    unit = 1024 * 1024
                    bytes_consumed = bytes_consumed // unit
                    total_bytes = total_bytes // unit
                    if pbar is None:
                        pbar = tqdm(total = total_bytes, desc = fname, unit = 'M',initial = bytes_consumed)
                    pbar.n = bytes_consumed
                    pbar.update(0)

                self.client.upload_file(
                    Bucket=self.bucket,
                    Key=oss_path,
                    LocalFilePath=fname,
                    PartSize=10,
                    MAXThread=5,
                    progress_callback=upload_percentage,
                    EnableMD5=True,
                )
                if pbar is not None:
                    pbar.close()
                    pbar = None
                succ = True
                break
            except CosClientError or CosServiceError as e:
                import traceback
                traceback.print_exc()
                print('retry!')
                time.sleep(2)
                continue
        return succ
