# StreamMonitor

Continuously monitors one or more continuous audio and video streams for connection and content issues, such as: audio silence, extended black frame, extended freeze frame, and more. Logs these events along with frame grabs and sends notifications to technical personnel about the same. Can be run on a virtual private server with as little as a single core shared CPU, and 1GB RAM (tested: 5 streams simultaneous)

![streammonitor screenshot](http://smcgrath.com/hosted_images/streammon_screenshot1.png)

![streammonitor screenshot](http://smcgrath.com/hosted_images/streammon_screenshot2.png)

Besides failure of the entire stream, it is intended only to alert about fairly high-level issues, such as those a human viewer would detect. It does not aim to analyze stream data such as latency, throughput, framerate, dropouts, and other quality issues that occur at the transport layer and below.

## Features

### Stream Monitoring
- Monitor RTSP, RTMP, HTTP(S), UDP, and other FFmpeg-compatible streams
- Per-stream audio-only or video monitoring modes
- Configurable detection thresholds for:
  - Black frame duration (default: 60s)
  - Freeze frame duration (default: 600s)
  - Audio silence duration (default: 60s)
  - Stream connection failures

### Alert Management
- Real-time alerts via Pushover
- Alert history with frame captures
- Searchable alert log with filters
- Per-user and per-stream alert configuration
- Alert suppression capabilities

### User Management
- Multi-user support with role-based access
- Individual Pushover credentials per user
- Enable/disable users without deletion
- Password management with bcrypt hashing
- Session-based authentication

### Stream Management
- Add/remove/configure streams via web UI
- Enable/disable monitoring per stream
- Live status reporting
- Thumbnail previews updated every minute
- Graceful stream failure handling with configurable grace periods

### System Management
- Restart scheduling for supervisor
- Global alert disable switches
- Per-stream alert configuration
- Systemd service integration

## Alert Conditions - Video

The following conditions are recognized and cause an alert:

- Interruption in the actual stream connection
- Black screen for more than 60 seconds
- Freeze frame for more than 600 seconds (10 minutes)
- Audio Silence for more than 60 seconds

## Alert Conditions - Audio

The following conditions are recognized and cause an alert:

- Interruption in the actual stream connection
- Audio Silence for more than 60 seconds

These durations and other parameters can be adjusted, see the Configuration section below for details.

## Architecture

The system consists of:

- **React UI**: Modern web interface for configuration and monitoring
- **Express/TypeScript API**: RESTful backend with session-based authentication
- **Python Supervisor**: Manages monitor agent lifecycle
- **Python Monitor Agents**: Individual stream monitors using FFmpeg
- **MongoDB**: Database for configuration, reports, and alerts
- **nginx**: Web server and reverse proxy

**Authentication**: Session-based auth with bcrypt password hashing. Users must be enabled and authenticated to access the system.

**Data Flow**:
```
Browser → nginx → Express API → MongoDB ← Python Agents
                    ↓
              React UI (static files)
```

**Component Details**:

- `sjmstreammonitor-withprobe.py` - Monitor agent that runs FFmpeg for a single stream and analyzes output for alert conditions
- `streammon_supervisor.py` - Ensures monitor agents are running as configured, manages their lifecycle, and reports status to database
- React UI - Provides web interface for stream management, user administration, alert history, and system configuration
- Express API - Handles authentication, database operations, and serves as middleware between UI and MongoDB

```
                                          ┌───────────────┐
                                          │               │
                                          │   Supervisor  │
                                ┌─────────┤   (Python)    ├────────┐
                                │         │               │        │
                                │         └───────────────┘        │
                                │                                  │
                         ┌──────┴──────┐                    ┌──────┴────────┐
                         │             │                    │               │
                         │  DB (Mongo) │                    │ Stream monitor│
                         │             ├────────────────────┤    Agent      │
                         │             │                    │   (Python)    ◄────────┐
                         └───┬─────────┘                    │               │        │
                             │                              └──────┬────────┘        │
                             │                                     │                 │
                             │                                     │                 │
                             │                                     │                 │
    ┌────────────┐    ┌──────▼─────┐                               │                 │
    │            │    │            │                               │                 │
    │  React UI  │    │  Express/  │                        ┌──────▼────────┐        │
    │            ◄────┼    API     │                        │               │   ┌────┴────┐
    │            │    │            │                        │    FFMPEG     │   │         │
    │            │    │            │                        │               ├───► LOG (TXT)
    └────────────┘    └────────────┘                        │               │   │         │
                                                            └───────────────┘   └─────────┘
```

## Installation

### Prerequisites

**Required Software:**
- Ubuntu 22.04 or 24.04 (tested) or compatible Linux distribution
- nginx web server
- FFmpeg 4.2.7 or higher
- MongoDB 7.0 or higher
- Python 3.10+ with pip
- Node.js v18 or higher with npm

**Required Python Packages:**
- pymongo
- Pillow (python-imaging)
- psutil
- python-dotenv
- apprise

**System Requirements:**
- Minimum: 1 vCPU, 1GB RAM (tested with 5 concurrent streams)
- Recommended: 2 vCPU, 2GB RAM for 10+ streams
- Disk space: ~500MB for application + log storage

### Quick Installation

1. **Clone the repository:**
   ```bash
   mkdir ~/StreamMonitor
   cd ~/StreamMonitor
   git clone [repo-url] .
   ```

2. **Run the installer:**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Follow the prompts:**
   - Accept defaults for most options
   - Choose a DNS name for nginx virtual host
   - **IMPORTANT**: Do NOT load initial data if updating existing installation
   - The script will:
     - Install dependencies
     - Configure MongoDB (WARNING: No authentication by default)
     - Create nginx virtual host configuration
     - Generate systemd service units
     - Build React UI
     - Install Express API dependencies
     - Generate secure session secret

4. **Set directory permissions:**
   ```bash
   # Allow nginx to traverse parent directories
   chmod a+x ~ ~/StreamMonitor
   ```

5. **Verify services are running:**
   ```bash
   sudo systemctl status streammon_supervisor
   sudo systemctl status streammon_api
   sudo systemctl status nginx
   sudo systemctl status mongod
   ```

### Post-Installation Configuration

#### 1. Change Default Credentials

**Default login:**
- Username: `streamadmin`
- Password: `changeme`

⚠️ **IMMEDIATELY** log in and change these credentials:
1. Navigate to http://[your-server]/
2. Log in with default credentials
3. Go to "Modify Users"
4. Change the password or create a new admin user and delete the default

#### 2. Configure MongoDB Security (Production)

The default installation has NO MongoDB authentication. For production:

```bash
# Enable authentication in MongoDB
sudo nano /etc/mongod.conf
# Add:
# security:
#   authorization: enabled

# Create admin user
mongosh
use admin
db.createUser({
  user: "streammon_admin",
  pwd: "your_secure_password",
  roles: ["readWrite", "dbAdmin"]
})

# Update config.py and .env with new connection string
```

#### 3. Configure Pushover Notifications

For each user who should receive alerts:
1. Sign up at [Pushover.net](https://pushover.net)
2. Create an application to get an API token
3. In the UI, go to "Modify Users"
4. Add the User Key and App Token for each user

#### 4. Add Streams

1. Go to "Modify Streams"
2. Click "Add Stream"
3. Enter:
   - **Title**: Descriptive name
   - **URI**: Stream URL (rtsp://, http://, udp://, etc.)
   - **Type**: Toggle Audio/Video mode
   - **Enabled**: Toggle to start monitoring
4. Click "Save All Changes"
5. System will restart supervisor to apply changes

### Configuration Files

#### config.py
Located in the installation root, contains system-wide settings:

```python
MONGO_CONNECTION_STRING = "mongodb://localhost:27017/?authSource=admin"
MONGO_DATABASE_NAME = "streammon"
OPERATING_DIRECTORY = "/home/scott/StreamMonitor"
USER = "scott"
ALERTS_DISABLED = 0  # Global alert disable
STREAMDOWN_ALERTS_DISABLED = 0  # Disable only connection alerts
STREAM_FAILURE_GRACE_PERIOD = 60  # Seconds before alerting on failure
STREAM_FAILURE_RETRY_INTERVAL = 10  # Seconds between reconnection attempts
ENABLE_GRACEFUL_STREAM_FAILURE = 1  # Handle transient failures gracefully
```

You need to create this file from config.py.example before anything will work. Additional configurable parameters (freeze frame duration, silence duration, black frame duration, audio volume threshold) are located in `streammon_supervisor.py`.

#### .env (Express API)
Located in `StreamMonitor_Express_API/.env`:

```bash
MONGO_URI=mongodb://localhost:27017/streammon
SESSION_SECRET=[generated-32-byte-base64-string]
```

⚠️ Never commit `.env` to version control or share `SESSION_SECRET`

### File Structure

```
StreamMonitor/
├── install.sh                          # Installation script
├── config.py                          # System configuration
├── sjmstreammonitor-withprobe.py     # Monitor agent
├── streammon_supervisor.py            # Supervisor process
├── schema_update.py                   # Database migration tool
├── StreamMonitor_React_UI/            # Frontend
│   ├── src/                          # React source
│   ├── build/                        # Production build
│   └── public/                       # Static assets
├── StreamMonitor_Express_API/         # Backend API
│   ├── src/                          # TypeScript source
│   └── .env                          # API configuration
├── public_html/                       # Nginx document root
│   └── logs/                         # Agent log files
└── mongodb_init/                      # Initial database data
```

## Configuration

The UI allows the creation/deletion of users, streams, and notification information. Individual stream monitoring and notifications on a per-stream/per-user basis can be enabled or disabled without removing entries from the database. The system currently requires a Pushover User Key and App Token to be provided for each user who will receive notifications.

In addition, configurable parameters are located in `config.py` and at the head of `streammon_supervisor.py`. The configurable parameters include:

- Acceptable freeze frame duration
- Acceptable audio silence duration
- Acceptable black frame duration
- Audio volume threshold considered to be "silence"
- Stream failure grace period
- Stream failure retry interval
- Global alert disable switches

## Operation

### Starting/Stopping the System

**Start all services:**
```bash
sudo systemctl start mongod
sudo systemctl start streammon_api
sudo systemctl start streammon_supervisor
sudo systemctl start nginx
```

**Stop all services:**
```bash
sudo systemctl stop streammon_supervisor  # Stop this first!
sudo systemctl stop streammon_api
sudo systemctl stop nginx
# MongoDB can remain running
```

**Check status:**
```bash
# View service status
sudo systemctl status streammon_supervisor
sudo systemctl status streammon_api

# View live logs
sudo journalctl -fu streammon_supervisor
sudo journalctl -fu streammon_api

# Check running monitor agents
ps aux | grep sjmstreammonitor
```

### Web Interface

Access the UI at: `http://[your-server]/`

**Main Views:**
- **Dashboard** (`/`): Live stream status and thumbnails
- **Modify Streams** (`/streams`): Add/edit/delete stream configurations
- **Modify Users** (`/users`): User management
- **Alert History** (`/alerts`): Searchable alert log with images
- **System Settings** (`/settings`): Global configuration

### Database Management

**Backup database:**
```bash
mongodump --db streammon --out ~/streammon-backup-$(date +%Y%m%d)
```

**Restore database:**
```bash
mongorestore --db streammon ~/streammon-backup-[date]/streammon/
```

**Update schema (after updates):**
```bash
cd ~/StreamMonitor
python3 schema_update.py --dry-run  # Preview changes
python3 schema_update.py            # Apply changes
```

## Updating

### Standard Update Procedure

1. **Backup everything:**
   ```bash
   # Backup database
   mongodump --db streammon --out ~/streammon-backup-$(date +%Y%m%d)
   
   # Backup installation
   cd ~
   cp -r StreamMonitor StreamMonitor.backup-$(date +%Y%m%d)
   ```

2. **Stop services:**
   ```bash
   sudo systemctl stop streammon_supervisor
   sudo systemctl stop streammon_api
   ```

3. **Update code:**
   ```bash
   cd ~/StreamMonitor
   git pull origin main  # or your branch
   ```

4. **Run installer (selective):**
   ```bash
   ./install.sh
   ```
   
   **Important responses:**
   - Install dependencies? **Y** (safe to reinstall)
   - Load initial database data? **N** (would reset everything!)
   - Overwrite config.py? **N** (unless you want defaults)
   - Generate nginx config? **N** (unless changed)
   - Install systemd units? **Y** (safe to reinstall)

5. **Update schema:**
   ```bash
   python3 schema_update.py
   ```

6. **Rebuild React UI:**
   ```bash
   cd StreamMonitor_React_UI
   npm install  # Update dependencies if needed
   npm run build
   ./sync_public_html.sh
   ```

7. **Restart services:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start streammon_api
   sudo systemctl start streammon_supervisor
   ```

8. **Verify:**
   - Check service status: `sudo systemctl status streammon_supervisor streammon_api`
   - Log in to web UI
   - Verify streams are monitoring
   - Check logs for errors: `sudo journalctl -xeu streammon_supervisor`

### Troubleshooting Updates

**If services won't start:**
```bash
# Check logs
sudo journalctl -xeu streammon_supervisor
sudo journalctl -xeu streammon_api

# Common issues:
# - Permission errors: Check file ownership
# - Port conflicts: Verify nginx/API ports
# - Database connection: Check MongoDB status
```

**If UI shows errors:**
- Clear browser cache
- Check nginx error log: `sudo tail -f /var/log/nginx/error.log`
- Verify React build completed: `ls -la ~/StreamMonitor/public_html/`

## Troubleshooting

### Common Issues

#### "Invalid host header" in browser
Create `StreamMonitor_React_UI/.env`:
```
DANGEROUSLY_DISABLE_HOST_CHECK=true
```
Rebuild: `npm run build && ./sync_public_html.sh`

#### Streams not monitoring
1. Check supervisor is running: `sudo systemctl status streammon_supervisor`
2. Check stream is enabled in UI
3. Check logs: `tail -f ~/StreamMonitor/public_html/logs/[stream-name].log`
4. Verify stream URL is accessible: `ffmpeg -i [url] -t 5 test.mp4`

#### No alerts received
1. Verify user Pushover credentials in UI
2. Check user and stream are enabled
3. Test Pushover: Send test notification from Pushover.net
4. Check global alert settings in config.py
5. Review alert history in UI to see if alerts were generated

#### Database connection errors
1. Check MongoDB is running: `sudo systemctl status mongod`
2. Verify connection string in config.py
3. Check .env file in Express API directory
4. Test connection: `mongosh "mongodb://localhost:27017/streammon"`

#### Permission denied errors
```bash
# Fix ownership
sudo chown -R [your-user]:www-data ~/StreamMonitor
sudo chmod -R 755 ~/StreamMonitor/public_html

# Fix parent directory permissions
chmod a+x ~ ~/StreamMonitor
```

#### React UI not loading
1. Check nginx is running: `sudo systemctl status nginx`
2. Verify build exists: `ls ~/StreamMonitor/public_html/index.html`
3. Check nginx config: `sudo nginx -t`
4. Check nginx logs: `sudo tail -f /var/log/nginx/error.log`

### Log Locations

- **Supervisor logs**: `sudo journalctl -fu streammon_supervisor`
- **API logs**: `sudo journalctl -fu streammon_api`
- **Monitor agent logs**: `~/StreamMonitor/public_html/logs/[stream-name].log`
- **nginx logs**: `/var/log/nginx/error.log` and `access.log`
- **MongoDB logs**: `/var/log/mongodb/mongod.log`

### Getting Help

When reporting issues, include:
- Output of `sudo systemctl status streammon_supervisor streammon_api`
- Relevant log excerpts
- Your OS version: `lsb_release -a`
- FFmpeg version: `ffmpeg -version`
- Node version: `node --version`
- MongoDB version: `mongod --version`

## Security Considerations

### Production Deployment Checklist

- [ ] Change default admin credentials immediately
- [ ] Enable MongoDB authentication
- [ ] Use strong passwords for all users
- [ ] Keep SESSION_SECRET secure and never commit to version control
- [ ] Run behind HTTPS (configure nginx with SSL/TLS)
- [ ] Restrict MongoDB to localhost or use firewall rules
- [ ] Keep system and dependencies updated
- [ ] Regular database backups
- [ ] Limit SSH access to trusted IPs
- [ ] Review nginx access logs periodically

### Securing MongoDB

```bash
# Create admin user
mongosh
use admin
db.createUser({
  user: "admin",
  pwd: "strong_password_here",
  roles: ["userAdminAnyDatabase", "readWriteAnyDatabase"]
})

# Enable auth in config
sudo nano /etc/mongod.conf
# Add: security.authorization: enabled

# Update connection strings in config.py and .env
MONGO_CONNECTION_STRING = "mongodb://admin:password@localhost:27017/streammon?authSource=admin"
```

### Enabling HTTPS

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured by default
```

## Notifications

Currently, [Pushover](https://pushover.net) notifications are supported via the [Apprise python library](https://pypi.org/project/apprise/).
Support for additional notification types is planned.

## Project Status

**Production Ready**: Yes, with caveats
- Extensively tested monitoring 5+ streams for 2+ years
- Reliable detection of stream failures and content issues
- Stable React UI with authentication and session management

**Known Limitations**:
- MongoDB installed without authentication by default (must secure for production)
- Limited documentation for advanced configuration
- No automated backup system (must implement manually)
- No built-in high-availability or failover
- Some configuration requires editing Python files and service restart

**Planned Improvements**:
- Additional notification providers beyond Pushover
- Enhanced analytics and reporting
- Multi-server deployment support
- Improved configuration UI for all parameters
- Better error recovery and self-healing

**Browser Support**: Modern browsers with ES6+ support (Chrome, Firefox, Safari, Edge)

**Tested Platforms**:
- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Should work on Debian-based distributions with minor adjustments
