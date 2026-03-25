class PIDController:
    def __init__(self, kp: float, ki: float, kd: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.previous_error = 0.0
        self.integral = 0.0
        self.output_min = -10.0
        self.output_max = 10.0

    def update(self, setpoint: float, measurement: float, dt: float) -> float:
        if dt <= 0:
            raise ValueError("dt must be greater than 0")

        error = setpoint - measurement
        self.integral += self.ki * error * dt
        self.integral = max(min(self.integral, self.output_max), self.output_min)  # anti-windup
        derivative = (error - self.previous_error) / dt

        output = (self.kp * error) + self.integral + (self.kd * derivative)
        output = max(min(output, self.output_max), self.output_min)  # output clamp

        self.previous_error = error
        return output
