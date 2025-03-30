from clickhouse_driver import Client

if __name__ == "__main__":
    # run import
    print("Import completed. To start web-server, please use WGSI.")
    print("For example, running dev-server: `python -m flask --app logger run`.")
    exit(0)
else:
    # Wil will start web-server now
    pass

# Now web-server code starts

from flask import Flask
from settings import *

app = Flask(__name__)


# Config DB connection
client = Client(host=CHDB_HOST,
                port=CHDB_PORT,
                database=CHDB_DATABASE,
                user=CHDB_USER,
                password=CHDB_PASSWORD,
                client_name='logger-server',
                settings={'use_numpy': True})

@app.route('/')
def root():
    return app.send_static_file('index.html')

@app.route('/test')
def test():
    return str(client.execute(
        'SELECT * FROM system.numbers LIMIT 10000',
        columnar=True))
