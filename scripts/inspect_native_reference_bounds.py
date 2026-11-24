"""Compare actual native mesh bounds, avoiding an assumed ground plane."""
import json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
path=ROOT/'artifacts/extracted/original/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple.uemodel'
UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,import_sockets=False,import_morph_targets=False)).import_file(path)
meshes=[o for o in bpy.data.objects if o.type=='MESH'];coords=np.concatenate([np.array([o.matrix_world@v.co for v in o.data.vertices]) for o in meshes])
report={'source':path.relative_to(ROOT).as_posix(),'units':'cm','bounds':{'min':coords.min(axis=0).tolist(),'max':coords.max(axis=0).tolist()},'foot_vertices_z_min':float(coords[coords[:,2]<20,2].min())}
(ROOT/'artifacts/native_reference_bounds.json').write_text(json.dumps(report,indent=2));print('NATIVE_MESH_BOUNDS',json.dumps(report))
