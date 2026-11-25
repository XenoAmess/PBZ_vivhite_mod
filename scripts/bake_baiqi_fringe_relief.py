"""Bake light response from the interior lines of the original fringe art."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from bake_baiqi_eye_materials import load, save
from bake_baiqi_face_relief import encode
from bake_baiqi_native_material_inputs import texture_size


FRINGE = 'BaiQi bob front appearance'
NORMAL = 'T_BaiQiNative_FringeRelief'
STRENGTH = .55


def fringe_normals(image):
    rgba = np.asarray(image.convert('RGBA'), dtype=np.float32)
    tone = np.rint(rgba[..., :3] @ np.array([.2126, .7152, .0722])).astype(np.uint8)
    tone = Image.fromarray(tone)
    line = np.asarray(tone.filter(ImageFilter.GaussianBlur(1.5)), dtype=np.float32)
    surrounding = np.asarray(tone.filter(ImageFilter.GaussianBlur(6.)), dtype=np.float32)
    alpha = Image.fromarray(rgba[..., 3].astype(np.uint8))
    interior = np.asarray(alpha.filter(ImageFilter.MinFilter(9)), dtype=np.float32) / 255.
    height = -2.55 * np.clip((surrounding - line - 6.) / 55., 0., 1.) * interior
    y = np.arange(image.height)[:, None]
    height *= np.clip((640. - y) / 55., 0., 1.) * np.clip((y - 100.) / 50., 0., 1.)
    dy, dx = np.gradient(height)
    limit = np.maximum(1., np.hypot(dx, dy) / .16)
    return -dx / limit, dy / limit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--attach-native', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    forms = load(args.inputs / 'form_inputs.json')
    source = forms['coat_on']['materials'][FRINGE]
    assert source == forms['coat_off']['materials'][FRINGE]
    entry = next(row for row in source['images'] if row['node'] == 'Image Texture')
    path = args.inputs / entry['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    with Image.open(path) as image:
        assert image.size == (880, 800)
        nx, ny = fringe_normals(image)
        native_size = texture_size(image)
    file = args.out / 'fringe_relief_blender.png'
    encode(nx, ny).save(file)
    report = {'source_sha256': entry['sha256'], 'normal_strength': STRENGTH,
              'tilt_degrees': float(np.degrees(np.arctan(np.hypot(nx, ny).max()))),
              'blender_sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    if args.attach_native:
        finish_path = args.inputs / 'surface_finish.json'
        finishes = load(finish_path)
        output = args.inputs / 'native_textures' / f'{NORMAL}.png'
        encode(nx, -ny).resize(native_size, Image.Resampling.BILINEAR).save(output)
        finishes[FRINGE].update(normal=NORMAL, normal_strength=STRENGTH)
        save(finish_path, finishes)
        report['native_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    save(args.out / 'fringe_relief_inputs.json', report)


if __name__ == '__main__':
    main()
