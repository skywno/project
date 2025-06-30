from locust import LoadTestShape

# Define your Custom Load Test Shape
class ConstantMediumLoadShape(LoadTestShape):
    """
    A custom load shape that provides a constant medium load,
    """
    user_count = 500
    duration = 300
    spawn_rate = 50

    def tick(self):
        run_time = self.get_run_time() # Get the total time the test has been running
        
        if run_time < self.duration:
            return (self.user_count, self.spawn_rate)
        else:
            return None
