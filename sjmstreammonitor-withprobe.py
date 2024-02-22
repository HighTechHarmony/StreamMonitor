#!/usr/bin/python
'''
streammonitor.py
This is a python script agent that monitors a single audio or video stream for black, freeze, and silence conditions.
If a problem is detected, it will send a notification 

Author:  Scott McGrath (scott@smcgrath.com)

'''

import sys
import os
import subprocess
from subprocess import PIPE, Popen, call
# from threading  import Thread
import threading
import time
import base64
import logging
import re
import argparse
from datetime import datetime
from PIL import Image
import io

from pymongo import MongoClient
import pymongo
from config import MONGO_CONNECTION_STRING, OPERATING_DIRECTORY, MONGO_DATABASE_NAME, ALERTS_DISABLED, STREAMDOWN_ALERTS_DISABLED

PROGRAM_VERSION = "1.0.3"

# Apprise is a notification framework that supports, among many other things, Pushover 
import apprise

# Import Queue in way that works for both versions of Python (2.x and 3.x)
# Note this is probably not necessary as we no longer support Python 2.x, but I'm chicken to remove it.
try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x


print ("Starting up")


# Get the database name from the config file
database_name = str(MONGO_DATABASE_NAME)
# Remove quotes
database_name = database_name.replace('"', '')

# Get the base directory from the config file
base_dir = str(OPERATING_DIRECTORY)
#remove quotes
base_dir = base_dir.replace('"', '')

# Set and configure hard-coded stuff through various globals
global_configs_collection_name = "global_configs"
stream_configs_collection_name = "stream_configs"
stream_alerts_collection_name = "stream_alerts"
stream_images_collection_name = "stream_images"
report_collection_name = "stream_reports"
alert_collection_name = "stream_alerts"
users_collection_name = "users"
log_dir = base_dir + "/public_html/logs"



# Set up the command line and arguments, we use parser

parser = argparse.ArgumentParser(description='Monitor a video stream, send alerts when black/freeze/silent/dropped.')

parser.add_argument('--pushover',
    metavar = 'pushover',
    type = str,
    action = "append",
    help = 'user_key')

parser.add_argument('--audio_only',    
    action = 'store_true')    

parser.add_argument('--black_threshold',
    metavar = 'black_threshold',
    type=str,
    default="32",
    help='Black frame threshold')
parser.add_argument('--black_duration',
    metavar = 'black_duration',
    type=str,
    default="30",
    help='Black frame acceptable duration in seconds')

parser.add_argument('--freeze_threshold',
    metavar = 'freeze_threshold',
    type=str,
    default="-50",
    help='Freeze frame noise threshold')
parser.add_argument('--freeze_duration',
    metavar = 'freeze_duration',
    type=str,
    default="0",
    help='Freeze frame acceptable duration in seconds')

parser.add_argument('--silence_threshold',
    metavar = 'silence_threshold',
    type=str,
    default="-45",
    help='Silence threshold')
parser.add_argument('--silence_duration',
    metavar = 'silence_duration',
    type=str,
    default="60",
    help='Silence acceptable duration in seconds')

parser.add_argument('--stream_uri',
    metavar = 'stream_uri',
    type=str,
    help='Stream URI (ex: https://streamurl')
parser.add_argument('--stream_desc',
    metavar = 'stream_desc',
    type=str,
    help='Stream Description (ex: "KTV Stream #1"')

parser.add_argument('--frame_grab_interval',
    metavar = 'frame_grab_interval',
    type=str,
    default="60",
    help='Frame grab thumbnail update interval in seconds')

parser.add_argument('--version',    
    action = 'version',
    version='%(prog)s v'+PROGRAM_VERSION,
    help='Display version info')

# Allows unknown arguments:
args, unknown = parser.parse_known_args()


###################################################################
# Still more hard-coded configuration values
    # But most of these are defaults of "last resort".  
    # Command line arguments will override some of these.
 
# Wait this long before restarting the monitor after an error
SLEEP_TIME = 10

# Ignore startup errors for this long when starting the monitor
RAMPUP_TIME = 10

# Set this to 1 to make freeze detections send alerts even when there is blackframe. Usually you wouldn't do want this.
FREEZE_PRIORITY = 0

# Suppress logging of each blackframe detected 
# Warning, enabling suppression prevents the stream dropped indication from working 
# because ffmpeg doesn't emit ongoing frame numbers to STDOUT
SUPPRESS_BLACKFRAME_LOGGING = 0
# Suppress most of the stuff from ffmpeg from going to the log
SUPPRESS_FFMPEG_LOGGING = 1

# blackframe threshold, typically around 32
BLACKFRAME_THRESHOLD = 32
# Number of blackframes allowed before we start watching
BLACKFRAMES_ALLOWED = 200
# Amount of time after blackframes started being detected before we alert
BLACKFRAME_SECONDS_ALLOWED = 5
# Amount of time to wait before we think blackframes are over
BLACKFRAME_RESET_TIME = 5

# Noise threshold for freeze frame, typically around -50, higher num more likely to be considered freeze
FREEZE_NOISE_THRESHOLD = "-50"
# Amount of time after freeze started being detected before we alert
# If this is 0, freeze frame will not generate an alert.
FREEZETIME_SECONDS_ALLOWED = "5"

SILENCE_THRESHOLD = "-45"
SILENCE_DURATION = "5"

FRAME_GRAB_INTERVAL = "60"

# PROBE_TIME = 10
# PROBE_TIMEOUT = 10

# Send an alert if we don't get a new frame in this amount of time
STALE_FRAME_TIMEOUT = 10

# Time to wait between upness checks.  This is not yet a command line option.
CHECK_UPNESS_TIME = 3600

# Send alerts when an issue is resolved
SEND_RESTORED_ALERTS = 1

# List of streams to check
#stream = 'udp://localhost:9999'
#stream_desc = 'Test Stream'

# Check if we are on a posix system. This info is necessary later when we are launching threads
ON_POSIX = 'posix' in sys.builtin_module_names

#############################################
# Initialize a bunch of globals
#############################################
program_start_time = time.time()
last_framegrab_time = 0
blackframe_timer_running = 0
blackframe_last_seen_time = 0
blackframe_timer = float(0)
freeze_frame_in_progress = 0
audio_silent_in_progress = 0
last_probe_time = 0
probe_running = 0
stream_status = 1
last_frame = 0
watching_stale_frames = 0
stale_frame_start_time = 0
stale_frames_in_progress = 0


# Get ready to bring the logger online
# Since logging depends on the stream description, we will start with that
if args.stream_desc:
    print("Stream description: "+ args.stream_desc)
    stream_desc=args.stream_desc
else:
    print("FATAL: Stream Description is required. Monitor thread exiting.")
    sys.exit()

# Ensure the log file exists because apparently logger can't handle that
filename_temp=str(log_dir + "/"+args.stream_desc+".log")
print ("Opening log file: " + filename_temp + "\n")
if not os.path.isfile(filename_temp):
    # Create an empty file
    with open(filename_temp, 'w') as f:
        pass

# set up logging to file    
logging.basicConfig(
    #  filename=log_dir + "/"+args.stream_desc+".log",
    filename=filename_temp,
     level=logging.DEBUG, 
     #format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
     filemode='w',
     format='%(asctime)s %(message)s',
     datefmt='%H:%M:%S'
 )

# set up logging to console
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
# set a format which is simple for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)
logger = logging.getLogger(__name__)

# Create a new Apprise instance for notifications
apobj = apprise.Apprise()

# Override defaults with anything we get from command line
if args.pushover:    
    for x in args.pushover:
        logging.info("Adding CL pushover info: " + x)
        apobj.add('pover://' + x)
else:
    logging.info("WARNING: No Pushover key, will run without delivering alerts")


#################################################
# Go through all the arguments we have been given and log the requested settings
#################################################
    
# If we are monitoring an audio stream, make a note so we don't do blackframe or freeze detection
if args.audio_only:
    logging.info("Stream is audio_only=" + str(args.audio_only))
    AUDIO_ONLY=1
    FRAME_GRAB_INTERVAL = 3600

else:
    AUDIO_ONLY=0

    if int(args.frame_grab_interval) > 0:
        logging.info("Using frame grab interval " + args.frame_grab_interval)
        FRAME_GRAB_INTERVAL = args.frame_grab_interval

    if args.black_threshold:
        logging.info("Using black threshold " + args.black_threshold)
        BLACKFRAME_THRESHOLD=args.black_threshold

    if args.black_duration:
        logging.info("Using black duration " + args.black_duration)
        BLACKFRAME_SECONDS_ALLOWED = args.black_duration

    if args.freeze_threshold:
        logging.info("Using freeze threshold " + args.freeze_threshold)
        FREEZE_NOISE_THRESHOLD=args.freeze_threshold

    if args.freeze_duration:
        logging.info("Using freeze duration " + args.freeze_duration)
        FREEZETIME_SECONDS_ALLOWED = args.freeze_duration

if args.silence_threshold:
    logging.info("Using silence threshold " + args.silence_threshold)
    SILENCE_THRESHOLD=args.silence_threshold

if args.silence_duration:
    logging.info("Using silence duration " + args.silence_duration)    
    SILENCE_DURATION = args.silence_duration

if args.stream_uri:
    logging.info("Using stream uri " + args.stream_uri)
    stream = args.stream_uri
else:
    logging.error("FATAL: Stream URI is required. Monitor thread exiting.")
    sys.exit()


# Define the FFMPEG stream monitor command
FFMPEG = "/usr/bin/ffmpeg"





# Define the FFMPEG_ARGS which will hold all of the arguments necessary to support the requested monitoring features
FFMPEG_ARGS = ""

if AUDIO_ONLY != 1:
    # This section deals with adding Freezeframe and blackframe detection for video (aka non-audio_only)
    # logging.info("Adding blackdetect and freezedetect to FFMPEG_ARGS")
    # The below line may not be necessary but makes the logs much more noisy. With some experimentation, it may be possible to remove it.
    # But I can't remember if there is a message we need that only appears with it on.
    FFMPEG_ARGS = " -loglevel repeat+level+debug"  

    # Add video filter argument
    FFMPEG_ARGS = FFMPEG_ARGS + " -vf "

    # Add blackdetect video filter
    FFMPEG_ARGS = FFMPEG_ARGS + "blackdetect=d=0:pix_th=0.10,blackframe=amount=98:threshold="+str(BLACKFRAME_THRESHOLD)

    # Add freezedetect video filter
    if int(FREEZETIME_SECONDS_ALLOWED) > 0:
        logging.info("Freezeframe alerting enabled")
        FFMPEG_ARGS = FFMPEG_ARGS +",freezedetect=noise="+str(FREEZE_NOISE_THRESHOLD)+"dB:duration=" + str(FREEZETIME_SECONDS_ALLOWED)
    else:
        logging.info("Freezeframe alerting disabled (duration was 0)")

# Add audio silence monitoring (for both video and audio)
FFMPEG_ARGS = FFMPEG_ARGS + " -af silencedetect=noise="+str(SILENCE_THRESHOLD)+"dB:d="+str(SILENCE_DURATION)

# Add max muxing queue size, output receive to null, and output messages to stdout
FFMPEG_ARGS = FFMPEG_ARGS + "  -max_muxing_queue_size 9999 -f null -"

#FFMPEG_ARGS = " -af silencedetect=noise="+str(SILENCE_THRESHOLD)+"dB:d="+str(SILENCE_DURATION)+"  -max_muxing_queue_size 9999 -f null -"


def main():
    
    global alerts_disabled
    global alerts_hard_disabled
    global streamdown_alerts_hard_disabled
    global stream_down_in_progress
    
    alerts_hard_disabled = ALERTS_DISABLED
    streamdown_alerts_hard_disabled = STREAMDOWN_ALERTS_DISABLED
    alerts_disabled = alerts_hard_disabled
    stream_down_in_progress = 0

    if (ALERTS_DISABLED == 1):
        logging.info ("Alerts are hard-disabled by configuration.")
        alerts_hard_disabled = 1
        alerts_disabled = 1
    else:
        alerts_disabled=0
        alerts_hard_disabled=0


    # Okay, time for action - we launch the stream monitor via the analyze function

    if not analyze (stream):
        logging.info("Stream analyzer could not launch for " + stream + ". sending alert")
        if not stream_down_in_progress:
            stream_down_in_progress = 1
            if streamdown_alerts_hard_disabled:
                logging.info("Skipping alert, stream down alerts are hard-disabled by configuration.")
            else:
                send_message("Stream failure for: " + args.stream_uri)        

    # If we get here, it's probably because the stream died, or something went wrong (hopefully temporary)
            # This will sleep for the prescribed time and then the process will die
            # at that point, the supervisor will notice and restart us as a new process.
    logging.info("Waiting for " + str(CHECK_UPNESS_TIME) + " seconds")
    time.sleep (CHECK_UPNESS_TIME)






################################################################################
# Functions
################################################################################


# This function deals with connecting to the Mongo database.
# It returns the handle to the connected database if it is available
# It exits the program if the database is not available (as we couldn't do anything without it)
def get_database():
    from pymongo import MongoClient
    import pymongo

    print ("get_database()\n")
    
    # Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure

    client = MongoClient(str(MONGO_CONNECTION_STRING))
    try:
        # The ping command is cheap and does not require auth.
        client.admin.command('ping')
    except ConnectionFailure:
        print("MongoDB Server not available. Exiting")
        exit()

    print ("MongoDB Server available\n")

    # Print all the databases found    
    # for db in client.list_databases():
    #     print(db)

    # Return the database handle
    return client[database_name]


# This function takes output of the ffmpeg process, assembles it, and puts it into the specified queue
def process_line(std, q):    
    partialLine = ""
    tmpLines=[]
    end_of_message = False
    while (True):
        data = std.read(10)
        
        #print repr(data)
        
        #break when there is no more data
        if len(data) == 0:
            end_of_message = True

        # data needs to be added to previous line
        # if ((not "\n" in str(data)) and (not end_of_message)):   
        if (data.find(b'\n') == -1) and (not end_of_message):         
            # partialLine += data
            partialLine = ''.join(chr(byte) for byte in data)
        #lines are terminated in this string
        else:
            tmpLines = []

            #split by \n
            split = str(data).split("\n")

            #add the rest of partial line to first item of array
            if partialLine != "":
                split[0] = partialLine + split[0]
                partialLine = ""

            #add every item apart from last to tmpLines array
            if len(split) > 1:
                for i in range(len(split)-1):
                    tmpLines.append(split[i])

            #last item is '' if data string ends in \r
            #last line is partial, save for temporary storage
            if split[-1] != "":
                partialLine = split[-1]
            #last line is terminated
            else:
                tmpLines.append(split[-1])
            
            #print split[0]
            q.put(split[0])
            if (end_of_message):
                #print partialLine
                break

# Simple function that receives output from a process, calls the function to process it
# and puts it into a queue
def enqueue_output(stdout, queue):
    #for line in iter(stdout.readline, b''):
    #    queue.put(line)
    process_line(stdout, queue)  
    stdout.close()

# This function runs FFMPEG command line and starts a thread to enqueue the output for analysis
def run(q, ffcmd, thread_name):
    logging.info("Running " + ffcmd)
    p = Popen(ffcmd,shell=True, stderr=PIPE, stdin=PIPE, bufsize=1, close_fds=ON_POSIX)
    #q = Queue()
    #t = Thread(target=enqueue_output, args=(p.stdout, q))
    #t.daemon = True # thread dies with the program
    #t.start()
    t = Thread(target=enqueue_output, name=thread_name, args=(p.stderr, q))
    t.daemon = True
    t.start()
    return p


# Updates the thumbnail image data and writes it to the stream_images database (for the preview)
# Should be run every minute or so.
# Note, if something goes wrong and the stream framegrab fails, the program exits (assumption is that the stream is down)
def update_frame_grab():

    dbname = get_database()
    stream_images_collection = dbname[stream_images_collection_name]

    # If this is an audio stream, we will use a static image of an audio icon
    if (AUDIO_ONLY == 1):

        logging.info("Writing audio icon as stream image: ")
        im = Image.open("audio_icon.jpg")
    
    # Otherwise, we start a special instance of ffmpeg to grab a frame from the stream and write it as a temp jpg file
    else: 
        ffcmd_grab = "ffmpeg -ss 2 -i "+ stream +" -frames:v 1 -y -f image2 -t 5 \""+ stream_desc + ".jpg\""

        logging.info("Running framegrab: " + ffcmd_grab)

        # Run the process and determine if there was a problem
        ffmpeg_result = subprocess.call(ffcmd_grab, shell=True)

        if (ffmpeg_result != 0):
            logging.error("Framegrab failed with result " + str(ffmpeg_result))
            logging.error("ffmpeg command failed.  Please check that ffmpeg is installed and in the path.")
            exit()

        
        # p = Popen(ffcmd_grab,shell=True, stderr=PIPE, stdin=PIPE, bufsize=1, close_fds=ON_POSIX)
        im = Image.open(stream_desc+".jpg")        
    

    # Now we read in the file, convert it to base64, and write it to the database
    image_bytes = io.BytesIO()
    im.save(image_bytes, format='JPEG')   
    
    dateTimeObj = datetime.now()
    mytime = dateTimeObj.now().strftime("%Y-%m-%d %H:%M:%S")

    logging.info("Updating frame grab in database")

    mydict = {'timestamp': mytime, 'stream': stream_desc, 'data': base64.b64encode(image_bytes.getvalue())}
    # convert2unicode(mydict)

    image_id = stream_images_collection.update_one(
        {'stream': stream_desc}, 
        {'$set': mydict},
        upsert=True
    )

    return    



# Returns base64 encoded image data of the latest thumbnail without writing it to the database
# Can be used to write an image to the stream_alerts collection in the database for logging/review purposes
def return_frame_grab():

    # ffcmd_grab = "ffmpeg -ss 2 -i "+ stream +" -frames:v 1 -y -f image2 -t 5 \""+ stream_desc + ".jpg\""

    # logging.info("Running framegrab: " + ffcmd_grab)
    # subprocess.call(ffcmd_grab, shell=True)

    if (AUDIO_ONLY == 1):
        logging.info("Monitoring an audio stream ")
        im = Image.open("audio_icon.jpg")
    
    else: 
        im = Image.open(stream_desc+".jpg")

    image_bytes = io.BytesIO()
    im.save(image_bytes, format='JPEG')

    # image = {
    #     'data': image_bytes.getvalue()
    # }

    dateTimeObj = datetime.now()
    mytime = dateTimeObj.now().strftime("%Y-%m-%d %H:%M:%S")

    return base64.b64encode(image_bytes.getvalue())
    


#####################################################################################
# The big function that does the analysis of ffmpeg output (should probably be broken down a little)
# This function runs FFMPEG continuously monitor the stream and monitor the output
####################################################################################
def analyze(stream):
    global blackframe_timer_running
    global blackframe_last_seen_time
    global blackframe_timer
    global program_start_time
    global freeze_frame_in_progress
    global audio_silent_in_progress
    global last_probe_time
    global probe_running
    global last_frame
    global watching_stale_frames
    global stale_frames_in_progress
    global stale_frame_start_time
    global stream_down_in_progress
    global last_framegrab_time
    global FRAME_GRAB_INTERVAL

    global FREEZETIME_SECONDS_ALLOWED    
    global SILENCE_DURATION

    blackframe_alerted_latch = 0

    analyzeq = Queue()
    probeq = Queue()

    logging.info("Analyzing " + stream)    
    
    # analyzeproc = run(analyzeq, FFMPEG + " -i " + stream + " " + FFMPEG_ARGS, "analyzethread")
    ffmpeg_command = FFMPEG + " -report" + " -i " + stream + " " + FFMPEG_ARGS

    # Remove quotes from ffmpeg command
    # ffmpeg_command = ffmpeg_command.replace('"', '')
    logging.info("Running ffmpeg command: " + str(ffmpeg_command))
    # Convert the command to an array of strings
    ffmpeg_command = ffmpeg_command.split()
    logging.info("ffmpeg command after split(): " + str(ffmpeg_command))

    analyzeproc = launch_process_to_q(ffmpeg_command, analyzeq)
    logging.info("Launched analyze process with pid " + str(analyzeproc.pid))

    # Read from the queue until the queue is empty and process has exited
    start_time=time.time()
    last_probe_time = time.time() + RAMPUP_TIME

    # This loop continues as long as the ffmpeg process is running as expected
    while (True):

        # Make sure line is empty as a bytes object
        line = ""

        
        # Try to get a line from the queue. We don't block but we do wait a second in case it's not right there
        try:
            line = analyzeq.get(timeout=1).decode('UTF-8')
            # trim trailing newline
            line = line.rstrip()

        except KeyboardInterrupt:
            # Disable alerts
            logging.info("Alerts disabled for keyboard interrupt")
            alerts_disabled=1
            analyzeproc.kill()
            return False
        except Empty:
            logging.info("Queue empty")

        
        if "https @ " in line:
            logging.info(line)

        # Suppress logging blackframe messages because super noisy                
        elif (SUPPRESS_BLACKFRAME_LOGGING):
            if (b'Parsed_blackframe' not in line):                
                if (SUPPRESS_FFMPEG_LOGGING == 0):
                    logging.debug(line)        

        '''
        Possible error responses:
        Server error: Failed to play stream
        Input/output error
        
        Need a regex to match for video found!
        Sample: Stream #0:0: Video: h264 (Baseline), yuv420p, 640x360 [SAR 1:1 DAR 16:9], 655 kb/s, 25 tbr, 1k tbn, 50 tbc
        Should also look for audio
        '''
        
        if ("Stream #0:0: Video" in line):
            logging.info("Found stream " + stream)
            logging.info(line)
            #return True
        if ("Stream #0:1: Video" in line):
            logging.info("Found stream " + stream)
            logging.info(line)
            #return True

        # print (line)  # Uncomment for debugging ffmpeg problems
        
        # See if it's time to update the frame grab thumbnail
        # print (time.time() - last_framegrab_time)
        # print FRAME_GRAB_INTERVAL
        if (time.time() - last_framegrab_time) > int(FRAME_GRAB_INTERVAL):
            update_frame_grab()
            last_framegrab_time = time.time()
    

        # If we see an error check to see if it's after the ramp up time, otherwise we ignore it
        if ( (time.time() - program_start_time) > RAMPUP_TIME ):

            if ("lavfi.freezedetect.freeze_start" in line):                
                # Suppress this alert if we also have a potential blackframe issue, which takes priority
                if not blackframe_timer_running or FREEZE_PRIORITY:
                    logging.info("FREEZEFRAME DURATION EXCEEDED " + FREEZETIME_SECONDS_ALLOWED + "sec")
                    send_message ("FREEZEFRAME DURATION EXCEEDED" + FREEZETIME_SECONDS_ALLOWED + "sec")
                    freeze_frame_in_progress = 1
                else:
                    logging.info("Suppressing freeze alert due to black screen")                
        
        
            if ("silence_start" in line):
                logging.info("SILENCE DURATION EXCEEDED")
                send_message ("SILENCE DURATION EXCEEDED")
                audio_silent_in_progress = 1


            # Extract and analyze quantity of contiguous frames
            # to determine if the stream is still giving us new data
            # logging.info("line is " + line)
            # Requires ffmpeg to log in debug level
            p = re.compile('.*\[debug\] frame:(\d+).*')        
            if (p.match(line)):
            #     print "Matched\n"
                for match in p.finditer(line):
                    frame = int(match.group(1))
                    logging.info ("Got frame: " + str(frame))                    
                    if (frame > last_frame):
                        last_frame=frame
                        watching_stale_frames = 0
                        if (stale_frames_in_progress):
                            logging.info("NO_NEW_FRAMES CONDITION ENDED")
                            send_message("NO_NEW_FRAMES CONDITION ENDED")
                            stale_frames_in_progress = 0
                    else:
                        if (watching_stale_frames == 0):
                            stale_frame_start_time = time.time()
                            watching_stale_frames = 1
                        logging.info(time.time() - stale_frame_start_time)
                        if ((time.time() - stale_frame_start_time > STALE_FRAME_TIMEOUT) and stale_frames_in_progress == 0):
                            logging.info("NO_NEW_FRAMES DURATION EXCEEDED " + STALE_FRAME_TIMEOUT + "sec")
                            send_message("NO_NEW_FRAMES DURATION EXCEEDED " + STALE_FRAME_TIMEOUT + "sec")
                            stale_frames_in_progress = 1
                        


            #         blackframe = match.group(1)
                    
            #         # print "last keyframe: " + match.group(2) + "\n"
            #         last_kf = match.group(2)
            #         total_blackframes=int(blackframe)-int(last_kf)
            #     print "Blackframes: " + str(total_blackframes)
            
            # # If we see an error and it's after the ramp up time
            # elif ("error" in line):
            #     if (time.time()-start_time) > RAMPUP_TIME:
            #         return False
            #     else:
            #         logging.info("Ignoring startup error: " + line)

            
            # The blackframe_timer times how long we have been getting black frames
            # The blackframe_last_seen timer times how long its been since we have seen a blackframe

            # If a blackframe is seen:
            # logging.info("line is " + line)
            p = re.compile('\[Parsed_blackframe_1.* frame:(\d+).* last_keyframe:(\d+)')            
            if (p.match(line)):
                logging.info('blackframe seen')

                # Reset the blackframe_last_seen timer
                blackframe_last_seen_time = time.time()

                # If the blackframe_timer is (already) running
                if (blackframe_timer_running):
                    logging.info('blackframe_timer: ' + str(round(time.time() - blackframe_timer)))
                    # Send an alert if it's more than n seconds                    
                    if (time.time() - blackframe_timer) > float(BLACKFRAME_SECONDS_ALLOWED):
                        # Send an alert if we haven't already
                        if not blackframe_alerted_latch:
                            logging.info("BLACKFRAME DURATION EXCEEDED " + BLACKFRAME_SECONDS_ALLOWED + "sec")
                            send_message("BLACKFRAME DURATION EXCEEDED " + BLACKFRAME_SECONDS_ALLOWED + "sec")
                            blackframe_alerted_latch = 1                        

                # Else start the blackframe_timer
                else:
                    logging.info('Starting blackframe_timer')
                    blackframe_timer_running = 1
                    blackframe_timer = time.time()


            # If the blackframe_last_seen timer is more than n seconds
            if ((time.time() - blackframe_last_seen_time) > BLACKFRAME_RESET_TIME):

                # logging.info('Resetting blackframe_timer')

                # Stop and reset the blackframe_timer
                blackframe_timer_running = 0
                blackframe_timer = time.time()
                blackframe_alerted_latch = 0 

            # Send a restored alert for black frame
            if "black_end" in line and blackframe_alerted_latch and SEND_RESTORED_ALERTS:
                send_message("Blackframe issue ended")
                blackframe_timer_running=0

            # Send a restored alert for frozen
            if "freeze_end" in line and freeze_frame_in_progress and SEND_RESTORED_ALERTS:
                send_message("Freezeframe issue ended")
                freeze_frame_in_progress=0

            # Send a restored alert for audio
            if "silence_end" in line and audio_silent_in_progress and SEND_RESTORED_ALERTS:
                send_message("Audio restored")
                audio_silent_in_progress = 0

        else:
            # logging.info("Ignoring condition because RAMPUP_TIME not exceeded")
            pass

        # See if the analyze process has exited
        if (analyzeproc.poll() != None):
            logging.info("Analyze thread died")
            # Print a dump of ffmpeg processes from ps
            # print (subprocess.check_output("ps -ef | grep ffmpeg", shell=True))

            return False
        else:
            # logging.info("Analyze thread still alive with pid " + str(analyzeproc.pid))
            pass
        

            
        
    
# Send given message to Apprise system
def send_message(msg):
    logging.info ("alerts_disabled: " + str(alerts_disabled) + " alerts_hard_disabled: " + str(alerts_hard_disabled))
    if not alerts_disabled and not alerts_hard_disabled:
        logging.info ("INIT SENDING ALERT: ")
        subj = stream_desc + ":"
        logging.info (subj + " " + msg)

        logging.info("Sending alert to pushover user ")        

        apobj.notify(
            body=msg,
            title=subj
        )
        
        time.sleep (1)  # Wait a second here to ensure we don't send too many alerts too quickly

        logging.info ("Logging alert to database")

        # Insert this alert into the database 
        dbname = get_database()
        stream_alerts_collection = dbname[stream_alerts_collection_name]

        dateTimeObj = datetime.now()
        mytime = dateTimeObj.now().strftime("%Y-%m-%d %H:%M:%S")

        mydict = {'timestamp': mytime, 'stream': stream_desc, 'alert': msg, 'image': return_frame_grab()}

        stream_alerts_collection.insert_one(mydict)

    else:
        logging.info("Alerts are hard-disabled, Skipping alert")




##################################################################################################
# Convenience functions
##################################################################################################

def convert2unicode(mydict):
    for k, v in mydict.iteritems():
        if isinstance(v, str):
            mydict[k] = unicode(v, errors = 'replace')
        elif isinstance(v, dict):
            convert2unicode(v)

def live_analyze():
    pass

def launch_process_to_q(command, q):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)    
    t1 = threading.Thread(target=enqueue_output, args=(process.stdout, q))
    t2 = threading.Thread(target=enqueue_output, args=(process.stderr, q))
    t1.start()
    t2.start()
    return process

def enqueue_output(output, q):
    for line in iter(output.readline, b''):
        q.put(line)
    output.close()

logging.info("(re)starting...")


if __name__ == "__main__":
    main()
