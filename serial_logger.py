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
        # Initialize serial connection with a timeout
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Serial Logger: Successfully connected to {SERIAL_PORT}.")

        # Flush input and output buffers after successful connection
        if ser.is_open:
            ser.flushInput()  # Discard data received but not read
            ser.flushOutput() # Discard data written but not transmitted
            print("Serial Logger: Flushed input and output buffers.")

    except serial.SerialException as e:
        print(f"Serial Logger: Error: Could not open serial port {SERIAL_PORT}: {e}")
        print("Serial Logger: Please ensure the device is passed through to the container and permissions are correct.")
        return  # Exit if connection fails
    except Exception as e_init:
        print(f"Serial Logger: An unexpected error occurred during serial initialization: {e_init}")
        return


    # Ensure the /data directory exists (it should be a mount point)
    if not os.path.exists(OUTPUT_CSV_DIR):
        print(f"Serial Logger: Warning: Output directory {OUTPUT_CSV_DIR} does not exist. This should be a mounted volume.")
        # Attempting to create it might hide a misconfiguration, but can be useful for some local tests.
        # For TrueNAS, this directory MUST be a mount point from the host.
        try:
            print(f"Serial Logger: Attempting to create {OUTPUT_CSV_DIR} for robustness...")
            os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
            print(f"Serial Logger: Directory {OUTPUT_CSV_DIR} check/creation step complete.")
        except Exception as e_dir:
            print(f"Serial Logger: Failed to create {OUTPUT_CSV_DIR}: {e_dir}. CSV writing will likely fail.")
            # Decide if you want to return or try to continue if dir creation fails.
            # For this app, if /data can't be accessed, logging will fail.
            if 'ser' in locals() and ser.is_open:
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
                raw_bytes_received = b'' # Initialize to empty bytes
                try:
                    raw_bytes_received = ser.readline() # Read raw bytes, uses the timeout from Serial init
                except serial.SerialException as e_read_serial:
                    print(f"Serial Logger: Serial read error: {e_read_serial}. Will attempt to continue...")
                    time.sleep(5) # Wait before retrying to avoid spamming logs if port is gone
                    # You might want to try re-opening the port here if it's a persistent issue
                    continue
                except Exception as e_read_other:
                    print(f"Serial Logger: Unexpected error during ser.readline(): {e_read_other}")
                    time.sleep(1)
                    continue

                if raw_bytes_received:
                    # *** THIS IS THE ADDED DEBUGGING LINE ***
                    print(f"Serial Logger: RAW BYTES RECEIVED: {raw_bytes_received!r}") # !r shows the repr (e.g., b'hello\r\n')

                    try:
                        # Decode after confirming some bytes were received
                        line = raw_bytes_received.decode('utf-8', errors='replace').strip()
                    except UnicodeDecodeError as e_decode:
                        print(f"Serial Logger: UnicodeDecodeError for raw bytes {raw_bytes_received!r}. Error: {e_decode}")
                        continue # Skip this line

                    if not line: # If line becomes empty after strip (e.g. just whitespace or control chars)
                        # print("Serial Logger: Line became empty after decode and strip.")
                        continue

                    # print(f"Serial Logger: Decoded Line for Regex: '{line}'") # Optional: for seeing what regex is testing

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
                            print(f"Serial Logger: Warning: Could not parse temperature float from '{match.group(2)}' in line: {line}")
                    elif line: # If line is not empty and not a match
                        print(f"Serial Logger: Received non-matching data (after decode): '{line}'")
                else:
                    # This will be hit if ser.readline() times out (returns empty bytes b'')
                    # print("Serial Logger: No data from serial (timeout).") # Can be very noisy, enable if needed
                    pass

    except KeyboardInterrupt:
        print("\nSerial Logger: Logging stopped by user (KeyboardInterrupt).")
    except IOError as e_io:
        print(f"Serial Logger: IOError (e.g. problem writing to CSV at {OUTPUT_CSV_FILE}): {e_io}")
    except Exception as e_main_loop:
        print(f"Serial Logger: An unexpected error occurred in the main loop: {e_main_loop}", exc_info=True)
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print(f"Serial Logger: Serial port {SERIAL_PORT} closed.")
        print("Serial Logger: Exiting logger script.")

if __name__ == '__main__':
    main()
