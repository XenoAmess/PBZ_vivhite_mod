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


def skin_relief(amount, nasal_strength=1.):
    # Coordinates come from the original 880 x 800 face atlas. Keep the
    # original eyelids, hair-shadow line, and mouth outside the active relief.
    y, x = np.mgrid[0:800, 0:880]
    nose = 3.8 * gaussian(x, y, (439, 467), (15, 32))
    cheeks = 2.75 * (gaussian(x, y, (380, 486), (38, 26)) + gaussian(x, y, (498, 486), (38, 26)))
    nasal_crease = .95 * (gaussian(x, y, (424, 488), (6.8, 11)) + gaussian(x, y, (454, 488), (6.8, 11)))
    lower_eye = 460. - 25. * np.exp(-.5 * ((x - 439) / 30.) ** 2)
    skin = ramp((y - lower_eye) / 14.) * ramp((523 - y) / 17.)
    skin *= ramp((x - 304.) / 23.) * ramp((574. - x) / 23.)
    height = (nasal_strength * nose + cheeks - nasal_strength * nasal_crease) * skin * amount
    dy, dx = np.gradient(height)
    slope = np.hypot(dx, dy)
    bound = np.maximum(1., slope / .165)
    return -dx / bound, dy / bound


def encode(nx, ny):
    normals = np.stack((nx, ny, np.ones_like(nx)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    return Image.fromarray(np.rint((normals * .5 + .5) * 255).astype(np.uint8))


def lift_nose_response(image, basis, amount, *, directx=False):
    x0, y0, x1, y1 = basis['box']
    normal_z, tangent_z, bitangent_z = basis['vertical'].transpose((2, 0, 1))
    rows, columns = np.mgrid[y0:y1, x0:x1]
    core = gaussian(columns, rows, (429., 506.5), (12.5, 11.))
    weight = core * ramp((-.18 - normal_z) / .34)
    weight *= (ramp((columns - 402.) / 10.) * ramp((458. - columns) / 12.)
               * ramp((rows - 490.) / 10.) * ramp((529. - rows) / 10.))

    def sample(field):
        full = np.zeros((800, 880), dtype=np.float32)
        full[y0:y1, x0:x1] = field
        return np.asarray(Image.fromarray(full).resize(image.size, Image.Resampling.BILINEAR))

    affected = sample(weight) > .003
    directions = (tangent_z, -bitangent_z if directx else bitangent_z, normal_z)
    upward = np.column_stack([sample(weight * axis)[affected] for axis in directions]).astype(np.float64)
    pixels = np.array(image.convert('RGB'))
    base = pixels[affected].astype(np.float64) / 127.5 - 1.
    base /= np.linalg.norm(base, axis=1, keepdims=True)
    upward -= np.sum(base * upward, axis=1, keepdims=True) * base
    desired = base + amount * upward
    desired /= np.linalg.norm(desired, axis=1, keepdims=True)
    changed = np.rint((desired * .5 + .5) * 255).astype(np.uint8)
    count = np.any(pixels[affected] != changed, axis=1).sum()
    pixels[affected] = changed
    angles = np.degrees(np.arccos(np.clip(np.sum(base * desired, axis=1), -1., 1.)))
    return Image.fromarray(pixels), {'changed_texels': int(count), 'max_tilt_degrees': float(angles.max())}


def soften_nose_ridge(image, basis, amount, *, directx=False):
    x0, y0, x1, y1 = basis['box']
    normal_x, tangent_x, bitangent_x = basis['horizontal'].transpose((2, 0, 1))
    rows, columns = np.mgrid[y0:y1, x0:x1]
    weight = np.exp(-.5 * ((columns + .5 - 429.) / 5.1) ** 2)
    weight *= ramp((rows - 478.) / 12.) * ramp((523. - rows) / 13.)
    weight *= ramp((columns - 413.) / 10.) * ramp((445. - columns) / 10.)

    def sample(field):
        full = np.zeros((800, 880), dtype=np.float32)
        full[y0:y1, x0:x1] = field
        return np.asarray(Image.fromarray(full).resize(image.size, Image.Resampling.BILINEAR))

    support = sample(weight)
    affected = support > .003
    axes = (tangent_x, -bitangent_x if directx else bitangent_x, normal_x)
    x_axis = np.column_stack([sample(axis)[affected] for axis in axes])
    x_axis /= np.linalg.norm(x_axis, axis=1, keepdims=True)
    pixels = np.array(image.convert('RGB'))
    base = pixels[affected].astype(np.float64) / 127.5 - 1.
    base /= np.linalg.norm(base, axis=1, keepdims=True)
    lateral = np.sum(base * x_axis, axis=1)
    direction = x_axis - lateral[:, None] * base
    desired = base - (amount * support[affected] * lateral)[:, None] * direction
    desired /= np.linalg.norm(desired, axis=1, keepdims=True)
    changed = np.rint((desired * .5 + .5) * 255).astype(np.uint8)
    count = np.any(pixels[affected] != changed, axis=1).sum()
    pixels[affected] = changed
    angles = np.degrees(np.arccos(np.clip(np.sum(base * desired, axis=1), -1., 1.)))
    return Image.fromarray(pixels), {'changed_texels': int(count), 'max_tilt_degrees': float(angles.max())}


def attach_native(inputs, directx, strength, nose_basis=None, nose_lift=0., nose_ridge=0.):
    finish_path = inputs / 'surface_finish.json'
    finishes = load(finish_path)
    palettes = load(inputs / 'eye_palette.json')
    materials = [FACE_SLOT, *(row['material'] for row in palettes['states'].values())]
    native = inputs / 'native_textures' / f'{NORMAL}.png'
    converted = directx.resize((1024, 1024), Image.Resampling.BILINEAR)
    if nose_basis is not None:
        converted, _ = lift_nose_response(converted, nose_basis, nose_lift, directx=True)
    if nose_ridge:
        converted, _ = soften_nose_ridge(converted, nose_basis, nose_ridge, directx=True)
    converted.save(native)
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
    parser.add_argument('--nasal-strength', default=1., type=float,
                        help='Scale the nose and nostril relief while retaining the authored cheek relief.')
    parser.add_argument('--nose-basis', type=Path, help='Sampled nose tangent basis for the authored head.')
    parser.add_argument('--nose-lift', default=.40, type=float,
                        help='Tilt the downward-facing nose normals toward overhead light.')
    parser.add_argument('--nose-ridge', default=0., type=float,
                        help='Soften the lateral normal transition across the original nose ridge.')
    args = parser.parse_args()
    assert .35 <= args.amount <= 1.5 and 0 < args.strength <= 1.
    assert .45 <= args.nasal_strength <= 1.
    args.out.mkdir(parents=True, exist_ok=True)
    nx, ny = skin_relief(args.amount, args.nasal_strength)
    blender = encode(nx, ny)
    nose_basis = None
    nose_report = None
    if args.nose_basis:
        assert 0. < args.nose_lift <= .60
        with np.load(args.nose_basis) as source:
            nose_basis = dict(source)
        blender, nose_report = lift_nose_response(blender, nose_basis, args.nose_lift)
    if args.nose_ridge:
        if not 0 < args.nose_ridge <= .90 or nose_basis is None or 'horizontal' not in nose_basis:
            parser.error('--nose-ridge requires a rebuilt nose basis and a value greater than 0 and at most .90')
        blender, ridge_report = soften_nose_ridge(blender, nose_basis, args.nose_ridge)
    blender.save(args.out / 'face_relief_blender.png')
    report = {'amount': args.amount, 'normal_strength': args.strength, 'nasal_strength': args.nasal_strength,
              'max_tangent_tilt_degrees': float(np.degrees(np.arctan(np.hypot(nx, ny).max()))),
              'blender_normal_sha256': hashlib.sha256((args.out / 'face_relief_blender.png').read_bytes()).hexdigest()}
    if nose_report:
        report['nose_lift'] = {'amount': args.nose_lift, 'basis_sha256': hashlib.sha256(args.nose_basis.read_bytes()).hexdigest(),
                               'head_sha256': str(nose_basis['head_sha256']), **nose_report}
    if args.nose_ridge:
        report['nose_ridge'] = {'amount': args.nose_ridge, **ridge_report}
    if args.game_inputs:
        report['native_normal_sha256'] = attach_native(args.game_inputs, encode(nx, -ny), args.strength,
                                                       nose_basis, args.nose_lift, args.nose_ridge)
    save(args.out / 'face_relief_inputs.json', report)
    print('BAIQI_FACE_RELIEF', report, flush=True)


if __name__ == '__main__':
    main()
