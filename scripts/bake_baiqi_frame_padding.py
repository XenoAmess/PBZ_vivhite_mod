"""Extend artwork color past its baked mesh cutout for texture filtering."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from bake_baiqi_native_material_inputs import FRAME_MATERIAL


CUTOUT_ALPHA = 64
DONOR_ALPHA = 128
MATERIALS = {'frame': FRAME_MATERIAL, 'fringe': 'BaiQi bob front appearance'}


def pad_cutout_color(rgba, radius):
    alpha = rgba[..., 3]
    color = rgba[..., :3]
    y, x = np.nonzero(alpha >= CUTOUT_ALPHA)
    top, left = max(0, y.min() - radius), max(0, x.min() - radius)
    bottom = min(alpha.shape[0], y.max() + radius + 1)
    right = min(alpha.shape[1], x.max() + radius + 1)
    area = np.s_[top:bottom, left:right]
    weights = alpha[area]
    height, width = weights.shape
    needs_color = weights < CUTOUT_ALPHA
    donors = np.pad(weights >= DONOR_ALPHA, radius)
    nearby_color = np.pad(color[area], ((radius, radius), (radius, radius), (0, 0)), mode='edge')
    result = color.copy()
    target = result[area]
    offsets = sorted(
        (dy * dy + dx * dx, dy, dx)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if 0 < dy * dy + dx * dx <= radius * radius
    )
    for _, dy, dx in offsets:
        row, column = radius + dy, radius + dx
        donor_area = np.s_[row:row + height, column:column + width]
        eligible = needs_color & donors[donor_area]
        target[eligible] = nearby_color[donor_area][eligible]
        needs_color[eligible] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--target', choices=MATERIALS, default='frame')
    parser.add_argument('--radius', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()

    materials = json.loads((args.inputs / 'engine_materials.json').read_text(encoding='utf-8'))
    material = MATERIALS[args.target]
    record = materials[material]
    if record['type'] != 'opaque_cutout':
        raise ValueError(f"Unexpected cutout texture type {record['type']!r} for {material}")
    stem = hashlib.sha256(material.encode()).hexdigest()[:14]
    path = args.inputs / 'native_textures' / f'T_BaiQiNative_{stem}.png'
    with Image.open(path) as native, Image.open(args.inputs / record['texture']) as source:
        current = np.asarray(native.convert('RGB'))
        rgba = np.asarray(source.convert('RGBA').resize(native.size, Image.Resampling.LANCZOS))
    original = rgba[..., :3]
    padded = pad_cutout_color(rgba, args.radius)
    if not (np.array_equal(current, original) or np.array_equal(current, padded)):
        raise ValueError('Native cutout color differs from its source bake. Rebuild the native textures first.')
    visible = rgba[..., 3] >= CUTOUT_ALPHA
    changed = np.any(padded != original, axis=2)
    if np.any(changed & visible):
        raise ValueError('Color padding crossed the original artwork cutout')
    Image.fromarray(padded).save(path)
    result = {
        'texture': path.name,
        'radius': args.radius,
        'texels_changed': int(changed.sum()),
        'unchanged_texels_at_or_above_cutoff': int(visible.sum()),
    }
    report = json.dumps(result, indent=2) + '\n'
    if args.report:
        args.report.write_text(report, encoding='utf-8')
    print(report, end='')


if __name__ == '__main__':
    main()
