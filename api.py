from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API работает!"}

@app.post("/upload/")
async def upload_log(file: UploadFile = File(...)):
    contents = await file.read()
    
    # Тут будет парсинг и сохранение в БД — добавлю позже
    print(contents[:100])  # Печатаем первые 100 логов для проверки

    return JSONResponse(content={"filename": file.filename, "status": "uploaded"})
