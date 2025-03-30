from flask import Flask
from clickhouse_driver import Client
from settings import *


# Connect to DB

client = Client(host=CHDB_HOST,
                port=CHDB_PORT,
                database=CHDB_DATABASE,
                user=CHDB_USER,
                password=CHDB_PASSWORD,
                client_name='logger-server',
                settings={'use_numpy': True})

if __name__ == "__main__":
    # run import
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
        'SELECT * FROM system.numbers LIMIT 10000')
        for row in d:
            yield str(f"{row[0]}\n")
    return return_data(), {"Content-Type": "text/csv"}
