"""Truth-free policies: typed state, exact views, bounded local feedback and memory."""
from __future__ import annotations
import ast
import hashlib
import json
from collections import deque

MAX_SOURCE_BYTES = 32768
MAX_FEEDBACK_BYTES = 16384
MAX_MEMORY = 4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def host_contract():
    return (
        'Solve the demonstrated grid rule. Return ONLY raw source beginning with def transform(grid):. '
        'The host ALREADY provides these functions; call them directly and DO NOT redefine any of them: '
        'copy_grid(g) -> independent grid copy; new_grid(h,w,color) -> grid; transpose(g) -> transposed grid; '
        'crop(g,r0,c0,r1,c1) -> grid, exclusive ends; components(g,background,connectivity) -> list of '
        'same-color objects, each object a list of [row,column,color] pixels. Background is an evidence-based '
        'color choice; connectivity is 4 or 8. Example: objects=components(grid,0,4); first=objects[0]; '
        'a pixel is first[0], with row=first[0][0], column=first[0][1], color=first[0][2]. '
        'Do not implement flood fill or redefine components/copy_grid. '
        'Other host primitives: list, len, range, enumerate, zip, min/max/sum/sorted/reversed/unique '
        '(one integer-list argument), abs, append(xs,x). '
        'Allowed language: integers/bools/None, lists/tuples, indexing/slices, + - * // %, comparisons, '
        'is/is not, booleans, if, for, while, list/eager generator comprehensions, lexical break/continue, '
        'return, explicit assignment, named helpers. Only exact-list .append(x), .pop([index]), '
        '.extend(xs) method calls. No imports, general attributes, strings/dicts/sets, += or other '
        'augmented assignments, nested functions, exceptions, async, lambda, powers, host APIs, prose or fences. '
        'Use ordinary variable names (the single underscore is allowed). Source <=32768 bytes, '
        '<=2048 AST nodes, <=8 functions, <=128 locals, <=12 call depth, <=16384 recursive value items, '
        '<=16 value depth, integers magnitude <=1000000, <=200000 total demo/query interpreter steps. '
        'Return a rectangular 1..30 grid of exact integer colors 0..9. Fit every demonstration with one program.\n'
    )


def _grid_view(g):
    h, w = len(g), len(g[0]); counts = [0]*10
    for row in g:
        for c in row: counts[c] += 1
    views = {}
    for connectivity in (4,8):
        seen = set(); objects = []
        for r in range(h):
            for c in range(w):
                if (r,c) in seen: continue
                color = g[r][c]; queue = deque([(r,c)]); seen.add((r,c)); pixels = []
                while queue:
                    rr,cc = queue.popleft(); pixels.append((rr,cc))
                    for dr in (-1,0,1):
                        for dc in (-1,0,1):
                            if not (dr or dc) or (connectivity==4 and dr and dc): continue
                            nr,nc=rr+dr,cc+dc
                            if 0<=nr<h and 0<=nc<w and (nr,nc) not in seen and g[nr][nc]==color:
                                seen.add((nr,nc));queue.append((nr,nc))
                objects.append({'color':color,'size':len(pixels),'bbox':[min(x[0] for x in pixels),min(x[1] for x in pixels),max(x[0] for x in pixels)+1,max(x[1] for x in pixels)+1]})
        objects.sort(key=lambda x:(-x['size'],x['color'],x['bbox']))
        views[str(connectivity)]={'total_objects':len(objects),'largest_objects':[[x['color'],x['size'],*x['bbox']] for x in objects[:12]],
                                  'omitted_objects':max(0,len(objects)-12)}
    row_runs=sum(1+sum(row[i]!=row[i-1] for i in range(1,w)) for row in g)
    column_runs=sum(1+sum(g[r][c]!=g[r-1][c] for r in range(1,h)) for c in range(w))
    return {'shape':[h,w],'color_counts':counts,'row_run_count':row_runs,'column_run_count':column_runs,
            'components_all_colors_including_zero':views}


def object_view(task):
    return {'format':'exact-visible-view-v1','background_inferred':False,
            'component_cap':12,'object_tuple_fields':['color','size','r0','c0','r1_exclusive','c1_exclusive'],'raw_grids_remain_complete':True,
            'train':[{'input':_grid_view(p['input']),'output':_grid_view(p['output'])} for p in task['train']],
            'query_input':_grid_view(task['test'][0]['input'])}


def initial_messages(task, policy, *, detailed_contract, ir_contract):
    allowed={'direct_grid','detailed_contract','host_toolbox','host_python','typed_ir','proposal_pool','generic_static','precise_static','raw_grid','raw_plus_objects','redacted_demo','true_demo','independent_roots','best_first_memory'}
    if policy not in allowed:raise ValueError('Unknown exact policy ID')
    if policy=='direct_grid':
        instruction='Infer the grid transformation from the demonstrations. Return only the complete output grid as a JSON array of integer rows, without explanation.\n'
    elif policy=='detailed_contract': instruction=detailed_contract()
    elif policy in ('typed_ir','proposal_pool'): instruction=ir_contract()
    else: instruction=host_contract()
    content=instruction+'\nDemonstrations:\n'+canonical(task['train']).decode()+'\nQuery input:\n'+canonical(task['test'][0]['input']).decode()
    if policy=='raw_plus_objects': content+='\nExact deterministic auxiliary view (all colors; largest12 components per connectivity; omitted counts explicit):\n'+canonical(object_view(task)).decode()
    return [{'role':'user','content':content}]


def valid_feedback(feedback):
    if type(feedback) is not dict or set(feedback)!={'error','demonstrations','all_demonstrations_exact'}:
        raise ValueError('Only visible-demo feedback schema permitted')
    if len(canonical(feedback))>MAX_FEEDBACK_BYTES: raise ValueError('No feedback truncation permitted')
    return json.loads(canonical(feedback))


def static_failed(result):
    return not result.get('ast_admitted')


def fit_key(row):
    """Select a parent without query status, prediction or evaluator truth."""
    result=row['result'];feedback=valid_feedback(result['feedback']); demos=feedback['demonstrations']
    exact=sum(x['exact'] for x in demos)
    assessed=len(demos)
    cells=sum((x['target_shape'][0]*x['target_shape'][1]) for x in demos if x['shape_match'])
    matches=sum(x['target_shape'][0]*x['target_shape'][1]-x['mismatch_count'] for x in demos if x['shape_match'])
    return (int(result.get('all_demonstrations_exact') is True),exact,assessed,
            (matches/cells if cells else 0.0),int(result.get('ast_admitted') is True),-row['identity']['call_index'])


def repair_messages(initial, parent, *, policy, archive):
    source=parent['response']['text']
    if type(source) is not str or len(source.encode())>MAX_SOURCE_BYTES:
        raise ValueError('Prior source exceeds repair byte cap; never truncate')
    feedback=valid_feedback(parent['result']['feedback'])
    static=static_failed(parent['result'])
    if policy=='generic_static':
        feedback={'error':('invalid Python syntax' if not parent['result'].get('python_parse_admitted') else 'unsupported syntax'),
                  'demonstrations':[],'all_demonstrations_exact':False}
    elif policy=='precise_static':
        feedback={'error':feedback['error'],'demonstrations':[],'all_demonstrations_exact':False}
    elif policy=='redacted_demo' and not static:
        feedback={'error':'Demonstration checking details withheld in this control. Reconsider the same task.',
                  'demonstrations':[],'all_demonstrations_exact':False}
    instruction='Return a complete replacement raw source beginning with def. The host toolbox and bounded language are unchanged.\nVisible-only checks:\n'+canonical(feedback).decode()
    if policy=='best_first_memory':
        memory=[]
        for old in archive[-MAX_MEMORY:]:
            result=old['result'];f=valid_feedback(result['feedback'])
            memory.append({'source_sha256':hashlib.sha256(old['response']['text'].encode()).hexdigest(),
                           'ast_admitted':result['ast_admitted'],'demo_exact':[r['exact'] for r in f['demonstrations']],
                           'error':f['error'],'readable_source_signature':source_signature(old['response']['text']),
                           'demo_shapes_and_mismatches':[{'predicted_shape':r['predicted_shape'],'target_shape':r['target_shape'],'mismatch_count':r['mismatch_count']} for r in f['demonstrations']]})
        instruction+='\nBounded candidate memory; avoid repeating the same failed hypothesis:\n'+canonical(memory).decode()
    return json.loads(canonical(initial))+[{'role':'assistant','content':source},{'role':'user','content':instruction}]


def next_messages(initial, policy, archive):
    if not archive: return initial,None
    last=archive[-1]
    if policy in ('generic_static','precise_static'):
        if not static_failed(last['result']): return initial,None
        parent=last
    elif policy in ('redacted_demo','true_demo'):
        if last['result'].get('all_demonstrations_exact'): return initial,None
        parent=last
    elif policy=='best_first_memory':
        if last['result'].get('all_demonstrations_exact'): return initial,None
        # Every third proposal is a fresh restart; otherwise best visible parent.
        if len(archive)==2: return initial,None
        parent=max(archive,key=fit_key)
    else:return initial,None
    return repair_messages(initial,parent,policy=policy,archive=archive),parent['identity']['record_id']


def source_metadata(source):
    if type(source) is not str or len(source.encode())>MAX_SOURCE_BYTES: return {'source_bounded':False}
    try: tree=ast.parse(source)
    except (SyntaxError,ValueError,MemoryError,RecursionError): return {'source_bounded':True,'parsed':False}
    owned={'copy_grid','new_grid','transpose','crop','components','list','len','range','enumerate','zip','min','max','sum','sorted','reversed','unique','abs','append'}
    names=[n.name for n in tree.body if isinstance(n,ast.FunctionDef)]
    return {'source_bounded':True,'parsed':True,'redefined_host_primitives':sorted(set(names)&owned),
            'source_bytes':len(source.encode()),'ast_nodes':sum(1 for _ in ast.walk(tree))}


def source_signature(source):
    if type(source) is not str or len(source.encode())>MAX_SOURCE_BYTES:return {'status':'oversize'}
    try:tree=ast.parse(source)
    except (SyntaxError,ValueError,RecursionError,MemoryError):return {'status':'unparsed'}
    nodes=list(ast.walk(tree))
    operations=sorted({n.func.id if isinstance(n.func,ast.Name) else 'list.'+n.func.attr for n in nodes if isinstance(n,ast.Call) and isinstance(n.func,(ast.Name,ast.Attribute))})
    constants=sorted({n.value for n in nodes if isinstance(n,ast.Constant) and type(n.value) is int})
    operators=sorted({type(n).__name__ for n in nodes if isinstance(n,(ast.operator,ast.cmpop,ast.boolop,ast.unaryop))})
    return {'status':'parsed','operations':operations[:16],'operations_omitted':max(0,len(operations)-16),
            'integer_constants':constants[:16],'constants_omitted':max(0,len(constants)-16),'operators':operators[:16]}
