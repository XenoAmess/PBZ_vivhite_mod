"""Compose a shallow iris normal over the current game face normal, per eye pose."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from bake_baiqi_eye_materials import load, save
from bake_baiqi_face_relief import NORMAL, encode


STATES = ('neutral', 'half_blink', 'closed', 'look_left', 'look_right')


def iris_normals(mask, amount):
    y, x = np.indices(mask.shape)
    nx = np.zeros(mask.shape, dtype=np.float64)
    ny = np.zeros_like(nx)
    for side in (x < mask.shape[1] / 2, x >= mask.shape[1] / 2):
        rows, cols = np.nonzero((mask > .35) & side)
        if not len(cols):
            continue
        sx, sy = np.ptp(cols) * .34, np.ptp(rows) * .34
        assert sx > 1. and sy > 1.
        u, v = (x - cols.mean()) / sx, (y - rows.mean()) / sy
        envelope = amount * np.exp(-.5 * (u * u + v * v)) * mask * side
        nx += u * envelope / sx
        ny -= v * envelope / sy
    return nx, ny


def compose_native(base, nx, ny):
    size = base.shape[1], base.shape[0]
    x, y = [np.asarray(Image.fromarray(field.astype(np.float32)).resize(size, Image.Resampling.BILINEAR))
            for field in (nx, -ny)]
    affected = (np.abs(x) + np.abs(y)) > 1e-6
    source = base[affected].astype(np.float32) / 127.5 - 1.
    source[:, 0] += x[affected]
    source[:, 1] += y[affected]
    source /= np.linalg.norm(source, axis=1, keepdims=True)
    result = base.copy()
    result[affected] = np.rint((source * .5 + .5) * 255).astype(np.uint8)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--amount', type=float, default=1.65)
    args = parser.parse_args()
    assert .80 <= args.amount <= 2.80
    args.out.mkdir(parents=True, exist_ok=True)
    if args.inputs:
        palette = load(args.inputs / 'eye_palette.json')
        finishes = load(args.inputs / 'surface_finish.json')
        materials = {'neutral': palette['neutral'], **{state: row['material'] for state, row in palette['states'].items()}}
        native = args.inputs / 'native_textures'
        with Image.open(native / f'{NORMAL}.png') as image:
            base = np.array(image.convert('RGB'))
        x0, y0, x1, y1 = palette['affected_bounds']
    report = {'amount': args.amount, 'states': {}}
    for state in STATES:
        with Image.open(args.poses / f'{state}_iris.png') as image:
            mask = np.asarray(image, dtype=np.float64) / 255.
        assert mask.shape == (800, 880)
        nx, ny = iris_normals(mask, args.amount)
        assert np.any(nx) == (state != 'closed')
        tilt = float(np.degrees(np.arctan(np.hypot(nx, ny).max())))
        assert tilt < 6.
        file = args.out / f'{state}_iris_normal.png'
        encode(nx, ny).save(file)
        record = {'tilt_degrees': tilt, 'preview_sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
        if args.inputs and state != 'closed':
            combined = compose_native(base, nx, ny)
            changed = (combined != base).any(axis=2)
            inside = int(changed[y0:y1, x0:x1].sum())
            assert inside == int(changed.sum()) and inside > 0
            name = f'T_BaiQiNative_FaceRelief_{state}'
            Image.fromarray(combined).save(native / f'{name}.png')
            finishes[materials[state]].update(normal=name)
            record.update(native_normal=name, changed_native_pixels=inside)
        report['states'][state] = record
    save(args.out / 'iris_relief_inputs.json', report)
    if args.inputs:
        save(args.inputs / 'surface_finish.json', finishes)
        save(args.inputs / 'iris_relief_inputs.json', report)
    print('BAIQI_IRIS_RELIEF', report, flush=True)


if __name__ == '__main__':
    main()
