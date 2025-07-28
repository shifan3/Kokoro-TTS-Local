
import os
import json
from alibabacloud_slb20140515.client import Client as Slb20140515Client
from alibabacloud_nlb20220430.client import Client as Nlb20220430Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_slb20140515 import models as slb_20140515_models
from alibabacloud_nlb20220430 import models as nlb_20220430_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from deploy.servers import SERVERS
import logging


class AlibabaSlbClient:
    def __init__(self, access_key_id = None, access_key_secret = None):
        if access_key_id is None or access_key_secret is None:
            access_key_id, access_key_secret = os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'], os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET']

        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/Slb
        config.endpoint = f'slb.aliyuncs.com'
        self.slb_client = Slb20140515Client(config)
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/Nlb
        config.endpoint = f'nlb.cn-hangzhou.aliyuncs.com'

        self.nlb_client = Nlb20220430Client(config)

    def _set_weight(self, machine_info, weight) -> None:
        
        region_id = machine_info['region_id']
        server_id = machine_info['server_id']
        load_balancer_id = machine_info.get('load_balancer_id', '')
        server_group_id = machine_info.get('server_group_id', '')

        if not load_balancer_id and server_group_id:
            servers_0 = nlb_20220430_models.UpdateServerGroupServersAttributeRequestServers(
                server_id=server_id,
                server_type='Ip',
                server_ip=server_id,
                port=machine_info['port'],
                weight=weight
            )
            print(server_id, machine_info['port'])
            update_server_group_servers_attribute_request = nlb_20220430_models.UpdateServerGroupServersAttributeRequest(
                region_id=machine_info['region_id'],
                server_group_id=server_group_id,
                servers=[
                    servers_0
                ]
            )
            runtime = util_models.RuntimeOptions()
            try:
                # 复制代码运行请自行打印 API 的返回值
                response = self.nlb_client.update_server_group_servers_attribute_with_options(update_server_group_servers_attribute_request, runtime)
                print(response)
            except Exception as error:
                # 此处仅做打印展示，请谨慎对待异常处理，在工程项目中切勿直接忽略异常。
                # 错误 message
                print(error.message)
                # 诊断地址
                print(error.data.get("Recommend"))
                UtilClient.assert_as_string(error.message)
                raise Exception("set weight failed")
        elif load_balancer_id and not server_group_id:
            if not server_id or not load_balancer_id or not region_id:
                logging.warning(f"{machine_info['host']} has no slb info, skip")
                return

            set_backend_servers_request = slb_20140515_models.SetBackendServersRequest(
                region_id=region_id,
                load_balancer_id=load_balancer_id,
                backend_servers=json.dumps([{"ServerId": server_id, "Weight": str(weight)}])
            )
            runtime = util_models.RuntimeOptions(read_timeout=100000, connect_timeout=10000)
            print(set_backend_servers_request)
            try:
                resp = self.slb_client.set_backend_servers_with_options(set_backend_servers_request, runtime)
            except Exception as error:
                # 错误 message
                print(error.message)
                # 诊断地址
                print(error.data.get("Recommend"))
                UtilClient.assert_as_string(error.message)
                raise
            result = [s for s in resp.to_map()['body']['BackendServers']['BackendServer'] if s['ServerId'] == server_id]
            if not result or result[0]['Weight'] != weight:
                raise Exception("set weight failed")
        else:
            raise Exception("bad config")
    
    def set_weight(self, server_name, weight):
        self._set_weight(SERVERS[server_name], weight=weight)

    def online(self, server_name):
        self.set_weight(server_name, 100)
    
    def offline(self, server_name):
        self.set_weight(server_name, 0)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-m', '--machine', dest = 'machine', type=str, default = None)
    parser.add_option('-w', '--weight', dest = 'weight', type=int, default = None)  
    opts, args = parser.parse_args()
    assert opts.weight is not None
    assert opts.machine
    client = AlibabaSlbClient(os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'], os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'])
    client.set_weight(opts.machine, opts.weight)
    print(f"{opts.machine}'s weight is set to {opts.weight}")