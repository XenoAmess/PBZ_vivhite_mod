"""Tone the two existing white pads in BaiQi's original eyewear artwork."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


MATERIAL = 'BaiQi round gold glasses appearance'
VALUE = .88


def smooth(value):
    amount = np.clip(value, 0., 1.)
    return amount * amount * (3. - 2. * amount)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    forms = json.loads((args.inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    source = forms['coat_on']['materials'][MATERIAL]
    assert source == forms['coat_off']['materials'][MATERIAL]
    entry, = source['images']
    original = args.inputs / entry['path']
    assert hashlib.sha256(original.read_bytes()).hexdigest() == entry['sha256']
    with Image.open(original) as source_image:
        rgba = np.array(source_image.convert('RGBA'), dtype=np.float32)
    assert rgba.shape == (800, 880, 4)
    y, x = np.indices(rgba.shape[:2])
    red, _, blue, alpha = rgba.transpose((2, 0, 1))
    # The source components share a drawable. Identify the white parts only
    # within the two measured pad bounds under the bridge.
    bounds = (((x >= 410) & (x <= 427)) | ((x >= 452) & (x <= 469))) & (y >= 441) & (y <= 469)
    white = smooth((blue - 169.) / 49.) * smooth((33. - (red - blue)) / 26.)
    weight = np.rint(bounds * white * smooth((alpha - 64.) / 145.) * 255.).astype(np.uint8)
    result = rgba.copy()
    result[..., :3] *= (1. - weight * ((1. - VALUE) / 255.))[..., None]
    result = np.rint(result).astype(np.uint8)
    changed = np.any(result != rgba, axis=2)
    assert changed.any() and not (changed & ~bounds).any()
    assert np.array_equal(result[..., 3], rgba[..., 3])
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / 'frame_pads.png'
    Image.fromarray(result).save(destination)
    report = {'source_sha256': entry['sha256'], 'candidate_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'max_rgb_multiplier': 1., 'min_rgb_multiplier': VALUE, 'changed_pixels': int(changed.sum())}
    (args.out / 'frame_pads.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
