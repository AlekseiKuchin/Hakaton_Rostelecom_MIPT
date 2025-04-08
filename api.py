from fastapi import FastApi

app = FastAPI()

@app.get("/")
def read_root():

