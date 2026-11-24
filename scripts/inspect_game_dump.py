"""Read exception/module metadata from a local minidump, excluding private data."""
import json
from pathlib import Path
import struct
ROOT=Path(__file__).resolve().parents[1]
folder=Path(r'C:\Users\xenoa\AppData\Local\ProjectPBZ\Saved\PBZCrashes\reports')
path=max(folder.glob('*.dmp'),key=lambda p:p.stat().st_mtime)
blob=path.read_bytes();assert blob[:4]==b'MDMP'
_,_,count,directory=struct.unpack_from('<4I',blob)
streams={}
for index in range(count):
    kind,size,rva=struct.unpack_from('<III',blob,directory+index*12);streams[kind]=(size,rva)
def string(rva):
    size=struct.unpack_from('<I',blob,rva)[0]
    return blob[rva+4:rva+4+size].decode('utf-16-le',errors='replace')
modules=[]
if 4 in streams:
    _,rva=streams[4];number=struct.unpack_from('<I',blob,rva)[0]
    for index in range(number):
        base,size,_,_,name_rva=struct.unpack_from('<QIIII',blob,rva+4+108*index)
        modules.append({'base':base,'size':size,'name':Path(string(name_rva)).name})
record={}
if 6 in streams:
    _,rva=streams[6]
    thread,_,code,flags,nested,address,parameters,_=struct.unpack_from('<IIIIQQII',blob,rva)
    details=list(struct.unpack_from('<15Q',blob,rva+40))[:parameters]
    module=next((m for m in modules if m['base']<=address<m['base']+m['size']),None)
    record={'thread':thread,'exception_code':hex(code),'address':hex(address),'parameters':[hex(p) for p in details],
            'module':module['name'] if module else None,'module_offset':hex(address-module['base']) if module else None}
report={'dump':path.name,'streams':sorted(streams),'exception':record,'module_count':len(modules)}
(ROOT/'artifacts/runtime_review/latest_exception.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
