import serial
import re
import csv
import time
from datetime import datetime
import os # Added for checking directory

# Configuration
SERIAL_PORT = '/dev/ttyUSB0'  # This will be the path inside the container
BAUD_RATE = 115200
OUTPUT_CSV_DIR = '/data' # Directory for the CSV
OUTPUT_CSV_FILE = os.path.join(OUTPUT_CSV_DIR, 'temperature_log.csv')

# Regex to match temperature lines (adjust if your sensor output format is different)
TEMP_REGEX = re.compile(
    r"Sensor '(.+?)' \(GPIO \d+\): Temperature = ([\d.-]+) C"
)

def main():
    print(f"Serial Logger: Attempting to connect to serial port {SERIAL_PORT} at {BAUD_RATE} baud...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Serial Logger: Successfully connected to {SERIAL_PORT}.")
    except serial.SerialException as e:
        print(f"Serial Logger: Error: Could not open serial port {SERIAL_PORT}: {e}")
        print("Serial Logger: Please ensure the device is passed through to the container and permissions are correct.")
        return  # Exit if connection fails

    # Ensure the /data directory exists (it should be a mount point)
    if not os.path.exists(OUTPUT_CSV_DIR):
        print(f"Serial Logger: Error: Output directory {OUTPUT_CSV_DIR} does not exist. Ensure it's mounted as a volume.")
        try:
            print(f"Serial Logger: Attempting to create {OUTPUT_CSV_DIR}...")
            os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
            print(f"Serial Logger: Successfully created {OUTPUT_CSV_DIR} or it already existed.")
        except Exception as e_dir:
            print(f"Serial Logger: Failed to create {OUTPUT_CSV_DIR}: {e_dir}")
            ser.close()
            return


    print(f"Serial Logger: Logging temperatures to {OUTPUT_CSV_FILE}. Press Ctrl+C to stop this container/script.")
    try:
        # Open in append mode, create if not exists
        with open(OUTPUT_CSV_FILE, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header only if the file is new/empty
            if csvfile.tell() == 0:
                writer.writerow(['timestamp', 'sensor', 'temperature'])
                csvfile.flush() # Ensure header is written immediately
                print(f"Serial Logger: CSV header written to {OUTPUT_CSV_FILE}")

            while True:
                try:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                except serial.SerialException as e:
                    print(f"Serial Logger: Serial read error: {e}. Attempting to reconnect or continue...")
                    # Optional: add logic to attempt re-opening the port
                    time.sleep(5) # Wait before retrying
                    continue # Skip to next iteration
                except Exception as e_read:
                    print(f"Serial Logger: Unexpected error reading line: {e_read}")
                    time.sleep(1)
                    continue


                if not line:
                    # print("Serial Logger: No data from serial (timeout).") # Can be noisy
                    continue # Skip empty lines (e.g., from timeout)

                match = TEMP_REGEX.search(line)
                if match:
                    timestamp = datetime.now().isoformat()
                    sensor_name = match.group(1).strip()
                    try:
                        temperature = float(match.group(2))
                        writer.writerow([timestamp, sensor_name, temperature])
                        csvfile.flush()  # Ensure data is written to disk regularly
                        print(f"Serial Logger: Logged - {timestamp} - Sensor: {sensor_name}, Temperature: {temperature}°C")
                    except ValueError:
                        print(f"Serial Logger: Warning: Could not parse temperature from '{match.group(2)}' in line: {line}")
                elif line: # If line is not empty and not a match (and not just a timeout)
                    print(f"Serial Logger: Received non-matching data: {line}")


    except KeyboardInterrupt:
        print("\nSerial Logger: Logging stopped by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"Serial Logger: An unexpected error occurred: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print(f"Serial Logger: Serial port {SERIAL_PORT} closed.")
        print("Serial Logger: Exiting logger script.")

if __name__ == '__main__':
    main()
