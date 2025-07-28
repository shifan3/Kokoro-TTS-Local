import hashlib
from .servers import SERVERS


import os
import logging


def set_weight(machine:str, weight:int):
    if machine not in SERVERS:
        raise Exception("unknown machine name")
    is_set = False
    provider = SERVERS[machine]['provider']
    if provider == 'aliyun' or provider == 'aliyun-external':
        from .aliyun_slb import AlibabaSlbClient
        client = AlibabaSlbClient(os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'], os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'])
        client.set_weight(machine, weight)
        is_set = True
    elif provider == 'tencent':
        from .tencent_slb import TencentSlbClient
        client = TencentSlbClient(os.environ['TENCENTCLOUD_SECRET_ID'], os.environ['TENCENTCLOUD_SECRET_KEY'])
        client.set_weight(machine, weight)
        is_set = True
    else:
        logging.warn(f"{machine}'s provider not support set weight, no change is done")
    if is_set:
        logging.warn(f"{machine}'s weight is set to {weight}")


def offline(machine:str):
    set_weight(machine, 0)

def online(machine:str):
    set_weight(machine, 100)

def wrap_bastion(cmd, bastion):
    if not bastion:
        return cmd
    head = cmd.split(' ')[0]
    if head == 'ssh':
        return f'stdbuf -oL ssh {bastion} "{cmd}"'
    elif head == 'rsync' :
        return f'stdbuf -oL rsync -e "ssh {bastion} ssh" {" ".join(cmd.split(" ")[1:])}'


def run_remote_command(host, remote_command):
    cmd = wrap_bastion(f'ssh {host["user"]}@{host["host"]} bash -c \'{remote_command}\'', host['bastion'])
    print(cmd)
    return os.system(cmd)

def get_md5(fname):
    md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        md5.update(f.read())
    return md5.hexdigest()
