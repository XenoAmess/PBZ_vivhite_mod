"""Arrange unaltered shape renders into consistent inspection plates."""
import argparse,html,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();out=(ROOT/args.output).resolve();r=json.loads((out/'shape_manifest.json').read_text(encoding='utf-8'))
assert r['coverage_complete'] and len(r['images'])==r['expected_images']
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22);pages=[]
for section in ['full_body']+r['sections']:
    entries=[i for i in r['images'] if i['section']==section]
    groups=[[i for i in entries if i['pass']==kind] for kind in ['clay','textured']] if section=='full_body' else [entries]
    for entries in groups:
        ncols=4 if section=='full_body' else 3;tile=480 if section=='full_body' else 512
        rows=(len(entries)+ncols-1)//ncols;sheet=Image.new('RGB',(ncols*tile,rows*(tile+36)+48),(28,31,37));d=ImageDraw.Draw(sheet);d.text((16,8),section+' | actual mesh | pending review',font=font,fill='white')
        for index,item in enumerate(entries):
            x=(index%ncols)*tile;y=48+(index//ncols)*(tile+36)
            d.text((x+10,y),item['pass']+' / '+str(item['angle_deg'])+' deg',font=font,fill=(220,225,235))
            with Image.open(out/item['path']) as image:sheet.paste(image.convert('RGB').resize((tile,tile)),(x,y+32))
        name=section+('_'+entries[0]['pass'] if section=='full_body' else '')+'.jpg';sheet.save(out/name,quality=94);pages.append(name)
body=['<!doctype html><meta charset="utf-8"><title>Delta whole-body shape audit</title><style>body{max-width:1400px;margin:32px auto;background:#181c23;color:#eee;font:18px system-ui}img{width:100%}a{color:#9af}</style><h1>全身静态形体检查</h1><p>固定视角与灯光。灰模和贴图逐部位检查；这些图不代表验收通过。</p>']
for name in pages:body.append('<section><h2>'+html.escape(name)+'</h2><a href="'+name+'"><img src="'+name+'" loading="lazy"></a></section>')
(out/'index.html').write_text('\n'.join(body),encoding='utf-8');print('SHAPE_PLATES_READY',len(pages))
