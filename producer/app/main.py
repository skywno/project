from fastapi import FastAPI, BackgroundTasks
from app.send import RabbitMQProducer
import asyncio

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

sending_message = False
message_task = None
producer = RabbitMQProducer()

async def send_message_task():
    while sending_message:
        producer.send_message("Hello World!")
        # print("Hello World!")
        await asyncio.sleep(1)  # Changed to 60 seconds for 1 minute interval

@app.post("/start_sending")
async def start_sending(background_tasks: BackgroundTasks):
    global sending_message, message_task
    sending_message = True
    message_task = asyncio.create_task(send_message_task())
    return {"message": "Sending messages..."}

@app.post("/stop_sending")
async def stop_sending():
    global sending_message, message_task
    sending_message = False
    if message_task:
        message_task.cancel()
        message_task = None
    producer.close()
    return {"message": "Stopped sending messages"}