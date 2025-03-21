import os


def post_fork(server, worker):
    os.environ['CUDA_VISIBLE_DEVICES'] = getattr(worker, "GPU_IND")
    
    
    server.log.info("Worker spawned (pid: %s) worker age %d,allocated cuda device %s",
                        worker.pid, worker.age, os.environ['CUDA_VISIBLE_DEVICES'])

def pre_fork(server, worker):
    devices = ["0"]
    if "CUDA_VISIBLE_DEVICES" in os.environ:
        devices = os.environ['CUDA_VISIBLE_DEVICES'].split(",")


    items = list(server.WORKERS.items()) # avoid crash 
    setattr(worker, "GPU_IND", devices[len(items) % len(devices)])



def pre_exec(server):
    server.log.info("Forked child, re-executing.")


def when_ready(server):
    server.log.info("Server is ready. Spawning workers")



