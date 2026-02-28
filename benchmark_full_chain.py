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
        # Simulate the overhead of argument parsing and basic checks inside note_filament_present
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
        # Below would be the rest of runout helper logic which we don't mock deeply, 
        # but avoiding it is the key optimization


# ------------------------------------------------------------------
# Old Implementation (MmuHallFilamentWidthSensor / MmuHallEndstop)
# ------------------------------------------------------------------
class OldSensor:
    def __init__(self):
        self.runout_helper = MockRunoutHelper()
        self.lastFilamentWidthReading = 0
        self.lastFilamentWidthReading2 = 0
        self.diameter = 1.75
        self.nominal_filament_dia = 1.75
        self.hall_min_diameter = 1.0
        
        # Calibration constants used in slope
        self.dia1 = 1.5
        self.dia2 = 2.0
        self.rawdia1 = 9500
        self.rawdia2 = 10500

        self._homing = False
        self._triggered = False
        self._trigger_completion = None
        self._last_trigger_time = None

    def _calc_diameter(self):
        try:
            val_sum = self.lastFilamentWidthReading + self.lastFilamentWidthReading2
            slope = (self.dia2 - self.dia1) / (self.rawdia2 - self.rawdia1)
            diameter_new = round(slope * (val_sum - self.rawdia1) + self.dia1, 2)
            self.diameter = (5.0 * self.diameter + diameter_new) / 6
        except ZeroDivisionError:
            self.diameter = self.nominal_filament_dia

    def _check_trigger(self, eventtime):
        is_present = self.diameter > self.hall_min_diameter
        self.runout_helper.note_filament_present(eventtime, is_present)
        
        if self._homing:
            if is_present == self._triggered:
                if self._trigger_completion is not None:
                    self._last_trigger_time = eventtime
                    # self._trigger_completion.complete(True)
                    self._trigger_completion = None

    def adc_callback(self, read_time, read_value):
        self.lastFilamentWidthReading = round(read_value * 10000)
        self._calc_diameter()
        self._check_trigger(read_time)

    def adc2_callback(self, read_time, read_value):
        self.lastFilamentWidthReading2 = round(read_value * 10000)
        self._calc_diameter()
        self._check_trigger(read_time)


# ------------------------------------------------------------------
# New Implementation (MmuHallSensor)
# ------------------------------------------------------------------
class NewSensor:
    def __init__(self):
        self.runout_helper = MockRunoutHelper()
        self._val1 = 0.
        self._val2 = 0.
        self._trigger_threshold = 0.95 # equivalent trigger threshold (approx 9500 in old raw units)
        self.lastReadTime = 0
        self.present = False
        self.lastTriggerTime = 0
        self.last_button = False

        self._homing = False
        self._triggered = False
        self._trigger_completion = None
        self._last_trigger_time = None

    def adc_callback(self, read_time, read_value):
        self._val1 = read_value
        self.lastReadTime = read_time
        
        present = (read_value + self._val2) > self._trigger_threshold
        if present != self.present:
            self.present = present
            self.last_button = present
            # Optimization to only call runout helper if state changed or we have a button handler
            if self.runout_helper.button_handler or present != self.runout_helper.filament_present:
                self.runout_helper.note_filament_present(read_time, present)

        if self._homing:
            if present == self._triggered:
                if self._trigger_completion is not None:
                    self._last_trigger_time = read_time
                    # self._trigger_completion.complete(True)
                    self._trigger_completion = None
        
        if present:
            self.lastTriggerTime = read_time


    def adc2_callback(self, read_time, read_value):
        self._val2 = read_value
        self.lastReadTime = read_time

        # Optimization - only process trigger on secondary pin if homing
        # During printing (normal runout detection), the primary callback frequency is sufficient
        if not self._homing:
            return

        present = (self._val1 + read_value) > self._trigger_threshold
        if present != self.present:
            self.present = present
            self.last_button = present
            # Optimization to only call runout helper if state changed or we have a button handler
            if self.runout_helper.button_handler or present != self.runout_helper.filament_present:
                self.runout_helper.note_filament_present(read_time, present)

        if self._homing:
            if present == self._triggered:
                if self._trigger_completion is not None:
                    self._last_trigger_time = read_time
                    # self._trigger_completion.complete(True)
                    self._trigger_completion = None
        
        if present:
            self.lastTriggerTime = read_time


# ------------------------------------------------------------------
# Benchmark Scenarios
# ------------------------------------------------------------------

old_sensor = OldSensor()
new_sensor = NewSensor()

n = 500_000

print(f"Full Chain Benchmark ({n} iterations per callback)")
print("=" * 60)

for scenario in ["Normal Printing", "Homing"]:
    print(f"\\nScenario: {scenario}")
    print("-" * 60)
    
    homing = (scenario == "Homing")
    
    # Setup state
    old_sensor._homing = homing
    new_sensor._homing = homing
    
    # State values
    read_val1_old, read_val2_old = 0.45, 0.45 
    old_sensor.lastFilamentWidthReading2 = round(read_val2_old * 10000)
    new_sensor._val2 = read_val2_old
    
    # Set matching states
    old_sensor.runout_helper.filament_present = False
    new_sensor.runout_helper.filament_present = False
    old_sensor.present = False
    new_sensor.present = False

    def run_old_adc1(): old_sensor.adc_callback(123.456, read_val1_old)
    def run_old_adc2(): old_sensor.adc2_callback(123.456, read_val2_old)
    
    def run_new_adc1(): new_sensor.adc_callback(123.456, read_val1_old)
    def run_new_adc2(): new_sensor.adc2_callback(123.456, read_val2_old)

    t_old_adc1 = timeit.timeit(run_old_adc1, number=n)
    t_new_adc1 = timeit.timeit(run_new_adc1, number=n)

    t_old_adc2 = timeit.timeit(run_old_adc2, number=n)
    t_new_adc2 = timeit.timeit(run_new_adc2, number=n)
    
    t_old_total = t_old_adc1 + t_old_adc2
    t_new_total = t_new_adc1 + t_new_adc2

    print(f"Old (ADC1 + ADC2):      {t_old_total:.4f}s  (ADC1: {t_old_adc1:.4f}s, ADC2: {t_old_adc2:.4f}s)")
    print(f"New (ADC1 + ADC2):      {t_new_total:.4f}s  (ADC1: {t_new_adc1:.4f}s, ADC2: {t_new_adc2:.4f}s)")
    print(f"Speedup:                {t_old_total / t_new_total:.2f}x")
    print(f"Time saved (Total):     {(t_old_total - t_new_total) / n * 1e6:.2f} µs per paired callback loop")
