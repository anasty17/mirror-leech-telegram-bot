# health_check.py
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/health')
def health_check():
    return "OK", 200

def start_health_check_server():
    # Run Flask app on port 6800 to match Koyeb's health check configuration
    app.run(host="0.0.0.0", port=6800)

# Start the server in a separate thread so it doesn't block the main bot process
if __name__ == "__main__":
    threading.Thread(target=start_health_check_server).start()
