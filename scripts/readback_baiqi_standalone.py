"""Verify the cooked appearance and coat toggle against the shipped PBZ skeleton."""
import json
from pathlib import Path

from readback_baiqi_adult_form import GAME, ROOT, cooked_path, export, verify_bones


OUT = ROOT / 'output/live2d_delta/baiqi_054_standalone'
BUILD = ROOT / 'build/baiqi_standalone'
FRAMEWORK = ROOT / 'tools/BaiQiOutfitFramework/runtime'
EXTRACT = ROOT / 'artifacts/extracted/baiqi_standalone'
COMPOSITES = [
    'ProjectPBZ/Content/PBZContent/DataTable/UI/DT_PBZAppearanceTable',
    'ProjectPBZ/Plugins/GameFeatures/PBZModLoader/Content/Options/DT_PBZOutfitOptions',
]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, document):
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def verify():
    allow = load(BUILD / 'standalone_allowlist.json')
    manifest = load(OUT / 'manifest.json')
    outfit_id, slot = allow['outfit_id'], allow['framework_slot']
    outfit, options = (f'ProjectPBZ/Content/Mods/PBZOutfitSlots/DT_{kind}Slot_{slot}'
                       for kind in ('Outfit', 'Options'))
    body = cooked_path('/HuaShira/Mods/BaiQi054/Standalone/SK_BaiQi')
    EXTRACT.mkdir(parents=True, exist_ok=True)
    actual = export(OUT, EXTRACT, 'list', [r'\.uasset$'])
    expected = {cooked_path(name) + '.uasset' for name in allow['owned_assets']}
    assert set(actual.splitlines()) == expected
    assert allow['replacement_packages'] == manifest['replacement_packages'] == []

    mounted = f'{OUT};{FRAMEWORK}'
    export(GAME, EXTRACT, 'json', [outfit, options, body, *COMPOSITES], mounted)
    export(GAME, EXTRACT, 'skel', [body], mounted)
    appearance, = load(EXTRACT / (outfit + '.json'))
    toggles, = load(EXTRACT / (options + '.json'))
    for composite, part in zip(COMPOSITES, (outfit, options)):
        data, = load(EXTRACT / (composite + '.json'))
        row_struct = 'PBZAppearanceStruct' if part == outfit else 'S_PBZOutfitOption'
        assert row_struct in data['Properties']['RowStruct']['ObjectName']
        assert any(entry and Path(part).name + '.' in entry['ObjectPath']
                   for entry in data['Properties']['ParentTables']), part

    rows = appearance['Rows']
    row = rows[outfit_id]
    assert len(rows) == 5 and row['AppearanceName']['ValueCache']['SourceString'] == '白绮'
    assert row['ItemId'] == outfit_id and row['bObtainableInGame'] and row['bDefaultHatHidden']
    assert row['AppearanceType'] == 'EAppearanceType::Outfit'
    assert row['AppearanceTexture']['AssetPathName'].endswith('/T_BaiQiAppearance.T_BaiQiAppearance')
    mesh_path = rows[row['OutfitBodyItem']]['BodyMeshAsset']['AssetPathName']
    assert mesh_path == '/HuaShira/Mods/BaiQi054/Standalone/SK_BaiQi.SK_BaiQi'
    for part, asset in [('HairStyle', 'HeadAsset'), ('SequenceHairStyle', 'HeadAsset'),
                        ('MeshBand', 'MeshBandAsset'), ('BrowLashCard', 'BrowLashCardAsset')]:
        assert rows[row[f'Outfit{part}Item']][asset]['AssetPathName'].endswith('/SK_BaiQiBlank.SK_BaiQiBlank')
    assert list(toggles['Rows']) == ['BaiQi_RemoveCoat']
    toggle = {name.split('_', 1)[0]: value for name, value in toggles['Rows']['BaiQi_RemoveCoat'].items()}
    assert toggle['Label']['SourceString'] == '脱外套' and toggle['Type'] == 'Hide'
    assert toggle['OutfitMesh']['AssetPathName'] == mesh_path
    assert not toggle['DefaultOn'] and not toggle['HideParts']
    assert toggle['HideSlots'] == [int(index) for index in allow['coat_slots']]

    geometry = load(EXTRACT / (body + '.SK_BaiQi.skel.json'))
    original = load(ROOT / 'repro/game_reference/adult_reference.skel.json')['bones']
    bone_error = verify_bones(geometry['bones'], original)
    assert len(geometry['bones']) == 348 and len(original) == 264 and 'Hun_Skin_Skeleton' in geometry['skeleton']
    materials = [item['slot'] for item in geometry['materials']]
    assert set(materials[index] for index in toggle['HideSlots']) == set(allow['coat_slots'].values())
    sections = geometry['lods'][0]['sections']
    triangles = {materials[item['MaterialIndex']]: item['NumTriangles'] for item in sections}
    assert all(triangles[materials[index]] > 0 for index in toggle['HideSlots'])
    assert triangles['F00_001_01_Body_00_SKIN'] == 7398
    assert triangles['BaiQi original face appearance'] == 9516
    assert triangles['BaiQi neck junction shading'] > 0
    assert triangles['BaiQi charcoal coat back'] > 0  # Wristbands retain this material in both forms.
    mesh_json = (EXTRACT / (body + '.json')).read_text(encoding='utf-8')
    assert 'ABP_AdultBaiQi' in mesh_json and 'PH_BaiQiClothThighs' in mesh_json
    save(OUT / 'readback.json', {
        'status': 'verified_offline', 'outfit': outfit_id, 'slot': slot, 'coat_slots': allow['coat_slots'],
        'bones': len(geometry['bones']), 'source_bone_max_error_cm': bone_error, 'files': manifest['files'],
        'triangles_by_material': triangles, 'framework_tables_resolved': True,
    })
    save(OUT / 'manifest.json', dict(manifest, status='readback_verified_pending_game'))
    print('BAIQI_STANDALONE_VERIFIED', outfit_id, slot, toggle['HideSlots'])


if __name__ == '__main__':
    verify()
