from clickhouse_driver import Client

client = Client(host="localhost")  # или из config

def clickhouse_query(query):
    return client.execute(query, with_column_types=True)
