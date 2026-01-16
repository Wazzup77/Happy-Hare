
import timeit

class Reactor:
    def monotonic(self): return 0

class MockRunoutHelper:
    def __init__(self):
        self.filament_present = False
        self.button_handler = None
        self.button_handler_suspended = False
        self.reactor = Reactor()

    def note_filament_present(self, *args):
        # Simulate the overhead of argument parsing and basic checks
        if len(args) == 1:
            eventtime = self.reactor.monotonic()
            is_filament_present = args[0]
        else:
            eventtime = args[0]
            is_filament_present = args[1]

        if self.button_handler and not self.button_handler_suspended:
             pass 

        if is_filament_present == self.filament_present: return
        self.filament_present = is_filament_present

# ------------------------------------------------------------------
# Old Implementation (Integer Math + Unconditional Call)
# ------------------------------------------------------------------
class OldSensor:
    def __init__(self):
        self.runout_helper = MockRunoutHelper()
        self.last_reading = 0
        self.last_reading2 = 0
        self.a_min = 5000  # Threshold (0.5 * 10000)
        self.lastReadTime = 0
        self.present = False
        self._homing = False
        self._triggered = False
        self._trigger_completion = None
        self.lastTriggerTime = 0

    def adc_callback(self, read_time, read_value):
        self.last_reading = round(read_value * 10000)
        self._check_trigger(read_time)
        self.lastReadTime = read_time

    def _check_trigger(self, eventtime):
        self.present = (self.last_reading + self.last_reading2) > self.a_min
        self.runout_helper.note_filament_present(eventtime, self.present)
        
        if self.present == True:
            self.lastTriggerTime = eventtime
        
        if self._homing:
            if self.present == self._triggered:
                if self._trigger_completion is not None:
                    self._last_trigger_time = eventtime
                    # self._trigger_completion.complete(True) # Mocked out
                    self._trigger_completion = None

# ------------------------------------------------------------------
# New Implementation (Float Math + Conditional Call)
# ------------------------------------------------------------------
class NewSensor:
    def __init__(self):
        self.runout_helper = MockRunoutHelper()
        self._val1 = 0.
        self._val2 = 0.
        self._trigger_threshold = 0.5 # Threshold (0.5)
        self.lastReadTime = 0
        self.present = False
        self._homing = False
        self._triggered = False
        self._trigger_completion = None
        self.lastTriggerTime = 0

    def adc_callback(self, read_time, read_value):
        self._val1 = read_value
        self._check_trigger(read_time)
        self.lastReadTime = read_time

    def _check_trigger(self, eventtime):
        self.present = (self._val1 + self._val2) > self._trigger_threshold
        if self.runout_helper.button_handler or self.present != self.runout_helper.filament_present:
            self.runout_helper.note_filament_present(eventtime, self.present)

        if self.present:
            self.lastTriggerTime = eventtime
        
        if self._homing:
            if self.present == self._triggered:
                if self._trigger_completion is not None:
                    self._last_trigger_time = eventtime
                    # self._trigger_completion.complete(True) # Mocked out
                    self._trigger_completion = None


old_sensor = OldSensor()
new_sensor = NewSensor()

# Scenario: Steady state (filament not present)
# Input values that result in total < threshold
read_val = 0.2
old_sensor.last_reading2 = 2000 # 0.2 * 10000
new_sensor._val2 = 0.2

# Ensure runout helper matches state so we test the "skip" path in new version
old_sensor.runout_helper.filament_present = False
new_sensor.runout_helper.filament_present = False

n = 1_000_000

def run_old():
    old_sensor.adc_callback(123.456, read_val)

def run_new():
    new_sensor.adc_callback(123.456, read_val)

t_old = timeit.timeit(run_old, number=n)
t_new = timeit.timeit(run_new, number=n)

print(f"Full Chain Benchmark ({n} iterations)")
print("-" * 30)
print(f"Old (Int Math + Always Call): {t_old:.4f}s")
print(f"New (Float Math + Skip Call): {t_new:.4f}s")
print(f"Speedup: {t_old / t_new:.2f}x")
print(f"Time saved: {(t_old - t_new) / n * 1e6:.2f} µs per call")
