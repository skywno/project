from locust import LoadTestShape

# Define your Custom Load Test Shape
class GradualRampUpDownShape(LoadTestShape):
    """
    A custom load shape that provides a gradual ramp-up, sustained peak load,
    and then a gradual ramp-down.
    """

    # Define the stages of your load test
    # Each dictionary represents a stage with its duration, target users, and spawn rate.
    stages = [

        # Gradual Ramp-up phases
        {"duration": 30, "users": 50, "spawn_rate": 2, "name": "Ramp Up to 50 Users"},
        {"duration": 30, "users": 100, "spawn_rate": 2, "name": "Ramp Up to 100 Users"},
        {"duration": 30, "users": 150, "spawn_rate": 2, "name": "Ramp Up to 150 Users"},

        # Sustained Peak Load phase: Hold the maximum desired load for a period
        {"duration": 60, "users": 200, "spawn_rate": 5, "name": "Sustained Peak (200 users)"},

        # Gradual Ramp-down phases
        {"duration": 30, "users": 150, "spawn_rate": 2, "name": "Ramp Down to 150 Users"},
        {"duration": 30, "users": 100, "spawn_rate": 2, "name": "Ramp Down to 100 Users"},
        {"duration": 30, "users": 50, "spawn_rate": 2, "name": "Ramp Down to 50 Users"},

        # Final cool-down/clearance phase: Bring users down to zero
        {"duration": 30, "users": 0, "spawn_rate": 1, "name": "Cool-down (0 users)"},
    ]

    def tick(self):
        run_time = self.get_run_time() # Get the total time the test has been running
        
        # Iterate through the defined stages
        for stage in self.stages:
            # Check if the current run_time falls within the current stage's duration
            if run_time < stage["duration"]:
                # If it does, return the target users and spawn rate for this stage
                # This directly applies the settings for the current stage.
                current_users = stage["users"]
                current_spawn_rate = stage["spawn_rate"]
                
                print(f"Time: {int(run_time)}s, Stage: {stage['name']}, Target Users: {current_users}, Spawn Rate: {current_spawn_rate}")
                return (current_users, current_spawn_rate)
            else:
                # If the run_time is beyond the current stage's duration,
                # subtract the stage's duration and move to evaluate the next stage.
                run_time -= stage["duration"]

        # If all stages have completed (run_time is greater than the total duration of all stages)
        # return None to signal Locust to stop the test.
        return None
