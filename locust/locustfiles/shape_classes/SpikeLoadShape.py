from locust import LoadTestShape
import math

class SpikeLoadShape(LoadTestShape):
    """
    A custom load shape that provides a gradual ramp-up, sustained peak load,
    and then a gradual ramp-down.
    """
    initial_baseline_users = 20 # Users during the initial low period
    initial_baseline_spawn_rate = 2 # Spawn rate during the initial low period

    peak_users = 300
    spike_spawn_rate = 50

    spike_duration = 10
    
    # Time before spike starts. This is effectively the duration of the initial baseline.
    pre_spike_duration = 20 
    
    # Time after spike ends, for the post-spike baseline.
    post_spike_duration = 40 
    post_spike_baseline_users = 20 # Users during the post-spike low period
    post_spike_baseline_spawn_rate = 50 # Spawn rate during the post-spike low period

    # Calculated start and end times for the spike based on pre_spike_duration
    spike_start_time = pre_spike_duration
    spike_end_time = pre_spike_duration + spike_duration

    def tick(self):
        run_time = self.get_run_time() # Get the total time the test has been running
        
        # Phase 1: Initial Baseline
        if run_time < self.spike_start_time:
            return (self.initial_baseline_users, self.initial_baseline_spawn_rate)
        
        # Phase 2: Spike
        elif run_time >= self.spike_start_time and run_time < self.spike_end_time:
            return (self.peak_users, self.spike_spawn_rate)
        
        # Phase 3: Post-Spike Baseline
        elif run_time >= self.spike_end_time and run_time < self.spike_end_time + self.post_spike_duration:
            return (self.post_spike_baseline_users, self.post_spike_baseline_spawn_rate)
        
        # Phase 4: Test End
        else:
            return None