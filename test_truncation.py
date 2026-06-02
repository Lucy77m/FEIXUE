import ctypes
from ctypes import wintypes

# Test what happens when int() converts a float
pid_float = 1234.5
pid_int = int(pid_float)
print(f"1234.5 -> int() -> {pid_int}")

# Test if int() actually truncates
test_floats = [1234.1, 1234.5, 1234.9]
for f in test_floats:
    print(f"{f} -> {int(f)}")
    
# Verify we get silent truncation
print(f"\nTruncation confirmed: 1234.5 becomes {int(1234.5)}, not 1235")
