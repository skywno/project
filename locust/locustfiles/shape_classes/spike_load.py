from locust import LoadTestShape
import math

class SpikeLoadShape(LoadTestShape):
    # Base configuration
    base_users = 10         # Number of users for the normal load
    base_spawn_rate = 5     # Spawn rate for the normal load
    
    # Spike configuration
    spike_users = 200       # Number of users during the spike
    spike_spawn_rate = 100  # Spawn rate for the spike (should be high to quickly reach spike_users)
    
    spike_start_time = 60   # Time (seconds) after which the spike should start
    spike_duration = 120    # Duration (seconds) of the spike

    # Overall test duration
    total_run_time = 300    # Total time (seconds) for the entire test

    def tick(self):
        run_time = self.get_run_time()

        if run_time > self.total_run_time:
            # Stop the test after total_run_time
            return None

        # Calculate spike end time
        spike_end_time = self.spike_start_time + self.spike_duration

        if self.spike_start_time <= run_time < spike_end_time:
            # During the spike
            print(f"Time: {run_time:.1f}s - SPIKE! Users: {self.spike_users}, Spawn Rate: {self.spike_spawn_rate}")
            return (self.spike_users, self.spike_spawn_rate)
        elif run_time < self.spike_start_time:
            # Before the spike (normal load ramp-up)
            # You can make this a ramp-up if needed, for simplicity it's constant here
            current_users = min(self.base_users, math.ceil(run_time * self.base_spawn_rate))
            print(f"Time: {run_time:.1f}s - Pre-spike. Users: {current_users}, Spawn Rate: {self.base_spawn_rate}")
            return (self.base_users, self.base_spawn_rate)
        else:
            # After the spike (return to normal or zero load)
            # Here we return to base users. You could also ramp down to 0, or just to base_users.
            # To ramp down after the spike, you'd need more complex logic.
            print(f"Time: {run_time:.1f}s - Post-spike. Users: {self.base_users}, Spawn Rate: {self.base_spawn_rate}")
            return (self.base_users, self.base_spawn_rate)
