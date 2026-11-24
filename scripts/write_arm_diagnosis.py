"""Produce a small evidence report from the actual native animation comparisons."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/arm_audit_handrepair'
data=json.loads((OUT/'audit_report.json').read_text())
models={}
for clip in data['clips'].values():
    for sample in clip['samples']:
        for model in sample['models']:models.setdefault(model['model'],[]).append(model['posed_edge_ratio'])
metrics={name:{part:{'worst_sample_p99_edge_length_ratio':max(s[part]['stretch_p99'] for s in samples),
                     'maximum_edge_length_ratio':max(s[part]['stretch_max'] for s in samples)}
               for part in ['arms','hands']} for name,samples in models.items()}
result={'conclusion':'Observed offline arm defects primarily come from reconstructed geometry, fitting and skin weights',
        'control':'Original adult Soul and both Delta variants share one identical native armature/action',
        'skeleton_comparison':data['rest_comparison'],'clips':{n:{k:c[k] for k in ['frames','total_frames','fps']} for n,c in data['clips'].items()},
        'views':['front','three-quarter'],'comparisons':metrics,
        'identified_problems':['Initial elbow anchor was too close to the cuff, stretching the inferred forearm',
                               'Initial forearm weighting did not use the native twist bones',
                               'Nearest-point hand weights mixed incompatible finger and forearm influences',
                               'Generated fingers were fused and had no suitable bending loops'],
        'changes':['Moved source elbow anchor to image offset +/-220, y875',
                   'Transferred local native arm surface weights, retaining twist bones',
                   'Fitted the hand orientation separately from the forearm',
                   'Built new palm and five finger chains around original joint centers'],
        'remaining':['Elbow and shoulder clothing topology still gives pinching in strong bends',
                     'Wrist seam uses an overlap and needs visual review',
                     'Live weapon grip, AnimBP/IK and postprocess have not been tested',
                     'Back texture, hair, feet and clothing remain rough prototype work'],
        'game_runtime_tested':False,'young_character_modified':False,'full_jpg_used':False}
(OUT/'diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
text='''成年魂 → Delta 手臂审核（2026-11-24）

结论：已观察到的主要问题来自我们重建模型的比例、几何和蒙皮。
离线对照没有发现原版骨架的骨名、父子关系、关节位置或旋转轴错位。
这不是游戏内 IK、持武器和后处理已通过验证的声明。

方法：原版成年魂、初版 Delta、修正版 Delta 共用同一个未重定向的原版骨架，
播放本地游戏导出的待机、向前跑和白衫双刀攻击动作。每个动作抽查4帧，
分别输出正面、四分之三视角，共24张三列对照图。
左列：原版魂；中列：初版；右列：肘部/权重/五指修正版。
绿点肩、橙点肘、蓝点腕。原版身体不含独立头部，因此左列没有头。

发现与处理：
1. 初版把靠近袖口的位置估作肘部，导致前臂过度拉长；已上移肘锚点。
2. 初版前臂几乎只用主骨，缺少原版扭转骨权重；已转移原版手臂表面权重。
3. 初版手掌、前臂与手指的近邻权重混用；已独立拟合手掌方向。
4. 生成手指粘连且缺乏关节边环；已重新构建掌部和五指，绑定原版手指骨。

仍未解决：强弯曲时袖子在肘、肩处仍有挤压；手腕采用重叠接缝；
整体模型的头发、鞋、侧背面和服装仍粗糙。尚无新布料物理或脸部形变。
这些不能因为骨骼数据检查通过就认定模型制作完成。

抽样数值见 diagnosis.json。边长拉伸值用于定位蒙皮拉扯，不是视觉质量分数，
也不代表完整动作、游戏实机或所有姿态已经验收。
本次只处理 Delta.zip 对应角色和成年魂。full.jpg 未用于此模型，少年魂未修改。
'''
(OUT/'review.txt').write_text(text,encoding='utf-8-sig')
print('ARM_DIAGNOSIS_WRITTEN',len(data['clips']),'clips')
