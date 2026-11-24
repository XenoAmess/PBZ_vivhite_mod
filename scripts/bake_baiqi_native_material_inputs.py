"""Prepare game-native albedo and cutout maps from the approved BaiQi bake."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image


def srgb_channel(linear):
    return round(255 * (12.92 * linear if linear <= .0031308 else 1.055 * linear ** (1 / 2.4) - .055))


def texture_size(image):
    return tuple(2 ** round(math.log2(value)) for value in image.size)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', type=Path)
    parser.add_argument('skin_report', type=Path)
    args = parser.parse_args()
    directory = args.inputs / 'native_textures'
    directory.mkdir(exist_ok=True)
    materials = json.loads((args.inputs / 'engine_materials.json').read_text(encoding='utf-8'))
    arm = json.loads(args.skin_report.read_text(encoding='utf-8'))['coat_off']['arm_reference_texel']
    for name, row in materials.items():
        stem = hashlib.sha256(name.encode()).hexdigest()[:14]
        kind = row['type']
        if row['texture']:
            with Image.open(args.inputs / row['texture']) as image:
                color = image.convert('RGBA').resize(texture_size(image), Image.Resampling.LANCZOS)
        else:
            rgb = [round(channel * 255) for channel in arm] if kind == 'skin_junction' else [
                srgb_channel(channel) for channel in row['color'][:3]]
            color = Image.new('RGBA', (64, 64), (*rgb, 0 if kind == 'hidden' else 255))
        color.convert('RGB').save(directory / f'T_BaiQiNative_{stem}.png')
        if kind in {'masked', 'hidden'}:
            color.getchannel('A').convert('RGB').save(directory / f'T_BaiQiAlpha_{stem}.png')
    for name, flat in [('FlatNormal', (128, 128, 255)), ('Mix', (255, 195, 0)),
                       ('NeutralBlack', (0, 0, 0)), ('NeutralWhite', (255, 255, 255))]:
        Image.new('RGB', (64, 64), flat).save(directory / f'T_BaiQiNative_{name}.png')


if __name__ == '__main__':
    main()
