"""Continue the original gold skirt border on an unused part of its atlas."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


FRONT = 'BaiQi pleated skirt artwork'
BOX = (1020, 1370, 1328, 1722)
SOURCE_ROWS = (899., 1220.)


def smooth(value):
    amount = np.clip(value, 0., 1.)
    return amount * amount * (3. - 2. * amount)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    forms = json.loads((args.inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    art = forms['coat_on']['materials'][FRONT]
    assert art == forms['coat_off']['materials'][FRONT]
    entry, = art['images']
    source = args.inputs / entry['path']
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == entry['sha256']
    with Image.open(source) as image:
        assert image.size == (1400, 2200)
        atlas = np.array(image.convert('RGBA'))
    red, green, blue, alpha = atlas.transpose((2, 0, 1)).astype(np.int16)
    gold = (red > 178) & (green > 112) & (red - blue > 54) & (green - blue > 32) & (alpha > 172)
    gold &= np.arange(len(red))[:, None] > 1080
    assert gold.any()
    source_gold = np.median(atlas[gold, :3], axis=0)
    left, top, right, bottom = BOX
    rear = atlas[top:bottom, left:right]
    assert not rear[..., 3].any()
    azimuth = np.linspace(0., 1., right - left)
    row = np.linspace(*SOURCE_ROWS, bottom - top)[:, None]
    centre = 1117.5 + 39. * np.sin(np.pi * azimuth) ** 1.15
    distance = np.abs(row - centre)
    edge = smooth((3.75 + 2.1 - distance) / 1.35)[..., None]
    stripe = smooth((3.75 - distance) / 1.6)[..., None]
    cloth = np.array([226., 230., 237.])
    stitch = np.array([117., 97., 63.])
    color = cloth * (1. - edge) + stitch * edge
    rear[..., :3] = np.rint(color * (1. - stripe) + source_gold * stripe).astype(np.uint8)
    rear[..., 3] = 255
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / 'skirt_rear.png'
    Image.fromarray(atlas).save(path)
    report = {'source_sha256': digest, 'candidate_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'atlas_box': BOX, 'source_rows': SOURCE_ROWS, 'gold_srgb': source_gold.astype(int).tolist()}
    (args.out / 'skirt_rear.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
