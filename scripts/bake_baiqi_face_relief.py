"""Bake a restrained tangent normal around the nose and cheeks without changing face pigment."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from bake_baiqi_eye_materials import FACE_SLOT, load, save


NORMAL = 'T_BaiQiNative_FaceRelief'


def gaussian(x, y, centre, spread):
    return np.exp(-.5 * (((x - centre[0]) / spread[0]) ** 2 + ((y - centre[1]) / spread[1]) ** 2))


def ramp(value):
    t = np.clip(value, 0, 1)
    return t * t * (3. - 2. * t)


def skin_relief(amount):
    # Coordinates come from the original 880 x 800 face atlas. Keep the
    # original eyelids, hair-shadow line, and mouth outside the active relief.
    y, x = np.mgrid[0:800, 0:880]
    nose = 3.8 * gaussian(x, y, (439, 467), (15, 32))
    cheeks = 2.75 * (gaussian(x, y, (380, 486), (38, 26)) + gaussian(x, y, (498, 486), (38, 26)))
    nasal_crease = .95 * (gaussian(x, y, (424, 488), (6.8, 11)) + gaussian(x, y, (454, 488), (6.8, 11)))
    lower_eye = 460. - 25. * np.exp(-.5 * ((x - 439) / 30.) ** 2)
    skin = ramp((y - lower_eye) / 14.) * ramp((523 - y) / 17.)
    skin *= ramp((x - 304.) / 23.) * ramp((574. - x) / 23.)
    height = (nose + cheeks - nasal_crease) * skin * amount
    dy, dx = np.gradient(height)
    slope = np.hypot(dx, dy)
    bound = np.maximum(1., slope / .165)
    return -dx / bound, dy / bound


def encode(nx, ny):
    normals = np.stack((nx, ny, np.ones_like(nx)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    return Image.fromarray(np.rint((normals * .5 + .5) * 255).astype(np.uint8))


def attach_native(inputs, directx, strength):
    finish_path = inputs / 'surface_finish.json'
    finishes = load(finish_path)
    palettes = load(inputs / 'eye_palette.json')
    materials = [FACE_SLOT, *(row['material'] for row in palettes['states'].values())]
    native = inputs / 'native_textures' / f'{NORMAL}.png'
    directx.resize((1024, 1024), Image.Resampling.BILINEAR).save(native)
    for name in materials:
        finishes[name].update(normal=NORMAL, normal_strength=strength)
    save(finish_path, finishes)
    return hashlib.sha256(native.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--game-inputs', type=Path)
    parser.add_argument('--amount', default=1., type=float)
    parser.add_argument('--strength', default=.75, type=float)
    args = parser.parse_args()
    assert .35 <= args.amount <= 1.5 and 0 < args.strength <= 1.
    args.out.mkdir(parents=True, exist_ok=True)
    nx, ny = skin_relief(args.amount)
    blender = encode(nx, ny)
    blender.save(args.out / 'face_relief_blender.png')
    report = {'amount': args.amount, 'normal_strength': args.strength,
              'max_tangent_tilt_degrees': float(np.degrees(np.arctan(np.hypot(nx, ny).max()))),
              'blender_normal_sha256': hashlib.sha256((args.out / 'face_relief_blender.png').read_bytes()).hexdigest()}
    if args.game_inputs:
        report['native_normal_sha256'] = attach_native(args.game_inputs, encode(nx, -ny), args.strength)
    save(args.out / 'face_relief_inputs.json', report)
    print('BAIQI_FACE_RELIEF', report, flush=True)


if __name__ == '__main__':
    main()
