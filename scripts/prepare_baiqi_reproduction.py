"""Restore public source inputs to local working paths without downloading tools."""
import shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def extract(archive,destination):
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target=(destination/info.filename).resolve();assert target.is_relative_to(destination.resolve()),'Archive path leaves workspace'
        z.extractall(destination)
extract(ROOT/'resources/Delta.zip',ROOT/'source')
extract(ROOT/'repro/third_party/VRoid_base_female.zip',ROOT/'artifacts/anatomy_base')
src=next((ROOT/'artifacts/anatomy_base').rglob('Base_Female.vrm'));shutil.copy2(src,ROOT/'artifacts/anatomy_base/Base_Female.glb')
for source,target in [('repro/native_inputs/repair_015/Delta_adult.blend','build/qa_pre_inputs_015/Delta_adult.blend')]:
    dst=ROOT/target;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,dst)
print('BAIQI_PUBLIC_INPUTS_RESTORED; run inspect_anatomy_base.py in Blender before retargeting')
