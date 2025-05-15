#!/bin/bash

echo "Starting serial logger..."
# Start the serial logger in the background
# The 'python3 -u' makes the output unbuffered, which is good for logging in containers
python3 -u /app/serial_logger.py &

# Add a small delay (optional, but can sometimes help ensure logger starts cleanly)
sleep 2

echo "Starting Flask web server on host 0.0.0.0 port 5000..."
# Start the Flask web server in the foreground
# Host 0.0.0.0 makes it accessible from outside the container (if port is mapped)
python3 -u /app/app.py
