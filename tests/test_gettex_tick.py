import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.market_collector.gettex_tick import process_file


class GettexTickTests(unittest.TestCase):
    def test_live_batch_item_receipts_record_insert_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work").mkdir()
            slot = "20261112.09.45"
            source = root / ("mosa2-gettex-posttrade." + slot + ".mund.csv.gz")
            raw = gzip.compress(b"ZZ0000000016,09:44:30,EUR,1.25,1\n")
            source.write_bytes(raw)
            source.chmod(0o600)
            receipt = {"sha256":hashlib.sha256(raw).hexdigest(),"captured_at":"2026-11-12 10:07:06.240470"}
            config = {"php":"php","project":str(root),"web":str(root/"web"),"python":"python3","password":"fixture-only"}
            real_stat = Path.stat

            def private_stat(path, *args, **kwargs):
                result = real_stat(path, *args, **kwargs)
                if path != source or os.name != "nt":
                    return result
                fields = list(result)
                fields[0] = (fields[0] & ~0o777) | 0o600
                return os.stat_result(fields)

            for writer, counts in [("INSERT",(1,0)),("DUPLICATE_UNCHANGED",(0,1))]:
                response = {"ok":True,"batch":{"item_results":[{"writer":writer,"readback":"PASS"}]},
                            "current":{"readback":"PASS"}}
                with patch.object(Path, "stat", private_stat), patch("scripts.market_collector.gettex_tick.subprocess.run",
                           return_value=subprocess.CompletedProcess([],0,json.dumps(response).encode(),b"")) as child:
                    result = process_file(root, config, slot, receipt, source, ["ZZ0000000016","ZZ0000000024"])
                self.assertEqual((result["observations"],result["duplicates"],result["failures"]),(*counts,0))
                request = json.loads(child.call_args.kwargs["input"])
                self.assertEqual(request["scope"]["expected_isins"],["ZZ0000000016"])
