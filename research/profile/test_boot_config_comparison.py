"""Cross-boot comparison only; never changes runtime PCI verification."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('profile_boot', Path(__file__).with_name('make-profile.py'))
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)


def sample():
    words = [0] * 64
    for offset, value in {0: 0x248910de, 8: 0x030000a1, 0x2c: 0x884f1043,
                          0x34: 0x60, 0x60: 0x48036801, 0x68: 0x00807805,
                          0x78: 0x0012b410, 0xa8: 0x001e0004}.items():
        words[offset // 4] = value
    return [f'{word:08x}' for word in words]


class BootConfigTests(unittest.TestCase):
    def compare(self, first, second):
        # Before implementation, exercise the existing exact comparison.
        return getattr(mp, 'boot_configs_equal', lambda a, b: a == b)(first, second)

    def test_observed_status_bit_can_differ_between_boots(self):
        first, second = sample(), sample()
        second[0xa8 // 4] = '001f0004'
        self.assertTrue(self.compare(first, second))
        self.assertTrue(self.compare(second, first))
        self.assertEqual(first[0xa8 // 4], '001e0004')
        self.assertEqual(second[0xa8 // 4], '001f0004')

    def test_identical_configs_keep_existing_behavior(self):
        self.assertTrue(self.compare(sample(), sample()))

    def test_every_other_bit_remains_exact(self):
        for index in range(64):
            for bit in range(32):
                if (index, bit) == (0xa8 // 4, 16):
                    continue
                first, second = sample(), sample()
                second[index] = f'{int(second[index], 16) ^ (1 << bit):08x}'
                with self.subTest(index=index, bit=bit):
                    self.assertFalse(self.compare(first, second))

    def test_exception_requires_exact_observed_identity_and_layout(self):
        for index in (0, 2, 0x2c // 4, 0x34 // 4, 0x60 // 4, 0x68 // 4, 0x78 // 4):
            first, second = sample(), sample()
            first[index] = second[index] = f'{int(first[index], 16) ^ 1:08x}'
            second[0xa8 // 4] = '001f0004'
            with self.subTest(index=index):
                self.assertFalse(self.compare(first, second))

    def test_unobserved_status_or_control_is_not_normalized(self):
        for value in (0x000e0004, 0x003e0004, 0x001e0003):
            first, second = sample(), sample()
            first[0xa8 // 4] = f'{value:08x}'
            second[0xa8 // 4] = f'{value ^ 0x10000:08x}'
            self.assertFalse(self.compare(first, second))


if __name__ == '__main__':
    unittest.main()
