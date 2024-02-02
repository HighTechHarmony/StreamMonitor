# streammonitor

Continuously monitor multiple audio and video streams for both connection and content problems. Get alerts.

![streammonitor screenshot](http://smcgrath.com/hosted_images/streammon_screenshot1.png)

![streammonitor screenshot](http://smcgrath.com/hosted_images/streammon_screenshot2.png)

## Alert conditions - video

Besides an interruption in the actual stream connection, the following conditions are recognized and cause an alert:

- Black screen for more than 60 seconds
- Freeze frame for more than 600 seconds (10 minutes)
- Audio Silence for more than 60 seconds

## Alert conditions - audio

Besides an interruption in the actual stream connection, the following conditions are recognized and cause an alert:

- Audio Silence for more than 60 seconds

These durations can be adjusted in supervisor.py

## Notifications

Currently pushover notifications are supported via the [Apprise python library](https://pypi.org/project/apprise/).
Support for lots more notification types are planned.

## Structure

The system currently consists of Python scripts and a PHP web interface, communicating via a MongoDB database.

\*sjmstreammonitor-withprobe.py is a probe that for a single stream, runs ffmpeg and monitors the output for various conditions.

\*streammonitor_supervisor.py is responsible for ensuring probe scripts that are supposed to be running are, ones that shouldn't aren't, and reporting the status to the database.

\*The web interface allows the user to provide stream URLS to monitor, enable and disable monitoring on a per stream basis, and administer a pushover token which will receive alerts.

## Installation

### Dependencies

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

You can try the included install.sh script. It has been tested on Ubuntu 22.04 server. It asks you lots of questions (with defaults available). It will ask for the root password for certain tasks.

install.sh attempts to:

- install above prerequistes
- load mongodb initial data
- create an apache2 name-based virtual host
- create a systemd service unit for the supervisor

WARNING: MongoDB is installed with no authentication, so you need to secure it.

There are some things it might not do well yet, but reading it can give you a better overview of what's needed, if nothing else.

### Alternative: Install MongoDB PHP driver library manually via composer

This can be a challenge. Some basics for a Debian/Ubuntu system:

`apt install php-pear php-dev`

`pecl install mongodb`

`apt install composer`

(as user) `composer require mongodb/mongodb --ignore-platform-reqs`

`composer require jenssegers/mongodb --ignore-platform-reqs`

Don’t underestimate how long the above commands will take.

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

The first thing you should do is go into "Users" panel and change this to something else, or create a new user and delete this one.
