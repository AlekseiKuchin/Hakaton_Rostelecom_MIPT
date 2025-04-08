from datetime import datetime
import os
import sys
from flask import Flask, send_file
from io import BytesIO, TextIOWrapper
from clickhouse_driver import Client
#import pyarrow.parquet as pq
import re

# Config from ENV
CHDB_HOST = os.getenv('CHDB_HOST', 'localhost')
CHDB_PORT = os.getenv('CHDB_PORT', '9000')
CHDB_DATABASE = os.getenv('CHDB_DATABASE', 'logger')
CHDB_USER = os.getenv('CHDB_USER', 'test')
CHDB_PASSWORD = os.getenv('CHDB_PASSWORD', 'test')

# Connect to DB

client = Client(host=CHDB_HOST,
                port=CHDB_PORT,
                database=CHDB_DATABASE,
                user=CHDB_USER,
                password=CHDB_PASSWORD,
                client_name='logger-server',
                settings={'use_numpy': False, 'insert_block_size': 1000}) # do not set use_numpy=True

# Apache2 logs parser

apache2_regex = re.compile(
    r'^(?P<ip>\S+)\s-\s-\s\[(?P<timestamp>[^\]]+)\]\s'
    r'"(?P<method>\S+)\s(?P<path>\S+)\s(?P<protocol>[^"]+)"\s'
    r'(?P<status>\d+)\s'
    r'(?P<bytes_sent>\d+)\s'
    r'"(?P<referrer>[^"]*)"\s'
    r'"(?P<user_agent>[^"]*)"\s'
    r'(?P<response_time>\d+)$'
)

def apache2_parse_log(text: TextIOWrapper):
    line_i = 0
    for line in text:
        def parse_datetime(dt_string):
            dt_string = dt_string.replace("+0300", "").strip()
            return datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
        line_i += 1
        if line_i % 100000 == 0:
            print(f"Checkpoint: line {line_i}...")
        match = apache2_regex.match(line)
        if match:
            log_data = match.groupdict()
            log_data['bytes_sent'] = int(log_data['bytes_sent']) if log_data['bytes_sent'].isdigit() else 0
            log_data['status'] = int(log_data['status'])
            log_data['response_time'] = int(log_data['response_time'])
            log_data['timestamp'] = parse_datetime(log_data['timestamp'])
            yield log_data


# Main app
if __name__ == "__main__":
    # run import
    if len(sys.argv) > 1:
        import_file = sys.argv[1]
    else:
        print("Please provide a file to import.")
        exit(1)
    if not os.path.isfile(import_file):
        print(f"File {import_file} is not a file.")
        exit(2)
    print("Importing...")
    with open(import_file, 'r') as file:
        # Insert parsed logs into ClickHouse
        client.execute(
            query='INSERT INTO apache_logs VALUES',
            params=apache2_parse_log(file)
        )
    print("Import completed. To start web-server, please use WGSI.")
    print("For example, running dev-server: `python -m flask --app logger run`.")
    exit(0)
else:
    # Wil will start web-server now
    pass


# Now web-server code starts
app = Flask(__name__)

@app.route('/')
def root():
    return app.send_static_file('index.html')

@app.route('/test')
def test():
    def return_data():
        d = client.execute_iter(
        'SELECT * FROM apache_logs LIMIT 100')
        for row in d:
            yield str(f"{row[0]} {row[1]}\n")
    return return_data(), {"Content-Type": "text/csv"}

@app.route('/export_parquet')
def export_parquet():
    buffer = BytesIO()
    buffer.write(b'Just some letters.')
    # Or you can encode it to bytes.
    # buffer.write('Just some letters.'.encode('utf-8'))
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name='a_file.txt',
        mimetype='text/csv'
    )