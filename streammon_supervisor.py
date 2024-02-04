#!/usr/bin/python3

'''
streammonitor_supervisor.py
This is a python script supervisor that starts, kills, or otherwise controls any number of monitor processes
It is part of the streammonitor system, which is a set of tools for monitoring audio streams for silence, black, and freeze frames

Author:  Scott McGrath (scott@smcgrath.com)

'''

import psutil
import os,signal
import time
import subprocess
from subprocess import PIPE, Popen
from config import MONGO_CONNECTION_STRING, OPERATING_DIRECTORY, MONGO_DATABASE_NAME, USER

database_name = str(MONGO_DATABASE_NAME)
# Remove quotes
database_name = database_name.replace('"', '')

operating_directory= str(OPERATING_DIRECTORY)
# Remove quotes
operating_directory = operating_directory.replace('"', '')

username = str(USER)
# Remove quotes
username = username.replace('"', '')


global_configs_collection_name = "global_configs"
stream_configs_collection_name = "stream_configs"
stream_reports_collection_name = "stream_reports"
users_collection_name = "users"
base_dir = str(OPERATING_DIRECTORY)
log_dir = base_dir + "/public_html/logs"


# Install a signal handler for shutting down gracefully
class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True

def main():

    # Install a signal handler for shutting down gracefully
    killer = GracefulKiller()


    # Connect to the database
    dbname = get_database()
    print ("Connected to database " + dbname.name + "\r\n")

    stream_configs_collection = dbname[stream_configs_collection_name]
    global_configs_collection = dbname[global_configs_collection_name]
    stream_reports_collection = dbname[stream_reports_collection_name]
    # users_collection = dbname[users_collection_name]

    while (1):

        print ("Checking global config...\r\n")
        # Review the global config and see if anything needs attention
        result=global_configs_collection.find()

        # If the collection is empty, insert a default doc
        if (result.count() == 0):
            print ("No global config found, creating...\r\n")
            global_configs_collection.insert_one({"global_configs": "1", "restart_due": "0"})

        
        for i in result:
            if i["restart_due"] == "1":
                print ("Restart requested. Killing all processes\r\n")
                kill_all_monitors()
                # Reset the restart request
                global_configs_collection.update_one({"global_configs": "1"}, {"$set": {"restart_due": "0"}})



        print ("Checking streams...\r\n")
        # Make sure there is a monitor running for each ENABLED stream in the config
        result=stream_configs_collection.find()

        # If the collection is missing, print an error and exit
        if (result.count() == 0):
            print ("No stream configs found, please configure a stream to watch or load some initial data...\r\n")            
        else:
            for i in result:    
                print(i["title"],end=" ")

                # If this doc has NECESSARY & VALID INFO (i.e. a stream uri, a title, etc.), do stuff, otherwise, skip.
                if len(i["title"]) >= 1 and len(i["uri"]) >= 4:

                    # See if the process is running
                    pid=check_monitor(i["uri"])
                    if (pid):
                        print ("Running = 1, ",end="")
                        # See if it should be
                        if i["enabled"] == "1":            
                            print ("Enabled = 1, action: none\r\n")
                            # Take this opportunity to update the stream report in the database
                            stream_reports_collection.update_one({'title': i["title"]},{'$set': {'status': tailshell(i["title"])}},True) #upsert

                        else:
                            print ("Enabled = 0, action: kill\r\n")    
                            #restart_monitor(i["uri"],i["stream_title"])
                            kill_monitor(pid)
                    else:
                        print ("Running = 0, ")
                        # See if it should be
                        if i["enabled"] == "1":            
                            print ("Enabled = 1, action: start\r\n")
                            restart_monitor(i["uri"],i["title"],i["audio"] == "1")
                        else:
                            print ("Enabled = 0, action: none\r\n")
                else:
                    print ("Ignoring partially/not populated db entry\r\n")

        if killer.kill_now:
            shutdown()
        time.sleep(1)                  
                


# If a shutdown signal is received, run kill all monitors
def shutdown():
    print ("Shutdown signal received")
    kill_all_monitors()
    time.sleep(5)
    exit(0)

def tailshell(title):
    # Returns the last line in the monitor's log file
    try:
        with open(log_dir+'/'+title+'.log', 'rb') as f:
            try:  
                f.seek(-2, os.SEEK_END)
                while f.read(1) != b'\n':
                    f.seek(-2, os.SEEK_CUR)
            except OSError:
                f.seek(0)
            last_line = f.readline().decode()
            return last_line
    except FileNotFoundError:
        return "No log file found"


def kill_monitor(pid):
    print ("Killing PID " + str(pid) +"\r\n")
    os.kill(pid, signal.SIGKILL)

def kill_all_monitors():
    # kill the monitor probes by iterating through the process stack
    for line in os.popen("ps ax | grep sjmstreammonitor | grep -v grep"):
        fields = line.split()
        
        # extracting Process ID from the output
        pid = fields[0]
        
        print ("PID "+pid) 

        # terminating process
        os.kill(int(pid), signal.SIGKILL)
        print(pid + "Stream probe Process Successfully terminated")

    # Kill ffmpeg processes
    # iterating through each instance of the process
    for line in os.popen("ps ax | grep ffmpeg | grep -v grep"):
        fields = line.split()
            
        # extracting Process ID from the output
        pid = fields[0]
            
        # terminating process
        os.kill(int(pid), signal.SIGKILL)
        print(pid + "ffmpeg Process Successfully terminated")


# starting a missing monitor
def restart_monitor(stream_uri, stream_desc, audio_only=0):
    # Connect to the necessary database collections
    dbname = get_database()
    stream_configs_collection = dbname[stream_configs_collection_name]
    users_collection = dbname[users_collection_name]

    pushover_list=[]

    print ("Starting monitor " + stream_desc +"\r\n")
    # Clear the log file
    os.system("rm -f \"" + log_dir + "/"+ stream_desc +".log\"")

    # kill the old monitor
    # if (pid):
    #     kill_monitor(pid)

    # Get the notification info for delivery to the new monitor via arguments
    
    pushover_list.clear()
    result=users_collection.find()    
    for i in result:
        # If there is an actual pushover key, and notification is enabled...
        if len(str(i["pushover_id"])) > 0 and i["enabled"] == "1":         
            pushover_list.append(" --pushover ")
            pushover_list.append(i["pushover_id"]+"@"+i["pushover_token"])
        else: 
            print ("Skipping " + i["pushover_id"] + " with length: ")
            print (len(str(i["pushover_id"])))
            print ("enabled = " + str(i["enabled"]))
    pushover_string =  "".join(pushover_list)
    
    if (audio_only):
        moncmd = "sudo -u " + username + " /usr/bin/python " + base_dir + "/sjmstreammonitor-withprobe.py "+ pushover_string + " --audio_only --silence_duration 60 --stream_uri \"" + stream_uri + "\" --stream_desc \"" +stream_desc +"\" > /dev/null"
    else:
        moncmd = "sudo -u " + username + " /usr/bin/python " + base_dir + "/sjmstreammonitor-withprobe.py "+ pushover_string + " --freeze_duration 600 --black_duration 60 --silence_duration 60 --stream_uri \"" + stream_uri + "\" --stream_desc \"" +stream_desc +"\" > /dev/null"
    print (moncmd)

    Popen (moncmd,shell=True)


# This function checks to see if a monitor is running by looking for the stream_uri in the command line of all running processes
    # If it is, it returns the PID
    # If it isn't, it returns false
def check_monitor (stream_uri):
    
    listOfProcessNames = list()
    # Iterate over all running processes
    for proc in psutil.process_iter(): 
        
        # Get process detail as dictionary
        pInfoDict = proc.as_dict(attrs=['pid', 'name', 'cmdline'])
        # Append dict of process detail in list
        listOfProcessNames.append(pInfoDict)
        
        #print ("\n");
        try:
            for line in proc.cmdline():        
                # print (stream_uri);
                # print (line)
                if stream_uri in line:
                    # print ("KILLING")
                    # Found it

                    # Return this pid 
                    return proc.pid
        except psutil.NoSuchProcess:
            continue
        except psutil.ZombieProcess:
            continue
    # Default action returns false (didn't find it)


# This function deals with connecting to the database
def get_database():
    from pymongo import MongoClient
    import pymongo

    print ("get_database()\r\n")
    
    # Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure

    client = MongoClient(str(MONGO_CONNECTION_STRING))
    try:
        # The ping command is cheap and does not require auth.
        client.admin.command('ping')
    except ConnectionFailure:
        print("Server not available")

    print ("Server available\r\n")

    # Print all the databases found    
    # for db in client.list_databases():
    #     print(db)

    # Return the database handle
    return client[database_name]
    




if __name__ == "__main__":
    main()
