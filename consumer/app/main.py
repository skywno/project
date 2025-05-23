from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get('/health')
async def check_health():
    return {"status": 200, "service_type": "RAG"}