"""Run Blender with a reliable native exit code and a quiet file log."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
log=(ROOT/sys.argv[1]).resolve();assert log.is_relative_to(ROOT)
script=(ROOT/sys.argv[2]).resolve();assert script.is_file()
command=[r'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe','--background','--factory-startup',
         '--python-exit-code','23','--python',str(script),'--',*sys.argv[3:]]
with log.open('wb') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
print('BLENDER_EXIT',result.returncode,script.name)
raise SystemExit(result.returncode)
