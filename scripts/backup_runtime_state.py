"""Keep a private local copy of game saves before the authorized runtime test."""
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import shutil
ROOT=Path(__file__).resolve().parents[1]
destination=ROOT/'tools/_private'/('runtime_before_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
assert destination.resolve().is_relative_to((ROOT/'tools/_private').resolve())
destination.mkdir(parents=True)
sources=[Path(r'Z:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Saved'),Path(os.environ['LOCALAPPDATA'])/'ProjectPBZ/Saved']
copied=[]
for index,source in enumerate(sources):
    if not source.is_dir():continue
    for child in source.iterdir():
        if child.name=='SaveGames' and child.is_dir():
            target=destination/str(index)/child.name
            shutil.copytree(child,target);copied.append(str(child))
        elif child.is_file() and child.suffix.lower()=='.sav':
            target=destination/str(index)/child.name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(child,target);copied.append(str(child))
(destination/'backup.json').write_text(json.dumps({'sources':copied,'restored':False},indent=2))
print('PRIVATE_RUNTIME_BACKUP_READY',len(copied),'save locations')
