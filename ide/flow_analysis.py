"""Bytecode control-flow and heuristic function call graph extraction."""
from __future__ import annotations
import re
from analytics import sanitize_source

INSTRUCTION = re.compile(r'^\s*(\d+)\s+([A-Za-z_]\w*)(.*)$')
TARGET = re.compile(r'->\s*(\d+)')


def bytecode_flow(listing, limit=200):
    instructions = []
    for line in listing.splitlines():
        match = INSTRUCTION.match(line)
        if match:
            target = TARGET.search(match.group(3))
            instructions.append((int(match.group(1)),match.group(2),
                                 int(target.group(1)) if target else None))
    shown = instructions[:limit]
    ids = {ip for ip,_,_ in shown}
    nodes = [(str(ip),f'{ip:04} · {op}') for ip,op,_ in shown]
    edges = []
    for pos,(ip,op,target) in enumerate(shown):
        next_ip = shown[pos+1][0] if pos+1 < len(shown) else None
        if op in ('Halt','Return'):
            continue
        if op in ('Jmp','Jz') and target in ids:
            edges.append((str(ip),str(target),op))
        if op != 'Jmp' and next_ip is not None:
            edges.append((str(ip),str(next_ip),'fallthrough'))
    return {'nodes':nodes, 'edges':edges, 'truncated':len(instructions)>limit,
            'method':'Exact bytecode graph for listed instructions'}


def call_graph(source):
    masked,_ = sanitize_source(source)
    matches = list(re.finditer(r'\b(?:func|proc)\s+([A-Za-z_]\w*)\s*\(',masked))
    names = {m.group(1) for m in matches}
    nodes = [('__main__','Top level')]+[(name,name+'()') for name in sorted(names)]
    edges = []
    for index, match in enumerate(matches):
        start = masked.find('{',match.end())
        if start < 0:
            continue
        depth=0
        end=len(masked)
        for i in range(start,len(masked)):
            if masked[i]=='{':
                depth+=1
            if masked[i]=='}':
                depth-=1
                if depth==0:
                    end=i+1
                    break
        body=masked[start:end]
        caller=match.group(1)
        for call in re.findall(r'\b([A-Za-z_]\w*)\s*\(',body):
            if call in names:
                edges.append((caller,call,'call'))
    # Calls from top level, omitting all defined function bodies.
    covered=list(masked)
    for match in reversed(matches):
        start=masked.find('{',match.end())
        if start<0:
            continue
        depth=0
        for i in range(start,len(masked)):
            if masked[i]=='{': depth+=1
            if masked[i]=='}':
                depth-=1
                if depth==0:
                    for j in range(match.start(),i+1):
                        covered[j]=' '
                    break
    for call in re.findall(r'\b([A-Za-z_]\w*)\s*\(',''.join(covered)):
        if call in names:
            edges.append(('__main__',call,'call'))
    return {'nodes':nodes,'edges':sorted(set(edges)),
            'truncated':False,'method':'Heuristic call graph from source symbols'}
