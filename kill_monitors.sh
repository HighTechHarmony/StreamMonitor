#!/bin/sh

# This is a simple script to kill all instances of sjmstreammonitor-withprobe.py
# It is intended to be run manually from the command line as the need arises,
# Such as when the supervisor is not automatically managing the sjmstreammonitor-withprobe.py processes

# Kill all instances of sjmstreammonitor-withprobe.py
for pid in $(ps aux | grep '[s]jmstreammonitor-withprobe.py' | awk '{print $2}'); do
    echo "Killing sjmstreammonitor-withprobe.py with PID: $pid"
    kill -9 $pid
    sleep 1
    # Verify this process is dead
    if ps -p $pid > /dev/null
    then
        echo "sjmstreammonitor-withprobe.py with PID: $pid is still running.  Killing again..."
        kill -9 $pid
    fi
done
# kill -9 $(ps aux | grep '[s]jmstreammonitor-withprobe.py' | awk '{print $2}')

# sleep 5

# and ffmpeg
killall ffmpeg

