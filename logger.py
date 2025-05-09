import itertools
import os
import sys
import time
from flask import Flask, request, Response, send_file
import tempfile
import io
import clickhouse_driver
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
import datetime
import logging
import shutil

tmp_files = []

# Logging setup
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

def batched_it(iterable, n):
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

def parquet_get_batches(rows_iterable, chunk_size, schema):
    for it in batched_it(rows_iterable, chunk_size):
        pad = pd.DataFrame(it, columns=schema.names)
        yield pa.RecordBatch.from_pandas(pad, schema=schema, preserve_index=False)

def default_lines_stream_limit():
    usage_info = shutil.disk_usage(tempfile.gettempdir())
    available_disk = usage_info.free - 1024 * 1024
    logger.info("Env LINES_STREAM_LIMIT is not set. Setting default one.")
    if available_disk <= 0:
        logger.warning("Available system RAM is too small. Setting LINES_STREAM_LIMIT=1000.")
        return 1000
    else:
        rows_limit = available_disk // 20
        logger.info(f"Setting LINES_STREAM_LIMIT={rows_limit}")
        return rows_limit

# Config from ENV
CHDB_HOST = os.getenv('CHDB_HOST', 'localhost')
CHDB_PORT = os.getenv('CHDB_PORT', '9000')
CHDB_DATABASE = os.getenv('CHDB_DATABASE', 'logger')
CHDB_USER = os.getenv('CHDB_USER', 'test')
CHDB_PASSWORD = os.getenv('CHDB_PASSWORD', 'test')
LINES_STREAM_LIMIT = int(os.getenv('LINES_STREAM_LIMIT', default_lines_stream_limit()))

db_connection = clickhouse_driver.dbapi.Connection(
    host=CHDB_HOST,
    port=CHDB_PORT,
    database=CHDB_DATABASE,
    user=CHDB_USER,
    password=CHDB_PASSWORD,
    client_name='logger-server-async',
    settings={'use_numpy': False, 'insert_block_size': 1000}
)

def create_empty_graph(message="Нет данных для отображения", font_color='#34495e'):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=20, color=font_color),
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=40, r=40, t=20, b=40),
    )
    return fig

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
    class IterStream(io.RawIOBase):
        def __init__(self):
            self.leftover = None
        def readable(self):
            return True
        def readinto(self, b):
            try:
                l = len(b)
                chunk = self.leftover or next(iterable)
                output, self.leftover = chunk[:l], chunk[l:]
                b[:len(output)] = output
                return len(output)
            except StopIteration:
                return 0
    return io.BufferedReader(IterStream(), buffer_size=buffer_size)

def get_db_size():
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT count() FROM apache_logs")
        count = cursor.fetchall()[0][0]
        cursor.execute("SELECT formatReadableSize(sum(bytes)), sum(bytes) FROM system.parts WHERE active AND table = 'apache_logs'")
        size_human, size = cursor.fetchall()[0]
        return count, size, size_human

def print_db_size():
    count, _, size_human = get_db_size()
    logger.info(f"Current db status: {count} lines, {size_human} size.")

def tmp_del_after():
    if len(tmp_files):
        tmp = tmp_files[-1]
        os.unlink(tmp.name)
        tmp_files.remove(tmp)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        import_file = sys.argv[1]
    else:
        print("Please provide a file to import.")
        exit(1)
    if not os.path.isfile(import_file):
        print(f"File {import_file} is not a file.")
        exit(2)
    print_db_size()
    logger.info(f"Import (local) started on {datetime.datetime.now()}...")
    with open(import_file, 'r') as file:
        with db_connection.cursor() as cursor:
            cursor.execute(
                operation='INSERT INTO apache_logs VALUES',
                parameters=apache2_parse_log(file)
            )
    print(f"Import (local) completed on {datetime.datetime.now()}.")
    print_db_size()
    print("To start web-server, please use WGSI. For example, running dev-server: `python -m flask --app logger run`.")
    exit(0)

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
        count, _, _ = get_db_size()
        print_db_size()
        logging.info(f"Import (web) started on {datetime.datetime.now()}...")
        def get_stream_bytes():
            bytes_left = int(request.headers.get('content-length'))
            chunk_size = 5120
            while bytes_left > 0:
                chunk = request.stream.read(chunk_size)
                bytes_left -= len(chunk)
                yield chunk
        stream = io.TextIOWrapper(iterable_to_stream(get_stream_bytes()))
        with db_connection.cursor() as cursor:
            cursor.execute(
                operation='INSERT INTO apache_logs VALUES',
                parameters=apache2_parse_log(stream)
            )
        new_count = count
        while new_count == count:
            time.sleep(0.5)
            new_count, _, _ = get_db_size()
        logging.info(f"Import (web) completed on {datetime.datetime.now()}.")
        print_db_size()
    except Exception as e:
        logging.critical(f"Import (web) failed on {datetime.datetime.now()}!")
        raise e
    resp = json.dumps({"status": "success"})
    return Response(response=resp, status=200, mimetype="application/json")

@app.route('/api/db/db_size', methods=['GET'])
def db_size_json():
    info = get_db_size()
    res = json.dumps({"count": info[0], "size": info[1], "size_human": info[2]})
    return Response(response=res, status=200, mimetype="application/json")

@app.route('/api/db/clean', methods=['POST'])
def db_clean():
    with db_connection.cursor() as cursor:
        cursor.execute("DELETE FROM apache_logs WHERE ip IS NOT NULL")
    resp = json.dumps({"status": "success"})
    return Response(response=resp, status=200, mimetype="application/json")

@app.route('/api/export/csv/<int:limit>', methods=['GET'])
def export_csv(limit: int):
    def return_data():
        if limit == 0:
            sql_req = 'SELECT * FROM apache_logs'
        else:
            sql_req = f'SELECT * FROM apache_logs LIMIT {limit}'
        with db_connection.cursor() as cursor:
            cursor.set_stream_results(True, 1000)
            cursor.execute(sql_req)
            for row in cursor:
                yield bytes(", ".join([str(i) for i in row]) + "\n", encoding="UTF-8")
    stream = iterable_to_stream(return_data())
    if limit and limit <= LINES_STREAM_LIMIT:
        tmp = tempfile.NamedTemporaryFile(delete_on_close=False)
        tmp.writelines(stream)
        tmp.close()
        tmp_files.append(tmp)
        resp = send_file(path_or_file=tmp.name, mimetype="text/csv", as_attachment=False, download_name="export.csv")
        resp.direct_passthrough = False
        resp.call_on_close(tmp_del_after)
    else:
        resp = Response(response=stream, content_type="text/csv")
        resp.headers['Content-Disposition'] = 'attachment; filename="export.csv"'
    return resp

@app.route('/api/export/parquet/<int:limit>')
def export_parquet(limit: int):
    def return_data():
        with db_connection.cursor() as cursor:
            if limit == 0:
                sql_req = 'SELECT * FROM apache_logs'
            else:
                sql_req = f'SELECT * FROM apache_logs LIMIT {limit}'
            cursor.set_stream_results(True, 1000)
            cursor.execute(sql_req)
            batches = parquet_get_batches(rows_iterable=cursor, chunk_size=50, schema=parquet_logs_schema)
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
    stream = iterable_to_stream(return_data())
    if limit and limit <= LINES_STREAM_LIMIT:
        tmp = tempfile.NamedTemporaryFile(delete_on_close=False)
        tmp.writelines(stream)
        tmp.close()
        tmp_files.append(tmp)
        resp = send_file(path_or_file=tmp.name, mimetype="application/vnd.apache.parquet", as_attachment=False, download_name="export.parquet")
        resp.direct_passthrough = False
        resp.call_on_close(tmp_del_after)
    else:
        resp = Response(response=stream, content_type="application/vnd.apache.parquet")
        resp.headers['Content-Disposition'] = 'attachment; filename="export.parquet"'
    return resp

@app.route('/api/db/get_date_range')
def get_date_range():
    with db_connection.cursor() as cursor:
        result = cursor._client.query_dataframe("SELECT MIN(timestamp), MAX(timestamp) FROM apache_logs")
        if result.empty:
            min_date = datetime.datetime.fromisoformat('2023-01-01').timestamp()
            max_date = datetime.datetime.fromisoformat('2023-01-01').timestamp()
        else:
            min_date = result.iloc[0, 0].timestamp()
            max_date = result.iloc[0, 1].timestamp()
        resp = json.dumps({"min_time": min_date, "max_time": max_date})
        return Response(response=resp, status=200, mimetype="application/json")

@app.route('/api/graph_show/graph1')
def graph1_show():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    with db_connection.cursor() as cursor:
        query = "SELECT toDate(timestamp) as date, COUNT(*) as total_requests FROM apache_logs WHERE 1=1"
        if start_time and end_time:
            start_date = datetime.datetime.fromtimestamp(int(start_time)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = datetime.datetime.fromtimestamp(int(end_time)).strftime("%Y-%m-%d %H:%M:%S")
            query += f" AND timestamp BETWEEN toDateTime('{start_date}') AND toDateTime('{end_date}')"
        query += " GROUP BY date ORDER BY date"
        df = cursor._client.query_dataframe(query)
        if df.empty:
            fig = create_empty_graph("Нет данных о запросах")
        else:
            fig = px.line(df, x='date', y='total_requests', title="График запросов", line_shape='linear')
            fig.update_layout(xaxis_title="Дата", yaxis_title="Запросы", showlegend=False)
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return Response(response=graphJSON, status=200, mimetype="application/json")

@app.route('/api/graph_show/graph2')
def graph2_show():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    with db_connection.cursor() as cursor:
        query = "SELECT toDate(timestamp) as date, COUNT(*) as total_failures FROM apache_logs WHERE status >= 400"
        if start_time and end_time:
            start_date = datetime.datetime.fromtimestamp(int(start_time)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = datetime.datetime.fromtimestamp(int(end_time)).strftime("%Y-%m-%d %H:%M:%S")
            query += f" AND timestamp BETWEEN toDateTime('{start_date}') AND toDateTime('{end_date}')"
        query += " GROUP BY date ORDER BY date"
        df = cursor._client.query_dataframe(query)
        if df.empty:
            fig = create_empty_graph("Нет данных об отказах")
        else:
            fig = px.line(df, x='date', y='total_failures', title="График отказов", line_shape='linear')
            fig.update_layout(xaxis_title="Дата", yaxis_title="Отказы", showlegend=False)
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return Response(response=graphJSON, status=200, mimetype="application/json")

@app.route('/api/graph_show/graph3')
def graph3_show():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    with db_connection.cursor() as cursor:
        query = "SELECT ip, COUNT(*) as request_count FROM apache_logs WHERE 1=1"
        if start_time and end_time:
            start_date = datetime.datetime.fromtimestamp(int(start_time)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = datetime.datetime.fromtimestamp(int(end_time)).strftime("%Y-%m-%d %H:%M:%S")
            query += f" AND timestamp BETWEEN toDateTime('{start_date}') AND toDateTime('{end_date}')"
        query += " GROUP BY ip ORDER BY request_count DESC LIMIT 10"
        df = cursor._client.query_dataframe(query)
        if df.empty:
            fig = create_empty_graph("Нет данных о топ-10 IP")
        else:
            fig = px.bar(df, x='ip', y='request_count', title="График топ-10 IP", text_auto=True)
            fig.update_layout(xaxis_title="IP", yaxis_title="Запросы", showlegend=False)
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return Response(response=graphJSON, status=200, mimetype="application/json")

@app.route('/api/graph_show/graph4')
def graph4_show():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    with db_connection.cursor() as cursor:
        query = """
        SELECT 
            CASE 
                WHEN status BETWEEN 200 AND 299 THEN '2xx (Успешные)'
                WHEN status BETWEEN 300 AND 399 THEN '3xx (Перенаправления)'
                WHEN status BETWEEN 400 AND 499 THEN '4xx (Клиентские ошибки)'
                WHEN status BETWEEN 500 AND 599 THEN '5xx (Серверные ошибки)'
                ELSE 'Другие'
            END as status_group,
            COUNT(*) as count
        FROM apache_logs
        WHERE 1=1
        """
        if start_time and end_time:
            start_date = datetime.datetime.fromtimestamp(int(start_time)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = datetime.datetime.fromtimestamp(int(end_time)).strftime("%Y-%m-%d %H:%M:%S")
            query += f" AND timestamp BETWEEN toDateTime('{start_date}') AND toDateTime('{end_date}')"
        query += " GROUP BY status_group"
        df = cursor._client.query_dataframe(query)
        if df.empty:
            fig = create_empty_graph("Нет данных о кодах состояния")
        else:
            fig = px.pie(df, names='status_group', values='count', title="Распределение кодов состояния")
            fig.update_traces(textinfo='percent+label')
            fig.update_layout(showlegend=True)
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return Response(response=graphJSON, status=200, mimetype="application/json")

@app.route('/api/graph_show/graph5')
def graph5_show():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    with db_connection.cursor() as cursor:
        query = """
        SELECT toDate(timestamp) as date, AVG(response_time) as avg_response_time
        FROM apache_logs
        WHERE 1=1
        """
        if start_time and end_time:
            start_date = datetime.datetime.fromtimestamp(int(start_time)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = datetime.datetime.fromtimestamp(int(end_time)).strftime("%Y-%m-%d %H:%M:%S")
            query += f" AND timestamp BETWEEN toDateTime('{start_date}') AND toDateTime('{end_date}')"
        query += " GROUP BY date ORDER BY date"
        df = cursor._client.query_dataframe(query)
        if df.empty:
            fig = create_empty_graph("Нет данных о времени ответа")
        else:
            fig = px.line(df, x='date', y='avg_response_time', title="Среднее время ответа по дням", line_shape='linear')
            fig.update_layout(xaxis_title="Дата", yaxis_title="Среднее время ответа (мс)", showlegend=False)
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return Response(response=graphJSON, status=200, mimetype="application/json")

@app.route('/api/graph_show/heatmap')
def graph_heatmap():
    with db_connection.cursor() as cursor:
        query = """
        SELECT 
            toDayOfWeek(timestamp) AS day_of_week,
            toHour(timestamp) AS hour,
            COUNT(*) AS request_count
        FROM apache_logs
        GROUP BY day_of_week, hour
        ORDER BY day_of_week, hour
        """
        df = cursor._client.query_dataframe(query)
        if df.empty:
            fig = create_empty_graph("Нет данных для тепловой карты")
        else:
            # Pivot: дни — строки, часы — столбцы
            df_pivot = df.pivot(index='day_of_week', columns='hour', values='request_count').fillna(0)
            # Переименуем дни недели в русские
            days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            fig = go.Figure(data=go.Heatmap(
                z=df_pivot.values,
                x=df_pivot.columns.astype(str),
                y=days,
                colorscale='YlGnBu'
            ))
            fig.update_layout(
                title="Тепловая карта запросов по дням и часам",
                xaxis_title="Час",
                yaxis_title="День недели",
                margin=dict(l=40, r=40, t=40, b=40),
            )
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return Response(response=graphJSON, status=200, mimetype="application/json")

@app.route('/api/details/ip/<ip>')
def ip_details(ip):
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    with db_connection.cursor() as cursor:
        query = """
        SELECT timestamp, method, path, status, bytes_sent, response_time
        FROM apache_logs
        WHERE ip = %s
        """
        if start_time and end_time:
            start_date = datetime.datetime.fromtimestamp(int(start_time)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = datetime.datetime.fromtimestamp(int(end_time)).strftime("%Y-%m-%d %H:%M:%S")
            query += f" AND timestamp BETWEEN toDateTime('{start_date}') AND toDateTime('{end_date}')"
        query += " ORDER BY timestamp DESC LIMIT 100"
        safe_ip = ip.strip()
        df = cursor._client.query_dataframe(query, parameters=[safe_ip])
        result = df.to_dict(orient='records')
    return Response(response=json.dumps(result), status=200, mimetype="application/json")
