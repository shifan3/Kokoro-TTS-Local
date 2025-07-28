set -e
NUM_WORKER=${NUM_WORKER:-1}
PWD=$(pwd)
docker kill kokoro-server || true
docker rm kokoro-server || true
docker run --rm -it -d --name kokoro-server --cap-add SYS_ADMIN --runtime nvidia --device /dev/fuse \
    --security-opt apparmor=unconfined -v $PWD:/root/kokoro -v /mnt/:/mnt/ -e LANG=C.UTF-8 -p 5006:13256 \
    kokoro:1.0.0 bash -c "cd /root/kokoro && NUM_WORKER=$NUM_WORKER bash do_start_server.sh && sleep infinity"