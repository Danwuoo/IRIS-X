"""Read-only native tokenizer byte replay; no neural model or remote assets."""
import json,hashlib
from .safe_io import Root,need,digest,is_sha

class NativeTokenCodec:
    def __init__(self,source_root):
        root=Root(source_root);name='baseline/materials/qwen14b/hf-overlay/tokenizer.json'
        path=root.member(name)
        need(path.stat().st_size<64*1024**2,'bounded native tokenizer asset')
        try:
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise ValueError('installed tokenizers required for exact offline prompt ID replay') from exc
        self.tokenizer=Tokenizer.from_file(str(path))
        self.vocab_sha256=hashlib.sha256(json.dumps(self.tokenizer.get_vocab(),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        self.asset_sha256=root.file_sha(name)
    def encode(self,text):
        need(type(text) is str and len(text)<1024**2,'bounded raw prompt text')
        return self.tokenizer.encode(text,add_special_tokens=False).ids
    def actor_prompt(self,messages):
        need(type(messages) is list and messages,'exact original target-free messages required')
        prompt=''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in messages)
        return self.encode(prompt+'<|im_start|>assistant\n<think>\n\n</think>\n\n')
    def generation(self,g,packing):
        need(g.get('tokenizer_sha256')==self.vocab_sha256,'generation actual native tokenizer vocabulary differs')
        ids=self.encode(packing['prompt'])
        need(g.get('prompt_sha256')==digest(ids) and g.get('input_tokens')==len(ids)==packing.get('prompt_tokens'),'actual native prompt token IDs/hash/count differ')
