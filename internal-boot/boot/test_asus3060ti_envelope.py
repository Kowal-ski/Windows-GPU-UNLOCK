"""Execute the real C read envelope against RAM-only EFI services."""
import ctypes
import sys

lib = ctypes.CDLL(sys.argv[1])
check = lib.Envelope
check.argtypes = [ctypes.c_uint32] * 5 + [ctypes.c_int]
check.restype = ctypes.c_int
base = [0x248910de, 0x884f1043, 3, 0x030000a1, 0xa3000000, 0]
cases = [('exact captured identity', base, 1)]
for name, index, value in [
    ('other NVIDIA', 0, 0x220410de), ('Intel', 0, 0x9bc88086),
    ('other subsystem', 1, 0x40761458), ('BME enabled', 2, 7),
    ('MEM disabled', 2, 1), ('wrong revision', 3, 0x030000a2),
    ('zero BAR', 4, 0), ('unaligned BAR', 4, 0xa3000004),
]:
    values = base.copy()
    values[index] = value
    cases.append((name, values, 0))
for fault in range(1, 7):
    values = base.copy()
    values[5] = fault
    cases.append((f'resource failure {fault}', values, 0))
for name, values, expected in cases:
    actual = check(*values)
    assert actual == expected, f'{name}: expected {expected}, got {actual}'
print(f'PASS {len(cases)} production-envelope cases; RAM only, no hardware access')
