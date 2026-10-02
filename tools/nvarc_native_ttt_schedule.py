"""Replay the pinned scalar schedule on the worker's own platform; no ML work."""
import ast
import hashlib
import json
import math
from pathlib import Path
import platform
import struct
import sys


SOURCES={
    'transformers/training_args.py':'d9aa07fe3d38b1e9d5dac822f21a6012361865d5b55904eb5edc65d46a410e5d',
    'transformers/optimization.py':'41b08ffb29c2691626b225ed389a694cc8e61480818214a35f215b5c39167bfb'}
FUNCTIONS={
    'get_warmup_steps':'83a90e8c1e78cc6fd3e75e72f9ca4969281a8f9b97a86d2374c641b53e727b45',
    '_get_cosine_schedule_with_warmup_lr_lambda':'187384f16375475fcd872a02c7879c16713d5f99e558f3b72d1a334d359db5d9'}


def require(value,message):
    if not value:raise RuntimeError(message)


def ulp_distance(a,b):
    require(type(a) in (int,float) and type(b) in (int,float) and
        math.isfinite(a) and math.isfinite(b) and a>=0 and b>=0,'finite nonnegative schedule rates required')
    if a==0 or b==0:return 0 if a==b else math.inf
    return abs(struct.unpack('>Q',struct.pack('>d',a))[0]-struct.unpack('>Q',struct.pack('>d',b))[0])


def source_functions(dependency):
    nodes=[]
    for name,expected in SOURCES.items():
        body=(Path(dependency)/name).read_bytes()
        require(hashlib.sha256(body).hexdigest()==expected,'exact native scalar source bytes required')
        source=body.decode('utf-8');tree=ast.parse(source)
        target='get_warmup_steps' if name.endswith('training_args.py') else '_get_cosine_schedule_with_warmup_lr_lambda'
        values=([node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name==target]
            if target=='get_warmup_steps' else [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==target])
        require(len(values)==(1 if target=='get_warmup_steps' else 2),'reviewed scalar binding topology required')
        node=values[-1]
        require(hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()==FUNCTIONS[target],
            'exact reviewed native scalar function required')
        nodes.append(node)
    for node in ast.walk(ast.Module(body=nodes,type_ignores=[])):
        require(not isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.With,ast.Try,ast.Raise)),
            'native scalar replay cannot import, perform IO or change globals')
        if isinstance(node,ast.Call):
            require(isinstance(node.func,ast.Name) and node.func.id in {'float','max'} or
                isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and
                node.func.value.id=='math' and node.func.attr in {'ceil','cos'},'only reviewed native scalar calls allowed')
    namespace={'math':math,'__builtins__':{'float':float,'max':max,'int':int}}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'verified-native::scalar-schedule','exec'),namespace)
    return namespace['get_warmup_steps'],namespace['_get_cosine_schedule_with_warmup_lr_lambda']


def native_schedule(dependency,arguments,reference):
    require(len(reference)==129 and arguments.learning_rate==5e-5 and arguments.warmup_ratio==.1 and
        arguments.warmup_steps==0 and arguments.num_train_epochs==1,'unchanged full native epoch schedule required')
    warmup,cosine=source_functions(dependency);warm=warmup(arguments,128)
    require(warm==13,'exact native thirteen-step warmup required')
    rates=[arguments.learning_rate*cosine(i,num_warmup_steps=warm,num_training_steps=128,num_cycles=.5) for i in range(129)]
    distances=[ulp_distance(a,b) for a,b in zip(rates,reference)]
    require(max(distances)<=4 and rates[0]==rates[-1]==0 and rates[13]==5e-5,
        'worker scalar schedule must preserve the pinned recipe within four cross-platform ULPs')
    evidence={'source_sha256':SOURCES,'function_sha256':FUNCTIONS,'warmup_steps':warm,'epoch_steps':128,
        'rates':rates,'reference_rates_sha256':hashlib.sha256(json.dumps(reference,separators=(',',':')).encode()).hexdigest(),
        'reference_ulp_distances':distances,'maximum_reference_ulp_distance':max(distances),
        'platform':platform.platform(),'python':sys.version,'model_calls':0,'optimizer_steps':0,
        'policy':'optimizer rate must exactly equal same-platform pinned scalar replay; reference differs by at most four ULPs'}
    return rates,evidence
