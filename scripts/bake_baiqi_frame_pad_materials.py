"""Bake distinct roughness and metallic values for the existing glasses pads."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from bake_baiqi_frame_pads import MATERIAL, smooth


PAD_ROUGHNESS = .67
PAD_METALLIC = .05


def pad_mix(source, frame_roughness, frame_metallic):
    rgba = np.asarray(source.convert('RGBA'), dtype=np.float32)
    assert rgba.shape == (800, 880, 4)
    y, x = np.indices(rgba.shape[:2])
    red, _, blue, alpha = rgba.transpose((2, 0, 1))
    bounds = (((x >= 410) & (x <= 427)) | ((x >= 452) & (x <= 469))) & (y >= 441) & (y <= 469)
    neutral = smooth((blue - 146.) / 51.) * smooth((46. - (red - blue)) / 35.)
    mask = np.rint(neutral * smooth((alpha - 64.) / 112.) * bounds * 255.).astype(np.uint8)
    mask = Image.fromarray(mask).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.48))
    weight = np.asarray(mask.resize((1024, 1024), Image.Resampling.BILINEAR), dtype=np.float64) / 255.
    roughness = round(frame_roughness * 255)
    metallic = round(frame_metallic * 255)
    values = (np.full_like(weight, 255), roughness + weight * (PAD_ROUGHNESS * 255 - roughness),
              metallic + weight * (PAD_METALLIC * 255 - metallic))
    packed = np.rint(np.stack(values, axis=-1)).astype(np.uint8)
    assert np.all(packed[weight == 0] == (255, roughness, metallic))
    return Image.fromarray(packed), int(np.count_nonzero(weight))


def frame_albedo(inputs):
    forms = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    source = forms['coat_on']['materials'][MATERIAL]
    assert source == forms['coat_off']['materials'][MATERIAL]
    entry = next(row for row in source['images'] if row['node'] == 'Image Texture')
    path = inputs / entry['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    return path, entry['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--roughness', type=float, default=.46)
    parser.add_argument('--metallic', type=float, default=.62)
    args = parser.parse_args()
    assert 0. <= args.roughness <= 1. and 0. <= args.metallic <= 1.
    args.out.mkdir(parents=True, exist_ok=True)
    source, source_sha = frame_albedo(args.inputs)
    with Image.open(source) as albedo:
        image, support = pad_mix(albedo, args.roughness, args.metallic)
    destination = args.out / 'frame_pad_mix.png'
    image.save(destination)
    report = {'source_sha256': source_sha, 'mix_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'pad_roughness': PAD_ROUGHNESS, 'pad_metallic': PAD_METALLIC, 'mask_support_texels': support,
              'frame_roughness': args.roughness, 'frame_metallic': args.metallic}
    (args.out / 'frame_pad_mix.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
