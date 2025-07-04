from locust import LoadTestShape

class MultiSpikeVolatileShape(LoadTestShape):
    """
    A custom load shape for a volatile pattern with multiple predefined spikes
    and varying baseline loads.

    Define your phases in the 'stages' list as dictionaries:
    {'duration': int (seconds), 'users': int, 'spawn_rate': int}
    """

    # Example Stages:
    # - Start with 30 users for 10 seconds
    # - Spike to 300 users quickly (100 spawn rate) for 30 seconds
    # - Drop to 20 users for 20 seconds
    # - Another big spike to 1000 users (100 spawn rate) for 15 seconds
    # - Drop to 5 users for 50 seconds
    # - Final medium spike to 400 users for 30 seconds
    # - Ramp down to 0
    stages = [
            {"duration": 10, "users": 30, "spawn_rate": 3},
            {"duration": 5, "users": 200, "spawn_rate": 100}, # Spike 1 - Fast ramp up
            {"duration": 20, "users": 20, "spawn_rate": 100}, # Drop 1 - Increased spawn_rate for faster drop
            {"duration": 5, "users": 300, "spawn_rate": 100}, # Spike 2 - Fast ramp up
            {"duration": 40, "users": 5, "spawn_rate": 100}, # Drop 2 - Very high spawn_rate for quick drop
            {"duration": 5, "users": 400, "spawn_rate": 100}, # Spike 3 - Fast ramp up
            {"duration": 10, "users": 1, "spawn_rate": 200}, # Final ramp down - Very high spawn_rate to kill users quickly
    ]

    def tick(self):
        run_time = self.get_run_time()
        
        total_duration_so_far = 0
        
        for stage in self.stages:
            stage_duration = stage["duration"]
            
            # Check if current run_time falls within this stage
            if run_time <= total_duration_so_far + stage_duration:
                # Calculate the percentage into this specific stage
                elapsed_in_stage = run_time - total_duration_so_far
                
                # Dynamic user calculation for smooth transitions within a stage (optional, but good for gradual phases)
                # For sharp spikes, you'd just return stage["users"] directly
                
                # If you want instantaneous jumps at stage start, just use:
                # return (stage["users"], stage["spawn_rate"])

                # If you want a smooth transition *within* each stage (e.g., from 10 to 150 users)
                # this would make the spikes less "sudden". For true spikes, stick to the commented line above.
                
                # Let's go with the instantaneous jump for "sudden spikes" as requested.
                # However, ensure the spawn rate is appropriate to reach the target quickly.
                
                return (stage["users"], stage["spawn_rate"])
                
            total_duration_so_far += stage_duration
            
        # If run_time exceeds total duration of all stages, stop the test
        return None
