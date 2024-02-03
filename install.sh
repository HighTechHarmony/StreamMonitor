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
if [ "$response" != "y" ]; then
    echo "Aborting..."
    exit 1
fi

echo "Configuring timezone..."
sudo dpkg-reconfigure tzdata

# Do you want to automatically install dependencies?
read -r -p "Do you want me to try to automatically install dependencies? (Y/n) " install_dependencies_auto
if [ "$install_dependencies_auto" = "n" ]; then
    echo "Skipping automatic dependency installation..."
else
echo "Installing dependencies..."
    sudo apt-get install python3 python3-pip python-is-python3 gnupg curl php \
        software-properties-common gnupg apt-transport-https ca-certificates \
        git nano iputils-ping ffmpeg zip unzip php-zip python-pymongo python3-pil\
        php-mbstring php-dev php-pear composer \
        -y

    curl -fsSL https://pgp.mongodb.com/server-7.0.asc |  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse
    sudo apt update
    sudo apt install mongodb-org -y

    # Install python dependencies for the normal user and for root
    python3 -m pip install apprise
    python3 -m pip install psutil
    sudo python3 -m pip install apprise
    sudo python3 -m pip install psutil
fi

echo ""
echo ""
echo "Creating folders..."
echo "${CURRENT_DIRECTORY}/public_html"
mkdir -p public_html/logs
echo "Setting ownership and permissions..."
# sudo chown -R www-data:www-data ${CURRENT_DIRECTORY}/public_html
sudo chmod -R 755 "${CURRENT_DIRECTORY}/public_html"



# Add an apache virtual host
echo ""
echo ""
echo "Enter the DNS name of the apache virtual host you want to create (e.g. streammon.local)"
read -r DNS_NAME
echo "Creating apache virtual host..."
echo ""
echo ""
echo "
<VirtualHost *:80>
    ServerAdmin webmaster@your_website_name.com
    ServerName ${DNS_NAME}
    ServerAlias www.${DNS_NAME}
    DocumentRoot \"${CURRENT_DIRECTORY}/public_html\"
    DirectoryIndex index.php index.html

    <Directory \"${CURRENT_DIRECTORY}/public_html\">
        AllowOverride all
        Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
        Require all granted
    </Directory>

</VirtualHost>" > ${DNS_NAME}.apache.conf
sudo cp ${DNS_NAME}.apache.conf /etc/apache2/sites-available/${DNS_NAME}.conf

# Enable the virtual host configuration and restart Apache
sudo a2ensite ${DNS_NAME}.conf
sudo systemctl restart apache2




# Install composer
echo "Installing composer..."
echo ""
echo ""

EXPECTED_CHECKSUM="$(php -r 'copy("https://composer.github.io/installer.sig", "php://stdout");')"
php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
ACTUAL_CHECKSUM="$(php -r "echo hash_file('sha384', 'composer-setup.php');")"

if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]
then
    >&2 echo 'ERROR: Invalid installer checksum'
    rm composer-setup.php
    exit 1
fi

php composer-setup.php --quiet
RESULT=$?
rm composer-setup.php

# If the exit code is 1, then the installation failed
if [ $RESULT -ne 0 ]; then
    echo "Composer installation failed.  Aborting..."
    exit 1
else
    echo "Composer installation succeeded."
fi

# Install mongodb extension
echo "Installing mongodb extension..."
sudo pecl install mongodb

# Add the mongodb extension to php.ini files
# Determine the current php.ini file in use (cli)
PHP_INI_FILE="$(php -i | grep 'Loaded Configuration File' | awk '{print $5}')"
echo "Detected PHP ini file: $PHP_INI_FILE"
echo "Analyzing PHP ini file: $PHP_INI_FILE"
# Scan the php.ini file for the mongodb extension and add it if it doesn't exist
if grep -q "extension=mongodb.so" "$PHP_INI_FILE"; then
    echo "mongodb extension already exists in php.ini file"
else
    echo "mongodb extension does not exist in php.ini file.  Adding..."
    echo "extension=mongodb.so" | sudo tee -a "$PHP_INI_FILE"    
fi

# Determine the current php.ini file in use (apache2)
# If it contains the text 'cli', replace it with apache2 assume that is the path to the apache php.ini file
PHP_INI_FILE="$(php -i | grep 'Loaded Configuration File' | awk '{print $5}' | sed 's/cli/apache2/')"
echo "Analyzing PHP ini file: $PHP_INI_FILE"
# Scan the php.ini file for the mongodb extension and add it if it doesn't exist
if grep -q "extension=mongodb.so" "$PHP_INI_FILE"; then
    echo "mongodb extension already exists in php.ini file"
else
    echo "mongodb extension does not exist in php.ini file.  Adding..."
    echo "extension=mongodb.so" | sudo tee -a "$PHP_INI_FILE"    
fi


# Install mongodb library
"${CURRENT_DIRECTORY}/composer.phar" require mongodb/mongodb --ignore-platform-reqs
"${CURRENT_DIRECTORY}/composer.phar" require jenssegers/mongodb --ignore-platform-reqs

echo "Enter the MongoDB connection string (default: mongodb://localhost:27017/?authSource=admin&readPreference=primary&ssl=false)"
echo "or Press ENTER to accept default:\n"
read -r MONGO_CONNECTION_STRING
if [ -z "$MONGO_CONNECTION_STRING" ]; then
    MONGO_CONNECTION_STRING="mongodb://localhost:27017/?authSource=admin&readPreference=primary&ssl=false"
fi


echo "Do you want to load initial database data? (y/N) "
echo "WARNING: This will overwrite any existing data in the database and reset user login to the default"
read -r LOAD_INITIAL_DATA
if [ "$LOAD_INITIAL_DATA" = "y" ]; then
    echo "Loading initial database data..."
    mongoimport --db $MONGO_DATABASE_NAME --file "${CURRENT_DIRECTORY}/mongodb_init"
    MONGO_DATABASE_NAME="streammon"
else

    echo "Skipping initial database data load..."
    echo "Enter the MongoDB database name (default: streammon)"
    echo "or Press ENTER to accept default:\n"
    read -r MONGO_DATABASE_NAME
    if [ -z "$MONGO_DATABASE_NAME" ]; then
        MONGO_DATABASE_NAME="streammon"
    fi
fi

# Create an inital config.py file
# if there is already a config.py file, ask if the user wants to overwrite it
if [ -f "config.py" ]; then
    echo "A config.py file already exists.  Do you want to overwrite it? (y/N)"
    read -r OVERWRITE_CONFIG
    if [ "$OVERWRITE_CONFIG" = "y" ]; then
        echo "Creating config.py file..."

        echo "# Automatically generated by install.sh" > config.py
        echo "MONGO_CONNECTION_STRING = \"$MONGO_CONNECTION_STRING\"" >> config.py
        echo "MONGO_DATABASE_NAME = \"$MONGO_DATABASE_NAME\"" >> config.py
        echo "OPERATING_DIRECTORY = \"$CURRENT_DIRECTORY\"" >> config.py
        echo "USER = \"$CURRENT_USERNAME\"" >> config.py
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


# Generate a systemd service unit based on the current directory and user
echo "Generating systemd service unit..."
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

echo "Do you want to install the systemd service unit and enable it? (y/N)"
read -r INSTALL_SYSTEMD
if [ "$INSTALL_SYSTEMD" = "y" ]; then
    echo "Installing systemd service unit..."
    sudo cp streammon_supervisor.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable streammon_supervisor.service
    sudo systemctl start streammon_supervisor.service
else
    echo "Skipping systemd service unit installation..."
fi

echo "Restarting apache2..."
sudo systemctl restart apache2

echo ""
echo ""
echo "Done!  Please note that if this is your first name-based virtual host, you"
echo "may also need to disable the default virtual host by running "
echo "'sudo a2dissite 000-default.conf' and restarting apache"

echo "Otherwise, you should be able to access the Stream Monitor Supervisor at"
echo "http://${DNS_NAME}/"
 
