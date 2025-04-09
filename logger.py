from datetime import datetime
import itertools
import os
import sys
from flask import Flask, send_file, Response
from io import BytesIO, TextIOWrapper
from clickhouse_driver import Client
#import pyarrow.parquet as pq
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# For parquet export
parquet_logs_schema = pa.schema([
    ('ip', pa.string()),
    ('timestamp', pa.date32()),
    ('method', pa.string()),
    ('path', pa.string()),
    ('protocol', pa.string()),
    ('status', pa.int32()),
    ('bytes_sent', pa.int32()),
    ('referrer', pa.string()),
    ('user_agent', pa.string()),
    ('response_time', pa.int32()),
])

# Python 3.11 or lesser does not have itertools.batched (https://stackoverflow.com/a/8998040)
def batched_it(iterable, n):
    "Batch data into iterators of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while True:
        chunk_it = itertools.islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield itertools.chain((first_el,), chunk_it)

# Chunk the rows into arrow batches (https://stackoverflow.com/a/73771478)
def parquet_get_batches(rows_iterable, chunk_size, schema):
    for it in batched_it(rows_iterable, chunk_size):
        pad = pd.DataFrame(it, columns=schema.names)
        yield pa.RecordBatch.from_pandas(pad, schema=schema, preserve_index=False)

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
    return Response(response=return_data(), content_type="text/csv")

@app.route('/export_parquet')
def export_parquet():
    def return_data():
        rows = client.execute_iter('SELECT * FROM apache_logs LIMIT 30000')
        batches = parquet_get_batches(rows_iterable=rows, chunk_size=50, schema=parquet_logs_schema)
        buffer = BytesIO()
        with pq.ParquetWriter(buffer, schema=parquet_logs_schema, compression='zstd') as writer:
            for batch in batches:
                buffer.flush()
                writer.write_batch(batch)
                buffer.seek(0)
                yield buffer.read()
            buffer.flush()
        buffer.seek(0)
        yield buffer.read()
    return Response(response=return_data(), content_type="application/vnd.apache.parquet")
