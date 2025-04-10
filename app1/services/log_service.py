from app.utils.db import clickhouse_query

def get_logs(date=None):
    query = "SELECT * FROM logs"
    if date:
        query += f" WHERE toDate(timestamp) = toDate('{date}')"
    return clickhouse_query(query)
