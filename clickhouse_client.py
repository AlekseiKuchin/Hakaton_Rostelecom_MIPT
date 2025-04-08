import clickhouse_connect

client = clickhouse_connect.get_client(
    host='root@77.95.201.152',        # или IP сервера ClickHouse
    port=18123,
    username='default',
    password='1234',
    database=''  
)
