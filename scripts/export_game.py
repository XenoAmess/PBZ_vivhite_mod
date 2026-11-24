"""Invoke the verified local exporter without exposing the private asset key.

Usage: .venv/Scripts/python.exe scripts/export_game.py <out_subdir> <command> [args...]
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if len(sys.argv)<3:
    raise SystemExit(__doc__)
out=(ROOT/'artifacts/extracted'/sys.argv[1]).resolve()
assert out.is_relative_to((ROOT/'artifacts/extracted').resolve()), 'Output must remain in artifacts/extracted'
out.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
env['PBZX_AES']=(ROOT/'tools/_private/aes.txt').read_text().strip()
args=[str(ROOT/'tools/PbzExport/PbzExport.exe'),
      r'Z:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks',
      str(ROOT/'tools/Mappings.usmap'),str(ROOT/'tools/oo2core_9_win64.dll'),
      str(out),*sys.argv[2:]]
result=subprocess.run(args,env=env)
raise SystemExit(result.returncode)
