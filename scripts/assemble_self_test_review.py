"""Make review grids and a local index from actual rendered pose samples."""
import html, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/live2d_delta/self_test'
report=json.loads((OUT/'sampling_report.json').read_text(encoding='utf-8'))
font_path=Path('C:/Windows/Fonts/msyh.ttc')
font=ImageFont.truetype(str(font_path),28);small=ImageFont.truetype(str(font_path),22)
views={'front':'正面','side':'侧面','back':'背面','oblique':'斜前方'}
pages=[]
for clip in report['clips']:
    if not clip['images']:continue
    passes=sorted(set(i['pass'] for i in clip['images']))
    for kind in passes:
        images=[i for i in clip['images'] if i['pass']==kind]
        rows=list(dict.fromkeys(i['view'] for i in images))
        if len(images)!=15:continue
        width,height=2660,110+len(rows)*558+45
        sheet=Image.new('RGB',(width,height),(28,31,37));draw=ImageDraw.Draw(sheet)
        draw.text((96,12),clip['title']+' / '+('灰模' if kind=='clay' else '贴图'),font=font,fill='white')
        draw.text((96,53),'固定镜头、灯光与缩放；颈部正角为抬头；抬臂角度从原生 A 姿势起算',font=small,fill=(190,201,215))
        for row,name in enumerate(rows):
            draw.text((10,130+row*558),views[name],font=small,fill=(220,225,235))
            for col,sample in enumerate(clip['samples']):
                item=next(i for i in images if i['view']==name and i['sample']==col)
                x=90+col*514;y=110+row*558
                draw.text((x+8,y),sample['label']+' / f'+str(sample['frame']),font=small,fill=(230,234,242))
                with Image.open(OUT/item['path']) as image:sheet.paste(image.convert('RGB'),(x,y+38))
        draw.text((96,height-39),'用于定位形体、权重、穿插和贴图接缝；采样完成不代表外观验收通过。',font=small,fill=(239,192,125))
        name=clip['id']+'_'+kind+'.jpg';sheet.save(OUT/name,quality=93)
        pages.append((clip,kind,name))
rows=[]
for clip in report['clips']:
    if not clip['samples']:continue
    highest={region:max((s['metrics'][region]['stretch_max'],s['frame']) for s in clip['samples']) for region in ['neck','shoulder','elbow']}
    rows.append({'clip':clip['id'],'title':clip['title'],'max_edge_stretch_and_frame':highest})
(OUT/'stress_summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
body=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Delta 离线动作自测</title>',
      '<style>body{margin:32px auto;max-width:1250px;padding:0 24px;background:#181c23;color:#e9edf4;font:17px/1.6 system-ui}a{color:#86bdff}img{width:100%;border:1px solid #4a5260}section{margin:36px 0}small{color:#b9c4d4}</style>',
      '<h1>Delta 离线动作自测</h1><p>14 组独立编制的动作，70 个目标姿态。全程未启动游戏。固定镜头和灯光采样，灰模用于看形体，贴图用于看接缝。</p>',
      '<p>自测范围是为本次诊断选定的范围。抬臂角度从游戏原生 A 姿势起算；不是从手臂垂直下垂起算。边长变化只提示复查位置，不能证明模型自然。</p>',
      '<p><a href="Delta_SelfTest.blend">可播放的 Blender 动作工程</a> · <a href="sampling_report.json">全部采样参数与指标</a> · <a href="stress_summary.json">变形峰值索引</a></p>']
if (OUT/'Review.txt').exists():body.append('<p><a href="Review.txt">人工观察记录与未解决问题</a></p>')
for clip,kind,name in pages:
    body.append('<section><h2>'+html.escape(clip['title'])+' · '+('灰模' if kind=='clay' else '贴图')+'</h2><small>动作名：'+html.escape(clip['action'])+'</small><a href="'+name+'"><img loading="lazy" src="'+name+'"></a></section>')
body.append('</html>');(OUT/'index.html').write_text('\n'.join(body),encoding='utf-8')
print('SELFTEST_REVIEW_GRIDS',len(pages))
print(json.dumps(rows[:5],ensure_ascii=False))
