"""Run required UE steps with exact exit codes and separate binary log files."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('step',choices=['build','import','materials','cook'])
parser.add_argument('--engine',default=r'E:\UE_5.7')
parser.add_argument('--no-pch',action='store_true',help='Build the editor helper without precompiled headers.')
parser.add_argument('--cook-dir',action='append',default=[],help='Include an additional content directory in the cook.')
args=parser.parse_args()
engine=Path(args.engine)
project=ROOT/'build/UE/ProjectPBZ/ProjectPBZ.uproject'
editor=engine/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
assert editor.is_file(),'UE editor installation is not ready'
version=json.loads((engine/'Engine/Build/Build.version').read_text())
assert (version['MajorVersion'],version['MinorVersion'])==(5,7),version
if args.step=='build':
    command=[str(engine/'Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe'),
             'Development','Win64',f'-Project={project}','-TargetType=Editor','-Progress','-NoHotReloadFromIDE','-NoUBA']
    if args.no_pch:command.append('-NoPCH')
else:
    command=[str(editor),str(project),'-unattended','-nop4','-stdout','-FullStdOutLogOutput','-nullrhi']
    if args.step in ['import','materials']:
        name='ue_import_delta.py' if args.step=='import' else 'ue_native_materials.py'
        command+=['-run=pythonscript',f'-script={ROOT / "scripts" / name}']
    else:
        command+=['-run=Cook','-TargetPlatform=Windows']
        command.extend(f'-CookDir={directory}' for directory in args.cook_dir)
logs=ROOT/'build/logs';logs.mkdir(parents=True,exist_ok=True)
path=logs/f'{args.step}.log'
print('Running UE step:',args.step,'log:',path,flush=True)
with path.open('wb') as stream:
    result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
with path.open('ab') as stream:stream.write(f'\nDELTA_STEP_EXIT {result.returncode}\n'.encode())
print('UE_STEP_EXIT',args.step,result.returncode,flush=True)
raise SystemExit(result.returncode)
