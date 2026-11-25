"""Bake source eye poses as native-parent swaps on the existing face slot."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from bake_baiqi_game_materials import load_rgba, match_face_pigment, opaque_art, srgb
from bake_baiqi_native_material_inputs import face_mix_texture, texture_size


FACE_SLOT = 'BaiQi original face appearance'
STATES = ('half_blink', 'closed', 'look_left', 'look_right')
EYE_BOUNDS = (274, 371, 606, 471)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def stem(name):
    return hashlib.sha256(name.encode()).hexdigest()[:14]


def render_albedo(source_path, mask_path, source):
    rgba = load_rgba(source_path)
    mask = load_rgba(mask_path)[..., 0:1]
    pigment = opaque_art(rgba, source['fallback_rgba'])
    rgb = srgb(match_face_pigment(pigment, mask, source))
    return Image.fromarray(np.rint(rgb * 255).astype(np.uint8))


def restrict_pose(base, pose, bounds):
    assert base.size == pose.size
    isolated = base.copy()
    isolated.paste(pose.crop(bounds), bounds[:2])
    assert isolated.tobytes() != base.tobytes()
    return isolated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--poses', type=Path, required=True)
    args = parser.parse_args()
    inputs, poses = args.inputs, args.poses
    native = inputs / 'native_textures'
    sources = load(inputs / 'form_inputs.json')
    source = sources['coat_on']['materials'][FACE_SLOT]
    assert source == sources['coat_off']['materials'][FACE_SLOT]
    materials = load(inputs / 'engine_materials.json')
    finishes = load(inputs / 'surface_finish.json')
    finish = finishes[FACE_SLOT]
    with Image.open(native / f'T_BaiQiNative_{stem(FACE_SLOT)}.png') as image:
        albedo = image.copy()
    with Image.open(native / f'{finish["mix"]}.png') as image:
        mix = image.copy()
    with Image.open(poses / 'neutral.png') as original, Image.open(inputs / source['images'][0]['path']) as face_art:
        assert original.size == (880, 800) and texture_size(original) == albedo.size == mix.size
        assert original.convert('RGBA').tobytes() == face_art.convert('RGBA').tobytes()
    sx, sy = albedo.width / 880, albedo.height / 800
    left, top, right, bottom = EYE_BOUNDS
    bounds = (math.floor(left * sx), math.floor(top * sy), math.ceil(right * sx), math.ceil(bottom * sy))
    report = {'slot': FACE_SLOT, 'neutral': FACE_SLOT, 'states': {}, 'affected_bounds': bounds}
    for state in STATES:
        identifier = f'BaiQi face {state}'
        mask_path = poses / f'{state}_mask.png'
        texture = render_albedo(poses / f'{state}.png', mask_path, source)
        texture = texture.resize(albedo.size, Image.Resampling.LANCZOS)
        color = restrict_pose(albedo, texture, bounds)
        masked_mix = restrict_pose(mix, face_mix_texture(mask_path, finish['roughness']), bounds)
        color_path = native / f'T_BaiQiNative_{stem(identifier)}.png'
        mix_name = f'T_BaiQiMix_{stem(identifier)}'
        color.save(color_path)
        masked_mix.save(native / f'{mix_name}.png')
        materials[identifier] = dict(materials[FACE_SLOT], texture=color_path.relative_to(inputs).as_posix())
        finishes[identifier] = dict(finish, mix=mix_name)
        report['states'][state] = {'material': identifier, 'texture': color_path.name}
    save(inputs / 'engine_materials.json', materials)
    save(inputs / 'surface_finish.json', finishes)
    save(inputs / 'eye_palette.json', report)
    print('BAIQI_NATIVE_EYE_PALETTE', len(report['states']), bounds, flush=True)


if __name__ == '__main__':
    main()
