from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import datetime
from db.clickhouse_client import client  # Подключение к ClickHouse

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API работает!"}

@app.post("/upload/")
async def upload_log(file: UploadFile = File(...)):
    contents = await file.read()
    text = contents.decode('utf-8')

    rows = []
    for line in text.splitlines():
        # Пример парсинга строки лога
        parts = line.split()
        if len(parts) < 9:
            continue
        
        ip = parts[0]
        method = parts[5].strip('"')
        url = parts[6]
        status = parts[8]
        timestamp = datetime.datetime.strptime(parts[3][1:], "%d/%b/%Y:%H:%M:%S")

        # Добавляем строку в список для вставки
        rows.append({
            'ip': ip,
            'method': method,
            'url': url,
            'status': status,
            'user_agent': "user_agent",  # Заменить на реальный парсинг User-Agent
            'timestamp': timestamp
        })

    # Вставка в таблицу ClickHouse
    client.insert('logs', rows)  # 'logs' — название таблицы в ClickHouse

    return JSONResponse(content={"filename": file.filename, "status": "uploaded", "inserted_rows": len(rows)})
