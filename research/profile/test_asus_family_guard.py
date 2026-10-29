"""Preprocess real gpu-family.h; no GPU execution."""
import os
from pathlib import Path
import subprocess
import unittest

HEADER = Path(__file__).resolve().parents[2] / 'internal-boot/unlock/gpu-family.h'


@unittest.skipUnless(os.environ.get('GU_TEST_CLANG'), 'set GU_TEST_CLANG to the host clang executable')
class AsusFamilyGuardTests(unittest.TestCase):
    def check(self, extra, accepted):
        definitions = {'GU_PROFILE_LOCAL': '1', 'GU_CHIP_ID': '0xb74000a1U',
                       'GU_BOARD_ID': '0x248910deU', 'GU_BOARD_SUBSYSTEM': '0x884f1043U',
                       'GU_DEVICE_MEMORY_SIZE': '0x2000U'}
        for key, value in extra.items():
            if value is None:
                definitions.pop(key, None)
            else:
                definitions[key] = value
        code = ''.join(f'#define {k} {v}\n' for k, v in definitions.items())
        code += f'#include "{HEADER.as_posix()}"\n'
        run = subprocess.run([os.environ['GU_TEST_CLANG'], '-E', '-x', 'c', '-'],
                             input=code, capture_output=True, text=True)
        self.assertEqual(run.returncode == 0, accepted, run.stderr)

    def test_explicit_exact_local_tuple(self):
        self.check({'GU_EXPERIMENTAL_ASUS3060TI': '1'}, True)

    def test_no_implicit_support(self):
        self.check({}, False)

    def test_no_other_subsystem_memory_chip_or_board(self):
        for key, value in {'GU_BOARD_SUBSYSTEM': '0x884e1043U', 'GU_DEVICE_MEMORY_SIZE': '0x3000U',
                           'GU_CHIP_ID': '0xb76000a1U', 'GU_BOARD_ID': '0x248710deU'}.items():
            with self.subTest(key=key):
                self.check({'GU_EXPERIMENTAL_ASUS3060TI': '1', key: value}, False)

    def test_no_nonlocal_experiment(self):
        self.check({'GU_EXPERIMENTAL_ASUS3060TI': '1', 'GU_PROFILE_LOCAL': None,
                    'GU_GPU_FAMILY': '104U'}, False)


if __name__ == '__main__':
    unittest.main()
