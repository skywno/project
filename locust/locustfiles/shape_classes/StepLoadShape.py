from locust import LoadTestShape
import math

class StepLoadShape(LoadTestShape):
    """
    A step load shape with increment and decrement phases


    Keyword arguments:

        step_time -- Time between steps
        step_load -- User increase amount at each step
        spawn_rate -- Users to stop/start per second at every step
        time_limit -- Time limit in seconds
        peak_time -- Time to start decrementing (if None, only increment)
        decrement_steps -- Number of steps to decrement (if None, decrement to 0)

    """

    step_time = 30
    step_load = 10
    spawn_rate = 10
    time_limit = 300
    peak_time = 150  # Time to start decrementing
    decrement_steps = None  # If None, decrement to 0

    def tick(self):
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        # Calculate current step
        current_step = math.floor(run_time / self.step_time) + 1
        
        # Increment phase
        if run_time < self.peak_time:
            return (current_step * self.step_load, self.spawn_rate)
        
        # Decrement phase
        else:
            # Calculate how much time has passed since peak
            time_since_peak = run_time - self.peak_time
            decrement_step = math.floor(time_since_peak / self.step_time) + 1
            
            # Calculate peak load
            peak_step = math.floor(self.peak_time / self.step_time) + 1
            peak_load = peak_step * self.step_load
            
            # Calculate decrement amount
            if self.decrement_steps is None:
                # Decrement to 0
                decrement_amount = decrement_step * self.step_load
            else:
                # Decrement by specified number of steps
                decrement_amount = min(decrement_step * self.step_load, 
                                     peak_load * (decrement_step / self.decrement_steps))
            
            # Calculate current load
            current_load = max(0, peak_load - decrement_amount)
            
            return (current_load, self.spawn_rate)