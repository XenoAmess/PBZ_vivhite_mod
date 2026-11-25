"""Remove the inherited planar neck tint from the projected lower face."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from baiqi_source_raster import SourceRaster
from bake_baiqi_eye_materials import STATES
from bake_baiqi_face_relief import ramp
from bake_baiqi_jaw_outline import CROP, OUTLINE


NECK_TINT = {'ArtMesh115', 'ArtMesh233'}
EDGE_TINT = 'ArtMesh54'


def source_region(edge):
    raster = SourceRaster(2800, 4400)
    try:
        parts = {part['id']: part for part in raster.source['parts']}

        def descendants(name):
            return {name}.union(*(descendants(child) for child in parts[name]['children']))

        face = descendants('Face') - descendants('Glasses')
        shadow = {row['id'] for row in raster.drawables if row['part'] == 'Fhair' and 'Facecolor' in row['masks']}
        layers = []
        omissions = (NECK_TINT, NECK_TINT | {EDGE_TINT}) if edge else (set(), NECK_TINT)
        for omit in omissions:
            frame = raster.render(face, include_drawables=shadow, exclude_drawables=omit | {'ArtMesh53', OUTLINE})
            layers.append(np.asarray(Image.fromarray(frame).crop(CROP)))
        return layers
    finally:
        raster.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--amount', type=float, required=True)
    parser.add_argument('--edge', action='store_true', help='Soften the painted edge after the neck tint correction.')
    args = parser.parse_args()
    if not 0 < args.amount <= 1. or args.poses.resolve() == args.out.resolve():
        parser.error('Supply an amount in (0, 1] and a separate output directory.')

    attached, hidden = source_region(args.edge)
    swatch = attached[520, 432, :3]
    assert np.array_equal(swatch, attached[590, 433, :3]) and attached[520, 432, 3] == 255
    if args.edge:
        y, x = np.mgrid[:800, :880]
        weight = ramp((y - 544.) / 15.) * ramp((621. - y) / 8.)
        weight *= ramp((x - 340.) / 18.) * ramp((460. - x) / 21.)
        delta = hidden[..., :3].astype(np.int16) - attached[..., :3].astype(np.int16)
        affected = (weight > 0.) & np.any(delta != 0, axis=2) & (attached[..., 3] > 0) & (hidden[..., 3] > 0)
        change = args.amount * delta[affected] * weight[affected, None]
        label, drawables = 'underjaw_edge', [EDGE_TINT]
    else:
        affected = np.any(attached != hidden, axis=2)
        affected[:567] = False
        rows, cols = np.nonzero(affected)
        assert len(rows) and 380 <= cols.min() <= cols.max() <= 450 and 572 <= rows.min() <= rows.max() <= 620
        target = np.where(hidden[affected, 3:4] > 0, hidden[affected, :3], swatch)
        change = args.amount * (target.astype(np.float32) - attached[affected, :3])
        label, drawables = 'underjaw_tint', sorted(NECK_TINT)

    args.out.mkdir(parents=True, exist_ok=True)
    for item in args.poses.iterdir():
        if item.is_file():
            shutil.copyfile(item, args.out / item.name)
    report = {'drawables': drawables, 'amount': args.amount, 'skin_rgb': swatch.tolist(), 'states': {}}
    for state in ('neutral', *STATES):
        filename = f'{state}.png'
        with Image.open(args.poses / filename) as image:
            previous = np.asarray(image.convert('RGBA'))
        if not args.edge:
            assert np.array_equal(previous[affected], attached[affected]), state
        corrected = previous.copy()
        corrected[affected, :3] = np.clip(np.rint(previous[affected, :3] + change), 0, 255).astype(np.uint8)
        report['states'][state] = int(np.sum(np.any(corrected != previous, axis=2)))
        Image.fromarray(corrected).save(args.out / filename)
    Image.fromarray(affected.astype(np.uint8) * 255).save(args.out / f'{label}_mask.png')
    (args.out / f'{label}.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
