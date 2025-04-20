import itertools
import os
import sys
from flask import Flask, request, Response
import io
from clickhouse_driver import Client
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import plotly
import plotly.express as px
import json
import datetime
import logging

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

def apache2_parse_log(text: io.TextIOWrapper):
    line_i = 0
    for line in text:
        def parse_datetime(dt_string):
            dt_string = dt_string.replace("+0300", "").strip()
            return datetime.datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
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


def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """
    Lets you use an iterable (e.g. a generator) that yields bytestrings as a read-only
    input stream.

    The stream implements Python 3's newer I/O API (available in Python 2's io module).
    For efficiency, the stream is buffered.
    """
    class IterStream(io.RawIOBase):
        def __init__(self):
            self.leftover = None
        def readable(self):
            return True
        def readinto(self, b):
            try:
                l = len(b)  # We're supposed to return at most this much
                chunk = self.leftover or next(iterable)
                output, self.leftover = chunk[:l], chunk[l:]
                b[:len(output)] = output
                return len(output)
            except StopIteration:
                return 0    # indicate EOF
    return io.BufferedReader(IterStream(), buffer_size=buffer_size)

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
    print(f"Import (local) started on {datetime.datetime.now()}...")
    with open(import_file, 'r') as file:
        # Insert parsed logs into ClickHouse
        client.execute(
            query='INSERT INTO apache_logs VALUES',
            params=apache2_parse_log(file)
        )
    print(f"Import (local) completed on {datetime.datetime.now()}. To start web-server, please use WGSI.")
    print("For example, running dev-server: `python -m flask --app logger run`.")
    exit(0)
else:
    # Wil will start web-server now
    pass

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Now web-server code starts
app = Flask(__name__)

@app.route('/')
def root():
    return app.send_static_file('index.html')

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.route('/api/import/apache_log', methods=['POST'])
def import_apache_log():
    try:
        print(f"Import (web) started on {datetime.datetime.now()}...")
        def get_stream_bytes():
            bytes_left = int(request.headers.get('content-length'))
            chunk_size = 5120
            while bytes_left > 0:
                chunk = request.stream.read(chunk_size)
                bytes_left -= len(chunk)
                yield chunk
        stream = io.TextIOWrapper(iterable_to_stream(get_stream_bytes()))
        client.execute(
                query='INSERT INTO apache_logs VALUES',
                params=apache2_parse_log(stream)
            )
        res = json.dumps({"status": "success"})
        print(f"Import (web) completed on {datetime.datetime.now()}.")
    except Exception as e:
        logging.critical(f"Import (web) failed on {datetime.datetime.now()}!")
        raise e
    return Response(response=res, status=200, mimetype="application/json")

@app.route('/api/db/count_rows', methods=['GET'])
def count_rows():
    answ = client.execute("SELECT count() FROM apache_logs")
    res = json.dumps({"rows": int(answ[0][0])})
    return Response(response=res, status=200, mimetype="application/json")

@app.route('/api/export/csv/<int:limit>', methods=['GET'])
def export_csv(limit: int):
    def return_data():
        if limit == 0:
            sql_req = 'SELECT * FROM apache_logs'
        else:
            sql_req =  f'SELECT * FROM apache_logs LIMIT {limit}'
        rows = client.execute_iter(sql_req)
        for row in rows:
            yield ", ".join([str(i) for i in row ])+"\n"
    resp = Response(response=return_data(), content_type="text/csv")
    resp.headers['Content-Disposition']='attachment; filename="export.csv"'
    return resp

@app.route('/api/export/parquet/<int:limit>')
def export_parquet(limit: int):
    def return_data():
        rows = client.execute_iter(f'SELECT * FROM apache_logs LIMIT {limit}')
        batches = parquet_get_batches(rows_iterable=rows, chunk_size=50, schema=parquet_logs_schema)
        buffer = io.BytesIO()
        with pq.ParquetWriter(buffer, schema=parquet_logs_schema, compression='zstd') as writer:
            for batch in batches:
                buffer.flush()
                writer.write_batch(batch)
                buffer.seek(0)
                yield buffer.read()
            buffer.flush()
        buffer.seek(0)
        yield buffer.read()
    resp = Response(response=return_data(), content_type="application/vnd.apache.parquet")
    resp.headers['Content-Disposition']='attachment; filename="export.parquet"'
    return resp

@app.route('/api/graph_show/graph1')
def graph1_show():
    df = client.query_dataframe('SELECT timestamp, response_time FROM apache_logs LIMIT 10')
    fig = px.line(df, x="timestamp", y="response_time", title='Timestamp to response_time')
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return Response(response=graphJSON, status=200, mimetype="application/json")
