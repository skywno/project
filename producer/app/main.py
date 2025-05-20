from fastapi import FastAPI, BackgroundTasks
from app.send import RabbitMQProducer
import asyncio
import json

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

sending_message = False
message_task = None
producer = RabbitMQProducer()

async def send_message_task():
    message_count = 0
    while sending_message:
        message = create_message_payload(message_count)
        print(message)
        producer.send_message(message)
        message_count += 1
        await asyncio.sleep(1)


def create_message_payload(ticket_id):
    data = {
        "ticket_id": ticket_id,
        "user_id": "some user_id",
        "group_id": "some group id",
        "target_type": "RAG",
        "task": "do something"
    }

    return json.dumps(data)

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