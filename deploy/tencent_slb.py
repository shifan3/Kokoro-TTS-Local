import time
from tencentcloud.clb.v20180317.clb_client import ClbClient
from tencentcloud.clb.v20180317.models import ModifyTargetWeightRequest, DescribeTaskStatusRequest
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from deploy.servers import SERVERS
import logging

import os
class TencentSlbClient:
    def __init__(self, access_key_id = None, access_key_secret = None):
        if access_key_id is None or access_key_secret is None:
            access_key_id, access_key_secret = os.environ['TENCENTCLOUD_SECRET_ID'], os.environ['TENCENTCLOUD_SECRET_KEY']

        cred = credential.Credential(
            access_key_id,
            access_key_secret)
        self.cred = cred
        httpProfile = HttpProfile()
        httpProfile.endpoint = "clb.tencentcloudapi.com"
        # 实例化一个client选项，可选的，没有特殊需求可以跳过
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        self.clientProfile = clientProfile
        # 实例化要请求产品的client对象,clientProfile是可选的
        self.clients_by_region = {}

    def get_client(self, region_id) -> ClbClient:
        if region_id not in self.clients_by_region:
            self.clients_by_region[region_id] = ClbClient(self.cred, region_id, self.clientProfile)
        return self.clients_by_region[region_id]

    def _set_weight(self, machine_info, weight) -> None:
        client = self.get_client(machine_info['region_id'])
        request = ModifyTargetWeightRequest()
        request.LoadBalancerId = machine_info['load_balancer_id']
        request.ListenerId = machine_info['listener_id']
        request.LocationId = machine_info['location_id']
        if not request.LoadBalancerId or not request.ListenerId or not request.LocationId:
            logging.warning(f"{machine_info['host']} has no slb info, skip")
            return
        request.Weight = weight
        request.Targets = [{"InstanceId": machine_info['server_id'], "Port": machine_info['port']}] 
        task = client.ModifyTargetWeight(request)
        ntry = 0
        request = DescribeTaskStatusRequest()
        request.TaskId = task.RequestId
        while ntry < 20:
            
            resp = client.DescribeTaskStatus(request)
            if resp.Status == 0:
                break
            elif resp.Status == 1:
                raise Exception(f"Task {task.RequestId} failed: {resp}")
            else:
                time.sleep(0.5)
                ntry += 1
        if ntry >= 20:
            raise Exception(f"Task {task.RequestId} failed: timeout")

    def set_weight(self, server_name, weight):
        self._set_weight(SERVERS[server_name], weight=weight)

    def online(self, server_name):
        self.set_weight(server_name, 100)
    
    def offline(self, server_name):
        self.set_weight(server_name, 0)
