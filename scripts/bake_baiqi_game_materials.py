"""Bake the approved costume artwork and arm-matched facial pigment for UE."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def linear(rgb):
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def srgb(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= .0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - .055)


def load_rgba(path):
    with Image.open(path) as image:
        return np.array(image.convert('RGBA'), dtype=np.float32) / 255


def opaque_art(input_image, fallback):
    alpha = input_image[..., 3:4]
    return linear(input_image[..., :3]) * alpha + np.asarray(fallback[:3]) * (1 - alpha)


def bake_texture(directory, material, record):
    rows = record['images']
    kind = record['type']
    if kind in {'hidden', 'skin_junction'} or not rows:
        return None
    source = load_rgba(directory / rows[0]['path'])
    if kind in {'skin_body', 'masked'}:
        rgba = source
    else:
        pigment = opaque_art(source, record['fallback_rgba'])
        if kind == 'skin_face':
            mask = load_rgba(directory / rows[1]['path'])[..., 0:1]
            arm = linear(np.asarray(record['arm_sample']))
            face = linear(np.asarray(record['face_sample']))
            assert np.all(face > .15)
            pigment = pigment * (mask + (1 - mask) * (arm / face))
        rgba = np.concatenate((srgb(pigment), np.ones_like(source[..., 3:4])), axis=-1)
    pixels = np.rint(np.clip(rgba, 0, 1) * 255).astype(np.uint8)
    name = 'T_BaiQi_' + hashlib.sha256(material.encode('utf-8')).hexdigest()[:14]
    path = directory / 'baked' / (name + '.png')
    Image.fromarray(pixels).save(path, compress_level=4)
    return path.relative_to(directory).as_posix()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', required=True, type=Path)
    args = parser.parse_args()
    directory = ROOT / args.inputs
    forms = json.loads((directory / 'form_inputs.json').read_text(encoding='utf-8'))
    (directory / 'baked').mkdir(exist_ok=True)
    records = {}
    for form in forms.values():
        for material, row in form['materials'].items():
            if material in records:
                continue
            records[material] = {
                'type': row['type'], 'color': row['fallback_rgba'], 'texture': bake_texture(directory, material, row),
            }
    (directory / 'engine_materials.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_UE_ARTWORK_BAKED', len(records))


if __name__ == '__main__':
    main()
