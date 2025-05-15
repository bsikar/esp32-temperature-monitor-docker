from flask import Flask, jsonify, render_template, request
import csv
import os
from datetime import datetime, timedelta

app = Flask(__name__) # Templates are expected in a 'templates' subdirectory

CSV_FILE_DIR = '/data' # Directory for the CSV
CSV_FILE = os.path.join(CSV_FILE_DIR, 'temperature_log.csv')


def parse_iso_timestamp(ts_str):
    """Safely parse ISO format timestamp string."""
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        app.logger.warning(f"Could not parse timestamp string: {ts_str}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    timespan_str = request.args.get('timespan', '24h')  # Default to last 24 hours
    app.logger.info(f"Data request received for timespan: {timespan_str}")

    sensors_data = {} # Store data as {sensor_name: {'timestamps': [], 'temps': []}}

    if not os.path.exists(CSV_FILE):
        app.logger.error(f"Data file '{CSV_FILE}' not found.")
        return jsonify({'error': f"Data file '{CSV_FILE}' not found. Is the logger running and writing data?"}), 404

    now = datetime.now()
    filter_start_time = None

    if timespan_str == '1h':
        filter_start_time = now - timedelta(hours=1)
    elif timespan_str == '6h':
        filter_start_time = now - timedelta(hours=6)
    elif timespan_str == '24h':
        filter_start_time = now - timedelta(days=1)
    elif timespan_str == '7d':
        filter_start_time = now - timedelta(days=7)
    elif timespan_str == '30d':
        filter_start_time = now - timedelta(days=30)
    elif timespan_str == 'all':
        filter_start_time = None  # No start time filter, load all data
    else:
        app.logger.warning(f"Unrecognized timespan '{timespan_str}', defaulting to 24h.")
        timespan_str = '24h' # For status message consistency
        filter_start_time = now - timedelta(days=1)
    
    app.logger.info(f"Filter start time for data: {filter_start_time}")

    all_rows_from_csv = []
    try:
        with open(CSV_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                app.logger.warning(f"CSV file '{CSV_FILE}' is empty or header is missing.")
                return jsonify({'message': f"No data to display. The log file '{CSV_FILE}' might be empty or missing headers."}), 200
            for row in reader:
                all_rows_from_csv.append(row)
    except FileNotFoundError: # Should be caught by os.path.exists, but good practice
        app.logger.error(f"Data file '{CSV_FILE}' disappeared or could not be opened during read.")
        return jsonify({'error': f"Data file '{CSV_FILE}' disappeared or could not be opened."}), 404
    except Exception as e_read_csv:
        app.logger.error(f"Error reading CSV file '{CSV_FILE}': {e_read_csv}", exc_info=True)
        return jsonify({'error': f"An unexpected error occurred while reading data: {str(e_read_csv)}"}), 500

    if not all_rows_from_csv:
        app.logger.info(f"No rows found in CSV file '{CSV_FILE}' after reading.")
        return jsonify({'message': f"No data logged yet in '{CSV_FILE}' for timespan: {timespan_str}."}), 200

    # Filter rows based on timestamp
    for row in all_rows_from_csv:
        try:
            timestamp_str = row['timestamp']
            temperature_str = row['temperature']
            sensor = row['sensor']

            # Basic validation
            if not all([timestamp_str, temperature_str, sensor]):
                app.logger.warning(f"Skipping row with missing data: {row}")
                continue
            
            temperature = float(temperature_str) # Can raise ValueError

            timestamp_obj = parse_iso_timestamp(timestamp_str)
            if not timestamp_obj:
                app.logger.warning(f"Skipping row with unparseable timestamp_str: '{timestamp_str}' in row: {row}")
                continue

            if filter_start_time and timestamp_obj < filter_start_time:
                continue  # Data is older than the filter window

            if sensor not in sensors_data:
                sensors_data[sensor] = {'timestamps': [], 'temps': []}
            
            sensors_data[sensor]['timestamps'].append(timestamp_str) # Send as string
            sensors_data[sensor]['temps'].append(temperature)

        except KeyError as e_key:
            app.logger.warning(f"Skipping row due to missing key: {e_key}. Expected 'timestamp', 'sensor', 'temperature'. Row: {row}")
            continue
        except ValueError as e_val: # Catch float conversion error
            app.logger.warning(f"Skipping row due to value error (e.g., non-float temp '{temperature_str}'): {e_val}. Row: {row}")
            continue
    
    # Optional: Limit the number of points for 'all' to prevent browser overload
    MAX_POINTS_FOR_ALL_TIMESPAN = 5000
    if timespan_str == 'all':
        for sensor_name in list(sensors_data.keys()): # Iterate over a copy of keys if modifying dict
            if len(sensors_data[sensor_name]['timestamps']) > MAX_POINTS_FOR_ALL_TIMESPAN:
                app.logger.info(f"Limiting data points for sensor '{sensor_name}' in 'all' view to last {MAX_POINTS_FOR_ALL_TIMESPAN}.")
                sensors_data[sensor_name]['timestamps'] = sensors_data[sensor_name]['timestamps'][-MAX_POINTS_FOR_ALL_TIMESPAN:]
                sensors_data[sensor_name]['temps'] = sensors_data[sensor_name]['temps'][-MAX_POINTS_FOR_ALL_TIMESPAN:]

    if not any(s_data.get('timestamps') for s_data in sensors_data.values()):
        app.logger.info(f"No data found for any sensor for the selected timespan: {timespan_str}.")
        return jsonify({'message': f"No data found for the selected timespan: {timespan_str}."}), 200
    
    app.logger.info(f"Processed {sum(len(s['timestamps']) for s in sensors_data.values())} data points for {len(sensors_data)} sensors for timespan {timespan_str}.")
    return jsonify(sensors_data)

if __name__ == '__main__':
    # When run directly (not through a production WSGI server like Gunicorn)
    # Host 0.0.0.0 makes it accessible on the network
    # Debug=True is useful for development but should be False in production
    # The Dockerfile/run.sh will handle running this.
    # If you were running this script directly outside docker, you'd use:
    # app.run(host='0.0.0.0', port=5000, debug=False)
    # But since run.sh calls `python3 /app/app.py`, Flask's default is host 127.0.0.1 and port 5000.
    # To make it accessible from outside the container, it MUST listen on 0.0.0.0.
    # So, the CMD in Dockerfile implicitly runs it. For Flask to listen on 0.0.0.0
    # when just `python app.py` is run, we must specify it in app.run().
    # However, production deployments often use Gunicorn or uWSGI.
    # For simplicity with `python app.py` in `run.sh`:
    app.run(host='0.0.0.0', port=5000, debug=False) # Set debug=False for container deployment
