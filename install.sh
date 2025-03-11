#!/bin/sh

# First verify prequisites
# Determine if php is installed and what version

echo ""
echo ""
echo "This will setup the Stream Monitor Supervisor on your system based on"
echo "the current directory and user.  It may ask for your root password several times"
CURRENT_USERNAME="$(whoami)"
CURRENT_GROUPNAME="$(id -gn)"
CURRENT_DIRECTORY="$(pwd)"

echo "Detected username: $CURRENT_USERNAME"
echo "Detected groupname: $CURRENT_GROUPNAME"
echo "Detected directory: $CURRENT_DIRECTORY"

echo "Do you want to continue? (y/n)"
read -r response
# examine the response in a case insensitive manner
response=$(echo "$response" | tr '[:upper:]' '[:lower:]')
if [ "$response" != "y" ]; then
    echo "Aborting..."
    exit 1
fi

echo "Configuring timezone..."
sudo dpkg-reconfigure tzdata

# Do you want to automatically install dependencies?
read -r -p "Do you want me to try to automatically install dependencies? (Y/n) " install_dependencies_auto
# examine the response in a case insensitive manner
install_dependencies_auto=$(echo "$install_dependencies_auto" | tr '[:upper:]' '[:lower:]')
if [ "$install_dependencies_auto" = "n" ]; then
    echo "Skipping automatic dependency installation..."
else
echo "Installing dependencies..."
    sudo apt-get install python3 python3-pip python-is-python3 gnupg curl nginx \
        software-properties-common gnupg apt-transport-https ca-certificates \
        git nano iputils-ping ffmpeg zip unzip python3-pymongo python3-pillow -y

    curl -fsSL https://pgp.mongodb.com/server-7.0.asc |  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse
    sudo apt update
    sudo apt install mongodb-org -y

    # Install python dependencies for the normal user and for root

    # Constants
    # VENV_DIR="$CURRENT_DIRECTORY/venv"
    PYTHON_BIN="/usr/bin/python3"

    echo "Starting installation process..."

    # Check if Python 3 is installed
    # if ! command -v $PYTHON_BIN &> /dev/null; then
    #     echo "Error: Python 3 is not installed. Will attempt to install."
        
    #     # Install python3
    #     sudo apt install python3.10-venv -y
    #     sudo apt install python3 -y

    #     if ! command -v $PYTHON_BIN &> /dev/null; then
    #         echo "Error: Python 3 could not be installed. Please install Python 3 first."
    #         exit 1
    #     fi

    # fi

    if ($PYTHON_BIN -m pip --version); then
        echo "Pip is installed"
    else
        echo "Pip is not installed"
        sudo apt install python3-pip -y
    fi

    # # Create a virtual environment if it doesn't already exist
    # if [ ! -d "$VENV_DIR" ]; then
    #     echo "Creating a virtual environment in $VENV_DIR..."
    #     $PYTHON_BIN -m venv $VENV_DIR
    # else
    #     echo "Virtual environment already exists at $VENV_DIR."
    # fi

    # # Activate the virtual environment
    # echo "Activating the virtual environment..."
    # source "$VENV_DIR/bin/activate"

    # Upgrade pip to the latest version
    echo "Upgrading pip..."
    pip install --upgrade pip --break-system-packages

    # Install dependencies from requirements.txt
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt..."
        pip install -r requirements.txt --break-system-packages
    else
        echo "Error: requirements.txt not found."
        deactivate
        exit 1
    fi

    # # Deactivate the virtual environment
    # echo "Deactivating the virtual environment..."
    # deactivate

    # External Environment Management: Offer workaround for errors
    # if [ ! -z "$(pip list | grep externally-managed-environment)" ]; then
    #     echo "Notice: If you encounter the 'externally-managed-environment' error and wish to install directly, run:"
    #     echo "       pip install <package-name> --break-system-packages"
    #     echo "Or use the provided virtual environment for isolated package management."
    # fi


    # Now install the packages all this setup was for.
    # python3 -m pip install apprise 
    # python3 -m pip install psutil
    # sudo python3 -m pip install apprise
    # sudo python3 -m pip install psutil
fi

echo "Starting mongodb..."
sudo systemctl start mongod

echo ""
echo ""
echo "Creating folders..."
echo "${CURRENT_DIRECTORY}/public_html"
mkdir -p public_html/logs
echo "Setting ownership and permissions for apache..."
sudo chown -R :www-data ${CURRENT_DIRECTORY}/public_html
sudo chmod -R 755 "${CURRENT_DIRECTORY}/public_html"
echo "You may additionally need to add a+x permission to this directory and parent directories"
echo "so that apache can traverse the directory"



# # Add an apache virtual host
# echo ""
# echo ""
# echo "Enter the DNS name of the apache virtual host you want to create (e.g. streammon.local)"
# read -r DNS_NAME
# # examine the response in a case insensitive manner
# DNS_NAME=$(echo "$DNS_NAME" | tr '[:upper:]' '[:lower:]')
# echo "Creating apache virtual host..."
# echo ""
# echo ""
# echo "
# <VirtualHost *:80>
#     ServerAdmin webmaster@your_website_name.com
#     ServerName ${DNS_NAME}
#     ServerAlias www.${DNS_NAME}
#     DocumentRoot \"${CURRENT_DIRECTORY}/public_html\"
#     DirectoryIndex index.php index.html

#     <Directory \"${CURRENT_DIRECTORY}/public_html\">
#         AllowOverride all
#         Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
#         Require all granted
#     </Directory>

# </VirtualHost>" > ${DNS_NAME}.apache.conf
# sudo cp ${DNS_NAME}.apache.conf /etc/apache2/sites-available/${DNS_NAME}.conf

# # Enable the virtual host configuration and restart Apache
# sudo a2ensite ${DNS_NAME}.conf
# sudo systemctl restart apache2

# Configure nginx default site


read -r -p "Shall I generate a default host for nginx (Y/n) " do_nginx_default
# examine the response in a case insensitive manner
do_nginx_default=$(echo "$do_nginx_default" | tr '[:upper:]' '[:lower:]')
if [ "$do_nginx_default" = "n" ]; then
    echo "Skipping nginx default site configuration..."
else
    echo "Enter the DNS name of the nginx virtual host you want to create (e.g. streammon.local)"
    read -r DNS_NAME
    # examine the response in a case insensitive manner
    DNS_NAME=$(echo "$DNS_NAME" | tr '[:upper:]' '[:lower:')

    sudo tee /etc/nginx/sites-available/default > /dev/null <<EOF
    server {
        listen 80;
        server_name ${DNS_NAME};

        root ${CURRENT_DIRECTORY}/public_html;
        index index.html;

        location / {
            try_files \$uri /index.html;
        }

        # Proxy configuration for API requests
        location /protected {
            proxy_pass http://localhost:5000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host \$host;
            proxy_cache_bypass \$http_upgrade;
        }

        location /auth {
            proxy_pass http://localhost:5000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host \$host;
            proxy_cache_bypass \$http_upgrade;
        }

        # Log files for debugging
        error_log /var/log/nginx/error.log;
        access_log /var/log/nginx/access.log;
    }
EOF

    echo "Restarting nginx..."
    sudo systemctl restart nginx
fi
# End of nginx stuff



# # Install composer
# echo "Installing composer..."

# EXPECTED_CHECKSUM="$(php -r 'copy("https://composer.github.io/installer.sig", "php://stdout");')"
# php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
# ACTUAL_CHECKSUM="$(php -r "echo hash_file('sha384', 'composer-setup.php');")"

# if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]
# then
#     >&2 echo 'ERROR: Invalid installer checksum'
#     rm composer-setup.php
#     exit 1
# fi

# php composer-setup.php --quiet
# RESULT=$?
# rm composer-setup.php

# # If the exit code is 1, then the installation failed
# if [ $RESULT -ne 0 ]; then
#     echo "Composer installation failed.  Aborting..."
#     exit 1
# else
#     echo "Composer installation succeeded."
# fi


# # Install mongodb extension
# echo ""
# echo ""
# echo "Installing mongodb extension..."
# sudo pecl install mongodb

# # Add the mongodb extension to php.ini files
# # Determine the current php.ini file in use (cli)
# PHP_INI_FILE="$(php -i | grep 'Loaded Configuration File' | awk '{print $5}')"
# echo "Detected PHP ini file: $PHP_INI_FILE"
# echo "Analyzing PHP ini file: $PHP_INI_FILE"
# # Scan the php.ini file for the mongodb extension and add it if it doesn't exist
# if grep -q "extension=mongodb.so" "$PHP_INI_FILE"; then
#     echo "mongodb extension already exists in php.ini file"
# else
#     echo "mongodb extension does not exist in php.ini file.  Adding..."
#     echo "extension=mongodb.so" | sudo tee -a "$PHP_INI_FILE"    
# fi

# # Determine the current php.ini file in use (apache2)
# # If it contains the text 'cli', replace it with apache2 assume that is the path to the apache php.ini file
# PHP_INI_FILE="$(php -i | grep 'Loaded Configuration File' | awk '{print $5}' | sed 's/cli/apache2/')"
# echo "Analyzing PHP ini file: $PHP_INI_FILE"
# # Scan the php.ini file for the mongodb extension and add it if it doesn't exist
# if grep -q "extension=mongodb.so" "$PHP_INI_FILE"; then
#     echo "mongodb extension already exists in php.ini file"
# else
#     echo "mongodb extension does not exist in php.ini file.  Adding..."
#     echo "extension=mongodb.so" | sudo tee -a "$PHP_INI_FILE"    
# fi

# echo "Do you want to (re)install the mongodb library driver? (Y/n)"
# read -r INSTALL_MONGODB_LIBRARY
# # examine the response in a case insensitive manner
# INSTALL_MONGODB_LIBRARY=$(echo "$INSTALL_MONGODB_LIBRARY" | tr '[:upper:]' '[:lower:]')
# if [ "$INSTALL_MONGODB_LIBRARY" != "n" ]; then
#     echo "Installing mongodb library..."
#     "${CURRENT_DIRECTORY}/composer.phar" require mongodb/mongodb --ignore-platform-reqs
#     "${CURRENT_DIRECTORY}/composer.phar" require jenssegers/mongodb --ignore-platform-reqs
# else
#     echo "Skipping mongodb library installation..."
# fi

echo ""
echo ""
echo "Enter the MongoDB connection string (default: mongodb://localhost:27017/?authSource=admin&readPreference=primary&ssl=false)"
echo "or Press ENTER to accept default:\n"
read -r MONGO_CONNECTION_STRING
# examine the response in a case insensitive manner
MONGO_CONNECTION_STRING=$(echo "$MONGO_CONNECTION_STRING" | tr '[:upper:]' '[:lower:]')
if [ -z "$MONGO_CONNECTION_STRING" ]; then
    MONGO_CONNECTION_STRING="mongodb://localhost:27017/?authSource=admin&readPreference=primary&ssl=false"
fi

echo "Enter the MongoDB database name (default: streammon)"
echo "or Press ENTER to accept default:\n"
read -r MONGO_DATABASE_NAME
# examine the response in a case insensitive manner
MONGO_DATABASE_NAME=$(echo "$MONGO_DATABASE_NAME" | tr '[:upper:]' '[:lower:]')
# If the user response has no alphanumeric characters, or contains only an enter, use the default
if [ -z "$MONGO_DATABASE_NAME" ]; then
    echo "Using default database name: streammon"
    MONGO_DATABASE_NAME="streammon"
else 
    echo "Using user-provided database name: $MONGO_DATABASE_NAME"
fi

echo ""
echo ""
echo "Do you want to load initial database data? (Y/n) "
echo "WARNING: This will overwrite any existing data in the database and reset user login to the default"
read -r LOAD_INITIAL_DATA
# examine the response in a case insensitive manner
LOAD_INITIAL_DATA=$(echo "$LOAD_INITIAL_DATA" | tr '[:upper:]' '[:lower:]')
if [ "$LOAD_INITIAL_DATA" != "n" ]; then
    echo "Loading initial database data..."    
    echo "Command: mongorestore --db ${MONGO_DATABASE_NAME}  \"${CURRENT_DIRECTORY}/mongodb_init/streammon/\""
    mongorestore --db ${MONGO_DATABASE_NAME}  "${CURRENT_DIRECTORY}/mongodb_init/streammon/"
    
else

    echo "Skipping initial database data load..."
fi

# Run schema updater
echo "Running schema updater..."
python3 schema_updater.py

# Create an inital config.py file
# if there is already a config.py file, ask if the user wants to overwrite it
echo ""
echo ""
if [ -f "config.py" ]; then
    echo "A config.py file already exists.  Do you want to overwrite it? (Y/n)"
    read -r OVERWRITE_CONFIG
    # examine the response in a case insensitive manner
    OVERWRITE_CONFIG=$(echo "$OVERWRITE_CONFIG" | tr '[:upper:]' '[:lower:]')
    if [ "$OVERWRITE_CONFIG" != "n" ]; then
        echo "Creating config.py file..."

        echo "# Automatically generated by install.sh" > config.py
        echo "MONGO_CONNECTION_STRING = \"$MONGO_CONNECTION_STRING\"" >> config.py
        echo "MONGO_DATABASE_NAME = \"$MONGO_DATABASE_NAME\"" >> config.py
        echo "OPERATING_DIRECTORY = \"$CURRENT_DIRECTORY\"" >> config.py
        echo "USER = \"$CURRENT_USERNAME\"" >> config.py
        echo "ALERTS_DISABLED = 0" >> config.py
        echo "STREAMDOWN_ALERTS_DISABLED = 0" >> config.py
    else
        echo "Skipping config.py file generation..."
    fi
else
    echo "Creating config.py file..."

    echo "# Automatically generated by install.sh" > config.py
    echo "MONGO_CONNECTION_STRING = \"$MONGO_CONNECTION_STRING\"" >> config.py
    echo "MONGO_DATABASE_NAME = \"$MONGO_DATABASE_NAME\"" >> config.py
    echo "OPERATING_DIRECTORY = \"$CURRENT_DIRECTORY\"" >> config.py
    echo "USER = \"$CURRENT_USERNAME\"" >> config.py
fi


echo "Installing nodejs and dependencies..."
# Constants
SERVICE_NAME="streammon-api"
APP_DIR="$CURRENT_DIRECTORY/StreamMonitor_Express_API" # Replace with the actual path

echo "Express API..."

# Install Node.js
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs


echo "Installing npm dependencies..."
cd "$APP_DIR" || { echo "Error: Directory $APP_DIR not found."; exit 1; }
npm install




# Generate a systemd service unit the SUPERVISOR based on the current directory and user
# Clear out any existing file
echo "" > streammon_supervisor.service
echo "Generating systemd service unit for SUPERVISOR..."
echo "[Unit]" > streammon_supervisor.service
echo "Description=Stream Monitor Supervisor" >> streammon_supervisor.service
echo "After=multi-user.target" >> streammon_supervisor.service
echo "[Service]" >> streammon_supervisor.service
echo "Type=simple" >> streammon_supervisor.service
echo "User=$CURRENT_USERNAME" >> streammon_supervisor.service
echo "Group=$CURRENT_GROUPNAME" >> streammon_supervisor.service
echo "Restart=always" >> streammon_supervisor.service
echo "WorkingDirectory=$CURRENT_DIRECTORY" >> streammon_supervisor.service
echo "ExecStart=/usr/bin/python3 \"$CURRENT_DIRECTORY/streammon_supervisor.py\"" >> streammon_supervisor.service
echo "[Install]" >> streammon_supervisor.service
echo "WantedBy=multi-user.target" >> streammon_supervisor.service


echo "Do you want to install the SUPERVISOR systemd service unit and enable it? (Y/n)"
read -r INSTALL_SYSTEMD
# examine the response in a case insensitive manner
INSTALL_SYSTEMD=$(echo "$INSTALL_SYSTEMD" | tr '[:upper:]' '[:lower:]')
if [ "$INSTALL_SYSTEMD" != "n" ]; then
    echo "Installing systemd service unit..."
    sudo cp streammon_supervisor.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable streammon_supervisor.service
    sudo systemctl start streammon_supervisor.service
else
    echo "Skipping systemd service unit installation..."
fi



# Generate a systemd service unit the API based on the current directory and user
# Clear out any existing file
echo "" > streammon_api.service
echo "[Unit]" >> streammon_api.service
echo "Description=StreamMonitor Express API" >> streammon_api.service
echo "After=network.target" >> streammon_api.service
echo "" >> streammon_api.service
echo "[Service]" >> streammon_api.service
echo "Environment=NODE_ENV=production" >> streammon_api.service
echo "WorkingDirectory=$APP_DIR" >> streammon_api.service
echo "ExecStart=/usr/bin/npm exec npm run start" >> streammon_api.service
echo "Restart=always" >> streammon_api.service
echo "User=$CURRENT_USERNAME" >> streammon_api.service
echo "Group=$CURRENT_GROUPNAME" >> streammon_api.service
echo "StandardOutput=inherit" >> streammon_api.service
echo "StandardError=inherit" >> streammon_api.service
echo "SyslogIdentifier=streammon-api" >> streammon_api.service
echo "" >> streammon_api.service
echo "[Install]" >> streammon_api.service
echo "WantedBy=multi-user.target" >> streammon_api.service




echo "Do you want to install the API systemd service unit and enable it? (Y/n)"
read -r INSTALL_SYSTEMD
# examine the response in a case insensitive manner
INSTALL_SYSTEMD=$(echo "$INSTALL_SYSTEMD" | tr '[:upper:]' '[:lower:]')
if [ "$INSTALL_SYSTEMD" != "n" ]; then
    echo "Installing systemd service unit..."
    sudo cp streammon_api.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable streammon_api.service
    sudo systemctl start streammon_api.service
else
    echo "Skipping API systemd service unit installation..."
fi


echo ""
echo ""
echo "Done!"

echo "You should be able to access the Stream Monitor Supervisor at"
echo "http://${DNS_NAME}/"
 
