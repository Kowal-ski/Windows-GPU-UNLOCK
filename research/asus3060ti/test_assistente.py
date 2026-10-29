"""RAM/filesystem-only wizard tests. Never query/stage a real USB or GPU."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('assistente',Path(__file__).with_name('assistente.py'))
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


def inventory():
    return {'cards':[{'vendor':'10de','device':'2489','subsystem':'884f1043'}],
            'usb':[{'drive':'Z','disk':123,'partition':1,'offset':1048576,'size':32000000}],
            'esp':['11111111-2222-3333-4444-555555555555'],'board':[],'bios':[]}


def capture(root,tag='one'):
    root.mkdir(parents=True,exist_ok=True);data=bytes(1048576)
    (root/'PROM.BIN').write_bytes(data);(root/'IMG00.BIN').write_bytes(b'image')
    (root/'DIAG00.TXT').write_text(f'capture={tag}\nprobe-target seg=0x0 bus=0x1 dev=0x0 fun=0x0\nprom sha256={hashlib.sha256(data).hexdigest()}\ncapture-complete=1\ndiagnostic-result status=0x0000000000000000\n')


class WizardTests(unittest.TestCase):
    def test_exact_target_and_explicit_usb(self):
        self.assertEqual(w.validate_inventory(inventory(),'z')[0]['disk'],123)

    def test_foreign_multi_gpu_and_ambiguous_partitions_refused(self):
        for mutate in (lambda x:x['cards'][0].update(device='2487'),
                       lambda x:x['cards'][0].update(subsystem='00000000'),
                       lambda x:x['cards'].append(dict(x['cards'][0])),
                       lambda x:x['usb'].clear(),lambda x:x['esp'].append(x['esp'][0])):
            info=inventory();mutate(info)
            with self.assertRaises(ValueError):w.validate_inventory(info,'Z')

    def test_usb_letter_reuse_is_detected_before_mutation(self):
        info=inventory();expected=dict(info['usb'][0]);info['usb'][0]['offset']+=4096
        with patch.object(w,'inventory',return_value=info),self.assertRaises(ValueError):
            w.recheck_usb('Z',expected)

    def test_completion_must_be_unique_successful_and_have_target(self):
        good='probe-target x\ncapture-complete=1\ndiagnostic-result status=0x0000000000000000\n'
        self.assertTrue(w.complete_capture(good))
        for bad in (good+'capture-complete=1\n',good.replace('complete=1','complete=0'),
                    good.replace('status=0x0000000000000000','status=0x8000000000000007'),
                    good.replace('probe-target x\n','')):
            self.assertFalse(w.complete_capture(bad))

    def test_import_keeps_verified_backup_and_clears_only_capture_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);usb=root/'usb';private=root/'private';capture(usb)
            (usb/'keep.txt').write_text('preserve')
            result=w.import_capture(usb,private)
            self.assertEqual((result/'PROM.BIN').stat().st_size,1048576)
            self.assertFalse((usb/'PROM.BIN').exists());self.assertEqual((usb/'keep.txt').read_text(),'preserve')
            self.assertEqual(len(list(usb.glob('wizard-archive-*'))),1)
            capture(usb)
            with self.assertRaisesRegex(ValueError,'ja foi importada'):w.import_capture(usb,private)
            self.assertTrue((usb/'PROM.BIN').exists())

    def test_corrupt_prom_preserves_all_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);usb=root/'usb';capture(usb);(usb/'PROM.BIN').write_bytes(b'x'*1048576)
            with self.assertRaisesRegex(ValueError,'Hash'):w.import_capture(usb,root/'private')
            self.assertTrue((usb/'DIAG00.TXT').exists());self.assertFalse(list(usb.glob('wizard-archive-*')))

    def test_assembly_requires_two_unique_boots_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);usb=root/'usb';private=root/'private';capture(usb);w.import_capture(usb,private)
            with self.assertRaises(ValueError):w.capture_set(private,root/'assembled')
            capture(usb,'two');w.import_capture(usb,private)
            self.assertEqual(len(w.capture_set(private,root/'assembled')),2)
            self.assertIn('one',(root/'assembled/DIAG00.TXT').read_text())
            self.assertIn('two',(root/'assembled/DIAG01.TXT').read_text())
            with self.assertRaises(ValueError):w.capture_set(private,root/'assembled')

    def test_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);inside=root/'inside';inside.mkdir()
            with self.assertRaises(ValueError):w.contained(inside,root/'outside')
            self.assertEqual(w.contained(inside,inside/'safe'),inside/'safe')

    def test_marker_hash_rejects_path_traversal(self):
        for value in ('../escape','', 'a'*63):
            with self.assertRaises(ValueError):w.marker_hash({'EfiSha256':value})
        self.assertEqual(w.marker_hash({'EfiSha256':'A'*64}),'a'*64)

    def test_stage_cancel_does_not_call_stager(self):
        with patch.object(w,'inventory',return_value=inventory()),patch.object(w,'recheck_usb'),\
             patch.object(w,'ps') as stage,patch('builtins.input',return_value='NAO'),\
             patch.object(w.os,'name','nt'),patch('sys.argv',['assistente.py','--action','stage','--drive','Z']):
            w.main();stage.assert_not_called()


if __name__=='__main__':unittest.main()
