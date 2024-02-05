# StreamMonitor

Continuously monitors one or more continuous audio and video streams for connection and content issues, such as: audio silence, extended black frame, extended freeze frame, and more. Logs these events along with frame grabs and sends notifications to technical personnel about the same. Can be run on a virtual private server with as little as a single core shared CPU, and 1GB RAM (tested: 5 streams simultaneous)

![streammonitor screenshot](http://smcgrath.com/hosted_images/streammon_screenshot1.png)

![streammonitor screenshot](http://smcgrath.com/hosted_images/streammon_screenshot2.png)

Besides failure of the entire stream, it is intended only to alert about fairly high-level issues, such as those a human viewer would detect. It does not aim to analyze stream data such as latency, throughput, framerate, dropouts, and other quality issues that occur at the transport layer and below.

## Alert conditions - video

The following conditions are recognized and cause an alert:

- Interruption in the actual stream connection
- Black screen for more than 60 seconds
- Freeze frame for more than 600 seconds (10 minutes)
- Audio Silence for more than 60 seconds

## Alert conditions - audio

The following conditions are recognized and cause an alert:

- Interruption in the actual stream connection
- Audio Silence for more than 60 seconds

These durations and other parameters can be adjusted, see the section on #configuration below for details.

## Status of this project, and known limitations

The idea of this system was born of a TV station Content Managers' need to monitor linear video and audio streams for reliability issues, processing equipment failures, or problematic content. At worst, this implementation primarily serves as a functional demonstration for a basic, extremely cost-efficient self-hosted monitoring system that works 24/7 to provide technical staff with insights on problematic stream behavior or content.

- There are bugs that can cause the system to break, most of these occur at configuration-time.
- The UI is very rudimentary, using static HTML with tables and refreshing, only allowing quick access to the most basic and important review and configuration needs
- In the UI, live data about each stream is undigested and doesn't really provide the user with conclusive info other than to know that the stream is actively being monitored.

That being said, the system in its current state has been tested extensively in a production environment, and has shown to be extremely reliable - monitoring multiple video streams around-the-clock for over almost 2 years without any surprise failures. The deployment, while not fully automated, can be scaled in a trivial way by adding VPS instances. At present, most VPS providers rarely charge extra for download data transfer, so adding streams doesn't add to the cost of the deployment.

## Notifications

Currently, [Pushover](https://pushover.net) notifications are supported via the [Apprise python library](https://pypi.org/project/apprise/).
Support for lots more notification types are planned.

## Structure

The system currently consists of Python scripts and a PHP web interface, communicating via a MongoDB database.

\*sjmstreammonitor-withprobe.py is a probe that for a single stream, runs ffmpeg and monitors the output for various conditions.

\*streammonitor_supervisor.py is responsible for ensuring probe scripts that are supposed to be running are, ones that shouldn't aren't, and reporting the status to the database.

\*The web interface allows the user to provide stream URLS to monitor, enable and disable monitoring on a per stream basis, and administer a pushover token which will receive alerts.

## Installation

### Dependencies

Essentially:

- FFmpeg 4.2.7 or higher
- MongoDB
- Python3
- Python-imaging
- PyMongo
- Apache2 with PHP
- MongoDB PHP driver extension & library
- Python PSutil
- Apprise (notification framework)

### Review (and run) install script

You can try the included install.sh script. It has been tested on Ubuntu 22.04 server. It asks you lots of questions, but accepting the defaults should result in a functional system on a template machine with the minimized Ubuntu deployment. It will ask for the root password for certain tasks.

install.sh attempts to:

- install above prerequistes
- load mongodb initial data
- create an apache2 name-based virtual host
- create a systemd service unit for the supervisor

WARNING: MongoDB is installed with no authentication, so you need to secure it.

To install the system, follow these steps:

- Create a new folder on your system
- cd into it
- clone the repository using `git clone (repo url)`
- run `./install.sh` as the user you wish the instance to run as.

The install script aims to compartmentalize the files necessary to run the instance as much as possible. Only when absolutely necessary are files copied outside of the installation directory. Specifically, this concerns the apache2 virtualhost configuration file, and systemd service unit.

There are some things the install.sh script might not do well yet, but reading it can give you a better overview of what's needed, if nothing else.

Tasks the install.sh script doesn't accomplish for you:

- Disabling the default apache virtualhost (to do this, type: `a2dissite 000-default.conf` as root)
- Apply execute permission to parent directories (to do this, type: `chmod a+x` on the installation directory and all of its parent directories, up to the root level)

In all, the system can be up and running on a barebones Ubuntu server installation within about 15 minutes of mostly automated downloading, building and compiling the prerequisites.

### Alternative: Install MongoDB PHP driver library manually via composer

This can be a challenge. Some basics for a Debian/Ubuntu system:

`apt install php-pear php-dev`

`pecl install mongodb`

`apt install composer`

(as user) `composer require mongodb/mongodb --ignore-platform-reqs`

`composer require jenssegers/mongodb --ignore-platform-reqs`

### Modify the generated config.py and fill in your connection string and pushover token default, like this:

You need to make a config.py file in order for anything to work. Here is an example config.py file.

```
CONNECTION_STRING = "mongodb://localhost:port/?authSource=admin&readPreference=primary&ssl=false"
MONGO_CONNECTION_STRING = "mongodb://localhost:27017/?authSource=admin&readPreference=primary&ssl=false"
MONGO_DATABASE_NAME = "streammon"
OPERATING_DIRECTORY = "/home/scott/streammon"
USER = "scott"
```

### IMPORTANT: Login and change the default login info

Once the installation is up and running, you can access the UI at http://server (port 80)

Default username:
`streamadmin`

Default password:
`changeme`

(Hopefully it is apparent that the first thing you should do is go into "Users" panel and change the password to something else, or create a new user and delete this one.)

## Configuration

The UI allows the creation/deletion of users, streams, and notification information. Individual stream monitoring and notifications on a per stream/user basis can be enabled or disabled without removing entries from the database. The system currently requires a Pushover ID and App token to be provided for each user who will receive notifications.

In addition, there are configurable parameters are located at the head of streammon_supervisor.py. The configurable paramaters include:

- Acceptable freeze frame duration
- Acceptable audio silence duration
- Acceptable black frame duration
- Audio volume threshold considered to be "silence"

## Operation

The primary components involved with putting the system into operation, or to stop it, are as follows:

- UI: Start or stop or disable the Apache2 virtualhost as configured (`sudo a2ensite name`, `sudo a2dissite name`, `sudo systemctl reload apache2`, `sudo systemctl start/stop apache2`, etc.)

- Backend: Start or stop the streammon_supervisor service using systemd (`sudo systemctl start/stop streammon_supervisor.service`). It will read the database, and if there are streams configured and enabled for monitoring, it will launch and manage agent processes as necessary. The supervisor process is expected to be running at all times, stopped only when the system is desired to be shutdown.

Checking the running status of the supervisor process can be done as follows:

`ps ax|grep streammon_supervisor.py`

## Updating

At this time, there is no update script yet. Therefore the recommended procedure is as follows:

- Apply updates to your OS as usual (e.g. apt update; apt dist-upgrade)
- Backup your existing installation folder (`mv streammonitor streammonitor.bak`, replace with your custom name if you have changed it)
- Clone the latest repository
- cd into the folder (default is: `streammonitor`)
- Run the install.sh script: `./install.sh`
- Do NOT load the inital mongodb data! (select 'n' when asked)
- Do NOT overwrite your config.py file if you have made customizations (select 'n' when asked)

Besides that, it should be safe to accept all of the rest of the defaults unless, of course, you have made custom entries to the directory, name, user, etc. It should be safe to install the prerequisites again, which will ensure that you have any new ones associated with the latest version. Once the install is complete, you should be up and running! However, a reboot is recommended.
