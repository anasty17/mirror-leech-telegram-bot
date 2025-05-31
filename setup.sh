#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Clone the repository
echo "Cloning the repository..."
git clone https://github.com/AarKro/email-organizer.git
cd email-organizer

# Install Docker and Docker Compose
echo "Installing Docker and Docker Compose..."
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements-cli.txt

# Create config.py from config_sample.py
echo "Creating config.py from config_sample.py..."
cp config_sample.py config.py

# Print instructions for the user
echo "--------------------------------------------------------------------------------"
echo "Setup script finished. Please complete the following manual steps:"
echo "--------------------------------------------------------------------------------"
echo "1. Fill in the required fields in config.py:"
echo "   - MONGO_URI: Your MongoDB connection string"
echo "   - RCLONE_REMOTE_NAME: Your rclone remote name (e.g., 'gdrive')"
echo ""
echo "2. Set up Google OAuth API credentials and place token.pickle in the root directory:"
echo "   - Follow the instructions at: https://developers.google.com/gmail/api/quickstart/python"
echo "   - Make sure to download 'credentials.json' and rename it to 'client_secret.json'."
echo "   - Run 'python -m email_organizer.auth' to generate 'token.pickle'."
echo ""
echo "3. Generate rclone.conf:"
echo "   - Run 'rclone config' and follow the prompts to configure your cloud storage."
echo "   - Ensure the rclone.conf file is placed in the '.config/rclone/' directory in your home folder, or linked appropriately."
echo ""
echo "4. Create a MongoDB database:"
echo "   - Ensure your MongoDB instance is running and accessible."
echo "   - The database and collections will be created automatically when the application runs for the first time if they don't exist."
echo ""
echo "Once these steps are completed, you can run the application."
echo "--------------------------------------------------------------------------------"

cd ..
