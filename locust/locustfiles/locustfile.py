from locust import task, constant, FastHttpUser, between

class FastUser(FastHttpUser):
    wait_time = constant(0)  
    
    @task
    def fast_task(self):
        # prevent keep-alive
        self.client.client.clientpool.close()
        self.client.post("/task")


class MediumUser(FastHttpUser):
    wait_time = between(1, 5)

    @task
    def medium_task(self):
        # prevent keep-alive
        self.client.client.clientpool.close()
        self.client.post("/task")


class SlowUser(FastHttpUser):
    wait_time = between(5, 10)  
    
    @task
    def slow_task(self):
        # prevent keep-alive
        self.client.client.clientpool.close()
        self.client.post("/task")
