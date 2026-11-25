"""Import both BaiQi forms and read back their shipped-parent material parameters."""
import json
from pathlib import Path
import sys

import unreal


sys.path.insert(0, str(Path(__file__).resolve().parent))
from ue_baiqi_native_materials import CLOTH, PREFIX, build_native_palette
from ue_build_baiqi_forms import assign_materials, slug
from ue_probe_baiqi_native_bridge import asset_library, import_mesh, reconcile_reference, tool
from ue_stage_baiqi_adult_form import DRIVER_SKELETON, INPUT
from ue_stage_baiqi_standalone import COAT_MATERIALS


def verify_palette(palette, finishes):
    records = {}
    for name, finish in finishes.items():
        material = palette[slug(name)]
        assert material.get_editor_property('parent').get_path_name().split('.')[0] == CLOTH, name
        values = json.loads(tool.dump_material_instance_parameters(material))
        params = {row['name']: row['value'] for row in values if row['index'] == 0}
        mix = params['Mix'].split('.')[-1]
        normal = params['Normal'].split('.')[-1]
        strength = float(params['NormalIntensity'])
        assert (mix, normal) == (finish['mix'], finish.get('normal', 'T_BaiQiNative_FlatNormal')), name
        assert abs(strength - finish.get('normal_strength', 0.)) < 1e-6, name
        assert abs(float(params['Specular']) - finish['specular']) < 1e-6, name
        records[name] = {'material': material.get_path_name(), 'mix': mix, 'normal': normal,
                         'normal_strength': strength, 'specular': float(params['Specular'])}
    return records


def verify_eye_switch(mesh, names, palette, eyes):
    slot = names.index(slug(eyes['slot']))
    component = unreal.SkeletalMeshComponent()
    component.set_skeletal_mesh_asset(mesh)
    materials = [component.get_material(index) for index in range(len(names))]
    assert materials[slot] == palette[slug(eyes['neutral'])]
    states = {}
    for state, row in eyes['states'].items():
        alternate = palette[slug(row['material'])]
        component.set_material(slot, alternate)
        assert component.get_material(slot) == alternate
        assert all(component.get_material(index) == material for index, material in enumerate(materials) if index != slot)
        states[state] = alternate.get_path_name()
    component.set_material(slot, materials[slot])
    assert component.get_material(slot) == materials[slot]
    return {'slot': slot, 'original': materials[slot].get_path_name(), 'states': states}


def main():
    assert PREFIX.startswith('/HuaShira/Mods/') and '/BaiQi054/' not in PREFIX, PREFIX
    review = PREFIX.rsplit('/', 1)[0] + '/OfflineReview'
    forms = json.loads((INPUT / 'form_inputs.json').read_text(encoding='utf-8'))
    finishes = json.loads((INPUT / 'surface_finish.json').read_text(encoding='utf-8'))
    eye_path = INPUT / 'eye_palette.json'
    eyes = json.loads(eye_path.read_text(encoding='utf-8')) if eye_path.is_file() else None
    palette = build_native_palette()
    skeleton = unreal.load_asset(DRIVER_SKELETON)
    assert len(forms) == 2 and skeleton
    output = {'status': 'editor_readback', 'materials': verify_palette(palette, finishes), 'forms': {}}
    coat = {slug(name) for name in COAT_MATERIALS}
    for form, prepared in forms.items():
        mesh = import_mesh(str(INPUT / prepared['fbx']), 'SK_BaiQi_' + form, review, skeleton=skeleton)
        bones = reconcile_reference(mesh)
        names = assign_materials(mesh, palette)
        assert len(bones) == 348
        actual = {name for name in names if slug(name) in coat}
        assert {slug(name) for name in actual} == (coat if form == 'coat_on' else set()), actual
        assert asset_library.save_loaded_asset(mesh)
        output['forms'][form] = {'mesh': mesh.get_path_name(), 'bones': len(bones), 'source_sha256': prepared['source_sha256'],
                                 'coat_slots': sorted(actual), 'sections': json.loads(tool.dump_sections(mesh))}
        if eyes:
            output['forms'][form]['eye_material_switch'] = verify_eye_switch(mesh, names, palette, eyes)
    (INPUT / 'surface_finish_readback.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    unreal.log('BAIQI_SURFACE_FINISH_EDITOR_READBACK')


if __name__ == '__main__':
    main()
