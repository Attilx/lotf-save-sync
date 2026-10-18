"""Run with python -m unittest discover -s tests -v.
Only synthetic inputs are distributed; no private save fixtures are included.
"""
import itertools,json,os,struct,tempfile,unittest,zipfile,zlib
from pathlib import Path
from lotfsync.engine import *
from lotfsync.workflow import *
from lotfsync.i18n import TEXT


class FormatTests(unittest.TestCase):
    def test_fstring_unicode(self):
        for s in ('', 'Ironman', 'È già qui', '玩家🛡'):
            b=encode_fstr(s);self.assertEqual(fstr(b,0),(s,len(b)))
    def test_translation_coverage(self):
        self.assertEqual(set(TEXT['it']),set(TEXT['en']))
    def test_bad_input(self):
        for data in (b'',b'hello',b'GVAS'+b'\0'*200):
            with self.assertRaises(FormatError):strict_read(data)
    def test_zip_selection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.zip'
            with zipfile.ZipFile(p,'w') as z:
                for n in ('folder/Save00.sav','folder/Save00_b1.sav','folder/Save00_b2.sav','folder/Save01.sav','GeneralSave.sav'):z.writestr(n,b'fake')
            s=Source.discover(p)
            self.assertEqual(s.keys('folder/Save00.sav',True),['folder/Save00.sav','folder/Save00_b1.sav','folder/Save00_b2.sav'])
            self.assertEqual(s.read(s.slots[0]),b'fake')
    def test_traversal_not_extracted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../../Save00.sav',b'fake')
            s=Source.discover(p);self.assertEqual(s.read(s.slots[0]),b'fake')
            self.assertEqual([x.name for x in Path(d).iterdir()],['a.zip'])

if __name__=='__main__':unittest.main()
