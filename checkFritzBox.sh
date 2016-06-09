#!/usr/bin/env bash

TX_THRESH_BYTES=100000000
RX_THRESH_BYTES=100000000

ALERT_INTERVAL=3600

#export PATH="/home/richard/anaconda2/bin:$PATH"
export PATH=/home/richard/Apps/Anaconda/envs/fritzbox/bin:$PATH


source activate fritzbox
sleep 3

python fritz_monitor_internet_anon.py -s $TX_THRESH_BYTES -r $RX_THRESH_BYTES -t $ALERT_INTERVAL

source deactivate

