"""Prepare the appearance thumbnail and derive the option schema from local framework metadata."""
import json
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/baiqi_standalone'
METADATA = ROOT / ('artifacts/extracted/baiqi_outfit_framework/ProjectPBZ/Plugins/GameFeatures/'
                   'PBZModLoader/Content/Options/S_PBZOutfitOption.json')
ICON = ROOT / 'output/live2d_delta/baiqi_cc0_054/review/coat_on_relaxed_front_torso.png'


def main():
    schema, = json.loads(METADATA.read_text(encoding='utf-8-sig'))
    assert schema['Name'] == 'S_PBZOutfitOption'
    fields = []
    for field in schema['ChildProperties']:
        is_array = field['Type'] == 'ArrayProperty'
        fields.append({'name': field['Name'], 'array': is_array,
                       'kind': field['Inner']['Type'] if is_array else field['Type']})
    guid = schema['Properties']['Guid'].replace('-', '')
    assert guid == 'E086C2174F6B09686694BFBCC5CC0A15', guid
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'option_schema.json').write_text(
        json.dumps({'schema_guid': guid, 'option_schema': fields}, indent=2) + '\n', encoding='utf-8')
    with Image.open(ICON) as image:
        thumbnail = ImageOps.fit(image.convert('RGB'), (512, 512), Image.Resampling.LANCZOS, centering=(0.5, 0.29))
        thumbnail.save(BUILD / 'appearance_icon.png')


if __name__ == '__main__':
    main()
