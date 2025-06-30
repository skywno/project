from locust import LoadTestShape

# Define your Custom Load Test Shape
class ConstantHighLoadShape(LoadTestShape):
    """
    A custom load shape that provides a constant high load,
    """
    user_count = 1000
    duration = 300
    spawn_rate = 5

    def tick(self):
        run_time = self.get_run_time() # Get the total time the test has been running
        
        if run_time < self.duration:
            return (self.user_count, self.spawn_rate)
        else:
            return None
