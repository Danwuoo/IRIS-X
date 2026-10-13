"""Qwen probe-only fixed decoder. Shared Granite implementation is untouched."""
from copy import deepcopy
import hashlib
import math
import time
from .protocol import digest,require
from tools.arc_learning_agent_20261011.qwen14b_model import Qwen14BModel
from tools.arc_learning_agent_20261011.native_model import _require,_digest,_decode,ContextLimitError


def cache_length(cache, config=None, device=None):
    require(cache is not None and callable(getattr(cache,'get_seq_length',None)), 'native dynamic cache missing')
    value=int(cache.get_seq_length())
    layers=getattr(cache,'layers',None)
    require(layers is not None and len(layers)>0,'native cache layer inventory missing')
    lengths=[int(layer.get_seq_length()) for layer in layers]
    require(all(x==value for x in lengths),'cache layer lengths disagree')
    if config is not None:
        require(len(layers)==config.num_hidden_layers,'cache layer count differs')
        for layer in layers:
            expected=[1,config.num_key_value_heads,value,config.head_dim]
            require(list(layer.keys.shape)==list(layer.values.shape)==expected,'native cache K/V shape differs')
            require(str(layer.keys.dtype)==str(layer.values.dtype)=='torch.bfloat16','native cache K/V must remain BF16')
            require(layer.keys.device==layer.values.device and (device is None or layer.keys.device==device),'native cache K/V device differs')
    return value


def cache_metadata(cache,config):
    return [{'layer':i,'key_shape':list(l.keys.shape),'value_shape':list(l.values.shape),
             'dtype':str(l.keys.dtype),'device':str(l.keys.device)} for i,l in enumerate(cache.layers)]


class InvalidCandidateError(ValueError):
    pass


class ProbeModel(Qwen14BModel):
    decoder_policy=None
    _decoder_policy_sha256=None

    def assert_decoder_policy(self):
        if self.decoder_policy is not None:
            require(digest(self.decoder_policy)==self._decoder_policy_sha256,'immutable decoder policy changed')
            require(self.identity.get('decoder_policy')==self.decoder_policy,'decoder identity policy changed')
            require(self.identity.get('decoder_policy_sha256')==self._decoder_policy_sha256,'decoder identity changed')

    def lock_decoder_policy(self,policy):
        require(self.decoder_policy is None,'decoder policy already chosen; switching forbidden')
        require(policy['selected_mode'] in ('cached','full_prefix'),'executable decoder policy required')
        self.decoder_policy=deepcopy(policy);self._decoder_policy_sha256=digest(policy)
        self.identity['decoder_policy_sha256']=self._decoder_policy_sha256
        self.identity['decoder_policy']=deepcopy(policy)
        self.assert_decoder_policy()

    def _base_receipt(self,start):
        self.assert_decoder_policy()
        r=super()._base_receipt(start)
        mode=self.decoder_policy['selected_mode'] if self.decoder_policy else 'full_prefix'
        return {**r,'decoder_mode':mode,'decoder_policy_sha256':self._decoder_policy_sha256,
            'decoder_selection_phase':'locked' if self.decoder_policy else 'preflight-reference',
            'kv_cache_policy':'call-local-discarded-after-every-generation' if mode=='cached' else 'disabled-full-prefix-every-forward'}

    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        start = time.monotonic()
        receipt = {"text": "", "input_tokens": 0, "output_tokens": 0, "output_token_ids": [],
                   "prompt_sha256": None, "finish_reason": "rejected", "elapsed_seconds": 0.0, "valid": False,
                   "forward_calls": 0, "forward_input_tokens": 0,
                "dispatched": False, "model_forward_started": False}
        old_training = None
        try:
            self._open()
            self.assert_decoder_policy()
            mode = self.decoder_policy["selected_mode"] if self.decoder_policy is not None else "full_prefix"
            receipt.update(self._base_receipt(start))
            _require(kind in {"grid", "program"}, "generation kind must be grid or program")
            _require(type(seed) is int and 0 <= seed < 2**63, "bounded integer sampling seed required")
            _require(type(max_new_tokens) is int and 0 < max_new_tokens <= self.output_cap,
                     "requested output token cap exceeds admitted bound")
            if not self._deadline(deadline):
                receipt.update(finish_reason="deadline", error="deadline expired before admission")
                return receipt
            rendered, prompt = self._prompt(messages)
            receipt.update(input_tokens=len(prompt), prompt_sha256=_digest(prompt),
                           rendered_prompt_sha256=hashlib.sha256(rendered.encode()).hexdigest(), seed=seed,
                           decoding_mode="native-rectangular-grid-DFA" if kind == "grid" else "unconstrained-native-program-text",
                           constraint_sha256=self.constraint.receipt["constraint_sha256"] if kind == "grid" else None)
            if len(prompt) + max_new_tokens > self.context_limit:
                raise ContextLimitError("prompt plus reserved output exceeds context cap")
            import torch
            device = next(self.model.parameters()).device
            generator = torch.Generator(device=device).manual_seed(seed)
            do_sample = self.config.get("do_sample", True)
            temperature = self.config.get("temperature", 1.0)
            top_p = self.config.get("top_p", 1.0)
            _require(type(do_sample) is bool and type(temperature) in (int, float) and math.isfinite(temperature)
                     and temperature > 0 and type(top_p) in (int, float) and 0 < top_p <= 1,
                     "invalid sampling configuration")
            receipt["sampling"] = {"do_sample": do_sample, "temperature": temperature, "top_p": top_p}
            old_training = self.model.training
            self.model.eval()
            sequence = list(prompt)
            past = None
            with torch.inference_mode():
                for _ in range(max_new_tokens):
                    if not self._deadline(deadline):
                        receipt.update(finish_reason="deadline", error="generation deadline reached")
                        break
                    suffix = receipt["output_token_ids"]
                    allowed = self.constraint.allowed_tokens(suffix) if kind == "grid" else None
                    forward_ids = sequence if mode == "full_prefix" or past is None else sequence[-1:]
                    inputs = torch.tensor([forward_ids], dtype=torch.long, device=device)
                    mask = torch.ones((1, len(sequence)), dtype=torch.long, device=device)
                    receipt["dispatched"] = receipt["model_forward_started"] = True
                    receipt["forward_calls"] += 1
                    receipt["forward_input_tokens"] += len(forward_ids)
                    cache_before = cache_length(past,self.model.config,device) if past is not None else 0
                    _require(mode == "full_prefix" or cache_before == len(sequence)-len(forward_ids), "generation cache length/position differs")
                    positions = torch.arange(len(sequence)-len(forward_ids), len(sequence), device=device)
                    forward_started=time.monotonic()
                    result = self.model(input_ids=inputs, attention_mask=mask, past_key_values=past if mode == "cached" else None,
                                        position_ids=positions.unsqueeze(0), cache_position=positions,
                                        use_cache=mode == "cached", logits_to_keep=1)
                    if device.type == "cuda": torch.cuda.synchronize(device)
                    forward_completed=time.monotonic()
                    logits = result.logits[0, -1].float()
                    trace={"input_tokens":len(forward_ids),"attention_mask_tokens":len(sequence),
                        "position_start":int(positions[0]),"position_end":int(positions[-1]),"cache_before":cache_before,
                        "cache_after":None,"use_cache":mode=="cached","started_monotonic":forward_started,
                        "completed_monotonic":forward_completed,"deadline_monotonic":deadline,
                        "late":forward_completed>=deadline,"finite_full_head":logits.numel()==self.vocab_size and bool(torch.isfinite(logits).all())}
                    receipt.setdefault("forward_trace",[]).append(trace)
                    _require(logits.numel() == self.vocab_size and bool(torch.isfinite(logits).all()),
                             "native full-head logits missing/nonfinite")
                    past = getattr(result, "past_key_values", None) if mode == "cached" else None
                    _require(mode == "full_prefix" or cache_length(past,self.model.config,device) == len(sequence), "generation cache did not grow exactly")
                    trace['cache_after']=cache_length(past,self.model.config,device) if past is not None else None
                    _require(mode=='cached' or getattr(result,'past_key_values',None) is None,'full-prefix unexpectedly returned cache')
                    if allowed is not None:
                        selected = torch.tensor(allowed, dtype=torch.long, device=device)
                        logits = logits.index_select(0, selected)
                    else:
                        selected = torch.arange(self.vocab_size, device=device)
                    # Deadline includes forward completion; no later token gets accepted.
                    if not self._deadline(deadline):
                        receipt.update(finish_reason="deadline", error="forward completed after generation deadline")
                        break
                    if do_sample:
                        probabilities = torch.softmax(logits / temperature, dim=-1)
                        if top_p < 1:
                            sorted_p, positions = probabilities.sort(descending=True)
                            keep = sorted_p.cumsum(-1) - sorted_p < top_p
                            sorted_p = sorted_p * keep
                            sampled = positions[torch.multinomial(sorted_p / sorted_p.sum(), 1, generator=generator)[0]]
                        else:
                            sampled = torch.multinomial(probabilities, 1, generator=generator)[0]
                        token_id = int(selected[sampled].item())
                    else:
                        token_id = int(selected[logits.argmax()].item())
                    if not self._deadline(deadline):
                        receipt.update(finish_reason="deadline",error="token selection completed after deadline")
                        break
                    suffix.append(token_id)
                    sequence.append(token_id)
                    receipt["output_tokens"] = len(suffix)
                    if token_id in self.eos_ids:
                        receipt["finish_reason"] = "eos"
                        break
                    if kind == "grid":
                        self.constraint.prefix_state(suffix)
                else:
                    receipt["finish_reason"] = "length"
            ids = receipt["output_token_ids"]
            content = ids[:-1] if ids and ids[-1] in self.eos_ids else ids
            receipt["text"] = _decode(self.tokenizer, content)
            receipt["output_sha256"] = _digest(ids)
            if receipt["finish_reason"] == "eos":
                if kind == "grid":
                    receipt["text"] = self.constraint.validate_completion(ids)
                if not receipt["text"]:raise InvalidCandidateError("empty native completion")
                if not self._deadline(deadline):
                    receipt.update(finish_reason="deadline", error="generation validation completed after deadline")
                else:
                    receipt["valid"] = True
            else:
                receipt.setdefault("error", "native completion lacks terminal EOS")
        except Exception as exc:
            receipt.update(valid=False, error=type(exc).__name__ + ": " + str(exc)[:512])
            if isinstance(exc, InvalidCandidateError):
                receipt["finish_reason"]="invalid_content"
            elif isinstance(exc, ContextLimitError):
                receipt["finish_reason"] = "context_excluded"
            else:
                receipt["finish_reason"] = "error"
        finally:
            if old_training is not None:
                self.model.train(old_training)
            receipt["elapsed_seconds"] = time.monotonic() - start
        if receipt['valid'] and kind == 'program':
            try:
                self.prompt_contract._content_ids(receipt['text'])
                content_ids=receipt['output_token_ids'][:-1];registered=set(self.tokenizer.get_vocab().values())
                _require(all(t in registered for t in content_ids) and not set(content_ids)&self.prompt_contract._control_ids,
                         'unregistered/reserved native program token IDs')
            except ValueError as exc:receipt.update(valid=False,finish_reason='invalid_content',error=str(exc))
        if receipt['valid'] and not self._deadline(deadline):receipt.update(valid=False,finish_reason='deadline',error='final validation completed after deadline')
        receipt['fatal_error']=receipt.get('finish_reason') in ('error','deadline')
        receipt['elapsed_seconds']=time.monotonic()-start
        return receipt

