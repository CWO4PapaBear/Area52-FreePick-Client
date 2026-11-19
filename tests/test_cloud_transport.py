import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('cloud_transport',Path(__file__).parents[1]/'tools/deployment/cloud_transport.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CloudTransportTests(unittest.TestCase):
 def test_readonly_and_execution_commands_target_only_cloud(self):
  for readonly in (False,True):
   with tempfile.TemporaryDirectory() as folder:
    p=Path(folder)/'package.json';p.write_text(json.dumps({'target':'cloud','id':'area52-test','runner_sha256':m.hashlib.sha256(Path(m.__file__).with_name('cloud_activation.py').read_bytes()).hexdigest()}))
    args=['transport',str(p)]+(['--check-only'] if readonly else [])
    with patch.object(m.sys if hasattr(m,'sys') else __import__('sys'),'argv',args),patch.object(m.subprocess,'run') as run:
     run.return_value.returncode=0
     with self.assertRaises(SystemExit) as e:m.main()
     self.assertEqual(e.exception.code,0);run.assert_called_once();cmd=run.call_args.args[0]
     self.assertIn('root@129.121.172.245',cmd);self.assertIn('StrictHostKeyChecking=yes',cmd)
     code=run.call_args.kwargs['input'].decode();self.assertEqual('--check-only' in code,readonly);self.assertIn('hashlib.sha256',code)
 def test_wrong_target_and_unsafe_id_rejected_before_network(self):
  for fields in ({'target':'development','id':'area52-test'},{'target':'cloud','id':'../bad'}):
   with tempfile.TemporaryDirectory() as folder:
    p=Path(folder)/'package.json';p.write_text(json.dumps(fields))
    with patch('sys.argv',['transport',str(p)]),patch.object(m.subprocess,'run') as run:
     with self.assertRaises(ValueError):m.main()
     run.assert_not_called()
