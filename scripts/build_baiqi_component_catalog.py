"""Make numbered, faithful source thumbnails for explicit accessory choices."""
import hashlib,html,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'qa/component_choices/baiqi';catalog=json.loads((out/'catalog.json').read_text(encoding='utf-8'));assets=ROOT/'artifacts/baiqi_component_audit';raw=out/'source_crops';raw.mkdir(exist_ok=True)
from baiqi_source_raster import SourceRaster
r=SourceRaster();font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',26);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
def checkers(size):
    image=Image.new('RGBA',size,(57,64,76,255));d=ImageDraw.Draw(image)
    for y in range(0,size[1],20):
        for x in range(0,size[0],20):
            if (x//20+y//20)%2:d.rectangle((x,y,x+19,y+19),fill=(67,74,86,255))
    return image
def thumbnail(item):
    if 'drawables' in item:
        r.set_state();im=Image.fromarray(r.render(set(),include_drawables=set(item['drawables'])));source='original_drawables:'+','.join(item['drawables'])
    elif 'preset' in item:
        path=assets/'variants'/(item['preset']+'.png');im=Image.open(path).convert('RGBA');source=path.relative_to(ROOT).as_posix()
        if not item.get('full_body'):im=im.crop((460,220,940,705))
    else:
        path=assets/item['image'];im=Image.open(path).convert('RGBA');source=path.relative_to(ROOT).as_posix()
    if 'crop' in item:im=im.crop(item['crop'])
    bbox=im.getbbox();assert bbox,('Blank component evidence',item['id'])
    left,top,right,bottom=bbox;pad=max(4,round(max(right-left,bottom-top)*.05));im=im.crop((max(0,left-pad),max(0,top-pad),min(im.width,right+pad),min(im.height,bottom+pad)))
    path=raw/f"{item['id']:02}.png";im.save(path);item['source_evidence']=source;item['thumbnail']=path.relative_to(out).as_posix();item.setdefault('decision','pending');item['thumbnail_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();return im
images={x['id']:thumbnail(x) for x in catalog['items']};r.close();boards=[]
starts=list(range(0,len(catalog['items']),9))
if len(starts)>1 and len(catalog['items'])-starts[-1]==1:starts.pop()
for page,offset in enumerate(starts):
    end=starts[page+1] if page+1<len(starts) else len(catalog['items']);items=catalog['items'][offset:end];sheet=Image.new('RGB',(1440,60+math.ceil(len(items)/3)*390),(26,30,38));d=ImageDraw.Draw(sheet);d.text((22,12),'白绮组件选择 / 原始 Live2D 素材 / '+str(offset+1)+'–'+str(offset+len(items)),font=font,fill='white')
    for index,item in enumerate(items):
        x=index%3*480;y=55+index//3*390;card=checkers((456,300));im=images[item['id']].copy();ratio=min(432/im.width,280/im.height);im=im.resize((max(1,round(im.width*ratio)),max(1,round(im.height*ratio))),Image.Resampling.LANCZOS);card.alpha_composite(im,((456-im.width)//2,(300-im.height)//2));sheet.paste(card.convert('RGB'),(x+12,y));d.text((x+18,y+309),f"{item['id']:02}  "+item['name'],font=font,fill='white');d.text((x+18,y+346),item['kind']+' · 等待选择',font=small,fill=(179,195,219))
    name=f'board_{offset//9+1:02}.jpg';sheet.save(out/name,quality=94);boards.append(name)
catalog['boards']=boards;(out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
body=['<!doctype html><meta charset="utf-8"><title>白绮组件选择</title><style>body{background:#1a1e26;color:#eee;font:18px/1.6 system-ui;margin:24px auto;max-width:1100px}article{display:grid;grid-template-columns:320px 1fr;gap:24px;margin:24px 0;padding:16px;background:#292f3b}img{width:300px;max-height:300px;object-fit:contain;background:#454b56}small{color:#b6c5df}</style><h1>白绮组件选择</h1><p>图片来自原始 Live2D 素材。可选嘴型和 ArtMesh53 已排除。其余项目等待逐项决定。</p>']
for item in catalog['items']:body.append('<article><img src="'+item['thumbnail']+'"><div><h2>'+f"{item['id']:02} "+html.escape(item['name'])+'</h2><small>'+html.escape(item['kind'])+'</small><p>'+html.escape(item['description'])+'</p><p>选择：保留 / 删除</p></div></article>')
(out/'index.html').write_text('\n'.join(body),encoding='utf-8',newline='\n');print('BAIQI_SOURCE_COMPONENT_CATALOG',len(images),'items',len(boards),'boards; all decisions pending')
