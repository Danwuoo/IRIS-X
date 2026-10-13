"""Prepare exact acyclic consumer release bytes before entry/operator final pins."""
from pathlib import Path
import argparse,sys,types
HERE=Path(__file__).resolve().parent
p=HERE/'build_release.py';m=types.ModuleType('rlvr_exact_release_builder');m.__file__=str(p);sys.modules[m.__name__]=m
exec(compile(p.read_bytes(),str(p),'exec',dont_inherit=True),vars(m))
def main():
    a=argparse.ArgumentParser();a.add_argument('--material-review',required=True);a.add_argument('--environment',required=True);a.add_argument('--policy',required=True);a.add_argument('--source-sha',required=True);a.add_argument('--out',type=Path,required=True);a=a.parse_args()
    material=m.raw(a.material_review);environment=m.raw(a.environment);policy=m.raw(a.policy)
    need=m.need;doc=m.loader.parse(material)
    need(doc['source_sha256']==a.source_sha and doc['environment_sha256']==m.sha(environment)==m.ENVIRONMENT_SHA and doc['phase_policy_sha256']==m.sha(policy)==m.POLICY_SHA,'independently reviewed final material identity')
    need(not a.out.exists(),'fresh consumer release binding root required')
    docs,release=m.consumer_documents(material,environment,policy,a.source_sha)
    for name,raw in docs.items():m.write(a.out/(name+'.json'),raw)
    m.write(a.out/'release.json',release)
    print(m.enc({'format':'irisx/rlvr-staged-consumer-release-binding-v1','release_sha256':m.sha(m.enc(release)),'source_sha256':a.source_sha,'output':str(a.out),'provider_calls':0}).decode())
if __name__=='__main__':main()
