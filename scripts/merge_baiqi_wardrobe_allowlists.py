"""Select the approved coat-on default and coat-off MoTian assets for one container."""
import argparse
import json
from pathlib import Path


DEFAULT = '/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple'
CLIMAX = '/HuaShira/Characters/Hero/Hero_Hun_Climax/SkinParts/Hun_Body_Climax'
MOTIAN = '/HuaShira/Characters/Hero/Hero_Hun_MoTian/Hun_MoTian_Body_Simple'
WARDROBE = {'default': 'coat_on', 'climax': 'coat_on', 'motian': 'coat_off'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    forms = {form: json.loads((args.inputs / f'{form}_allowlist.json').read_text(encoding='utf-8'))
             for form in ('coat_on', 'coat_off')}
    on, off = forms['coat_on'], forms['coat_off']
    shared_keys = ('adult_bones', 'combined_bones', 'body_sha256', 'material_strategy',
                   'excluded_placeholders', 'replacement_packages')
    for key in shared_keys:
        assert on[key] == off[key], key
    assert on['form'] == 'coat_on' and off['form'] == 'coat_off'
    assert on['source_sha256'] != off['source_sha256']
    assert on['material_strategy'] == 'native_baiqi_cloth_and_cutout'
    staged = []
    dependencies = set(on['owned_assets']) & set(off['owned_assets'])
    for outfit, mesh_path in (('default', DEFAULT), ('climax', CLIMAX), ('motian', MOTIAN)):
        form = WARDROBE[outfit]
        source = forms[form]
        assert mesh_path in source['replacement_packages'], mesh_path
        index, row = next((i, row) for i, row in enumerate(source['staged_bodies']) if row['path'] == mesh_path)
        folder = f'/HuaShira/Mods/BaiQi054/{form}'
        graph = folder + '/ABP_AdultBaiQi'
        collider = f'{folder}/Cloth_{index}/PH_BaiQiClothThighs'
        assert {graph, collider} <= set(source['owned_assets']), mesh_path
        assert 'maxdist=9.50' in row['cloth'], mesh_path
        dependencies.update((graph, collider))
        staged.append({**row, 'form': form, 'outfit': outfit, 'post_process': graph, 'collider': collider})
    merged = {key: on[key] for key in shared_keys}
    merged.update(form='wardrobe', wardrobe=WARDROBE,
                  source_models={key: value['source_sha256'] for key, value in forms.items()},
                  owned_assets=sorted(dependencies), staged_bodies=staged, status='staged_pending_cook')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(merged, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_WARDROBE_ALLOWLIST', args.out)


if __name__ == '__main__':
    main()
