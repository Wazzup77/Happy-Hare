
import timeit

class McuAdcMock:
    def __init__(self):
        self._last_state = (0.5, 1234.5)
    
    def get_last_value(self):
        return self._last_state

class SensorCurrent:
    def __init__(self):
        self._val1 = 0.
        self._val2 = 0.
        self.mcu_adc = McuAdcMock()
        self.present = False
        
    def callback(self, val):
        self._val1 = val
        self._check_trigger()
        
    def _check_trigger(self):
        self.present = (self._val1 + self._val2) > 0.5

class SensorProposed:
    def __init__(self):
        self.mcu_adc = McuAdcMock()
        self.mcu_adc2 = McuAdcMock() # Need 2 for hall
        self.present = False
        
    def callback(self, val):
        # User proposed: Don't store, fetch from object
        # Note: In reality callback provides 'val' which IS the latest for this pin
        # But we need the OTHER pin's value from the object
        v1 = val
        v2, _ = self.mcu_adc2.get_last_value()
        self.present = (v1 + v2) > 0.5

class SensorOptimized:
    def __init__(self):
        self._val1 = 0.
        self._val2 = 0.
        self.present = False
        
    def callback(self, val):
        self._val1 = val
        # Inline logic, no method call, local cache
        self.present = (val + self._val2) > 0.5

# Setup instances
s_cur = SensorCurrent()
s_prop = SensorProposed()
s_opt = SensorOptimized()

# Run Benchmarks
n = 1000000

t_cur = timeit.timeit(lambda: s_cur.callback(0.6), number=n)
t_prop = timeit.timeit(lambda: s_prop.callback(0.6), number=n)
t_opt = timeit.timeit(lambda: s_opt.callback(0.6), number=n)

print(f"Iterations: {n}")
print(f"1. Current (call _check_trigger): {t_cur:.4f}s")
print(f"2. Proposed (call get_last_value): {t_prop:.4f}s")
print(f"3. Optimized (Inline + Local Store): {t_opt:.4f}s")

print("\nRelative Performance (Lower is better):")
base = t_cur
print(f"Current:   100.0%")
print(f"Proposed:  {t_prop/base*100:.1f}%")
print(f"Optimized: {t_opt/base*100:.1f}%")
