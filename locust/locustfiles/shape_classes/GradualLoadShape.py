from locust import LoadTestShape
from math import ceil
# Define your Custom Load Test Shape
class GradualRampUpDownShape(LoadTestShape):
    """
    A custom load shape that provides a gradual ramp-up, sustained peak load,
    and then a gradual ramp-down.
    """
    initial_users = 0
    peak_users = 500
    ramp_up_duration = 150    
    peak_duration = 30
    ramp_down_duration = 150
    spawn_rate = ceil(peak_users / ramp_up_duration)
    end_users = 0

    def tick(self):
        run_time = self.get_run_time() # Get the total time the test has been running
        
        if run_time <= self.ramp_up_duration:
            return (self.peak_users, self.spawn_rate)
        elif run_time <= self.ramp_up_duration + self.peak_duration:
            return (self.peak_users, self.peak_users) # Sustained peak load
        elif run_time <= self.ramp_up_duration + self.peak_duration + self.ramp_down_duration:
            # Gradual ramp-down
            elapsed_ramp_down_time = run_time - self.ramp_up_duration - self.peak_duration
            user_count = max(self.end_users, self.peak_users - int(elapsed_ramp_down_time * self.spawn_rate))
            return (user_count, -self.spawn_rate)
        else:
            return None
