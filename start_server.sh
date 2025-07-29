set -e
NUM_WORKER=${NUM_WORKER:-4}
PWD=$(pwd)
VERSION=$(cat configs/version.txt)
GREEN='\033[1;32m'
GRAY='\033[0;37m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NOCOLOR='\033[0m'
docker kill kokoro-server || true
docker rm kokoro-server || true
docker run --rm -it -d --name kokoro-server --cap-add SYS_ADMIN --runtime nvidia --device /dev/fuse \
    --security-opt apparmor=unconfined -v $PWD:/root/kokoro -e LANG=C.UTF-8 -p 5006:5072 \
    kokoro:$VERSION bash -c "cd /root/kokoro && NUM_WORKER=$NUM_WORKER bash do_start_server.sh && sleep infinity"


echo -e "${GREEN}waiting server started...${NOCOLOR}"   
sleep 5
PREV_LINE=
SERVER_STARTED=0
for j in {1..2000}
do
    sleep 0.1
    if grep "Application startup complete" engine.log ; then
        echo -e "${GREEN}server started${NOCOLOR}"
        SERVER_STARTED=`python -c "print($SERVER_STARTED + 1)"`
        break
    else
        CURR_LINE=`cat engine.log | tail -n 1`
        if [ "$CURR_LINE" != "$PREV_LINE" ]; then
            echo -e "${GRAY}$CURR_LINE${NOCOLOR}"
            PREV_LINE=$CURR_LINE
        fi
    fi
done
if [ $SERVER_STARTED -eq $NUM_WORKER ]; then
    exit 0
fi
echo -e "${RED}server start failed${NOCOLOR}"

exit 1