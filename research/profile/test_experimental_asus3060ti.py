"""Experimental identity admission tests, synthetic data; no hardware claim."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('asus_data', HERE / 'test_local_topology.py')
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)
mp = data.mp
PROM = '2c6108c3c5fe6f6ff4d205f9ca2279c3b2f8fc35828fd5e8a5c31719d025df51'


class ExperimentalTests(unittest.TestCase):
    def envelope(self):
        self.assertTrue(callable(getattr(mp, 'experimental_asus3060ti_envelope', None)),
                        'explicit experimental admission is not implemented')
        original = json.loads((HERE / 'proven.json').read_text())
        snapshot = json.dumps(original, sort_keys=True)
        experimental = mp.experimental_asus3060ti_envelope(original)
        self.assertEqual(json.dumps(original, sort_keys=True), snapshot)
        self.assertNotIn('248910de', original['probe_device_ids'])
        return experimental

    def capture(self):
        return data.synthetic_capture(board=0x248910de, chip=0xb74000a1,
                                      memory=0x2000, children=1, aggregate=True,
                                      no_edid=False).replace('38811462', '884f1043').replace(data.PROM_HASH, PROM)

    def analyze(self, text, envelope):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'DIAG00.TXT'
            path.write_text(text)
            return mp.analyze(path, None, envelope)

    def test_default_admission_still_refuses(self):
        with self.assertRaisesRegex(mp.Refused, 'device ID is outside'):
            self.analyze(self.capture(), json.loads((HERE / 'proven.json').read_text()))

    def test_explicit_admission_marks_experimental_header(self):
        row = self.analyze(self.capture(), self.envelope())
        self.assertEqual(dict(row['defines'])['GU_EXPERIMENTAL_ASUS3060TI'], '1')

    def test_wrong_subsystem_and_prom_refused(self):
        for text in (self.capture().replace('884f1043', '884e1043'),
                     self.capture().replace(PROM, '0' * 64)):
            with self.subTest(text=text[:30]), self.assertRaisesRegex(mp.Refused, 'experimental ASUS'):
                self.analyze(text, self.envelope())


if __name__ == '__main__':
    unittest.main()
