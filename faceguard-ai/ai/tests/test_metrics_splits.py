"""Metrics are cross-checked against scikit-learn; splits are checked for identity/hash leakage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import pytest  # noqa: E402

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")  # optional AI dependency: skip, don't error, when it is absent
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score  # noqa: E402

from faceguard_ai import metrics, splits  # noqa: E402

def test_metrics_match_sklearn_and_splits_do_not_leak():
    rng=np.random.default_rng(0)
    for trial in range(50):
        n=200; y=rng.integers(0,2,n); s=np.round(rng.random(n),1)*0.5+y*0.3  # ties on purpose
        m=metrics.evaluate(y,s,0.5); p=(s>=0.5).astype(int)
        assert abs(m["roc_auc"]-roc_auc_score(y,s))<1e-9
        assert abs(m['accuracy']-accuracy_score(y,p))<1e-12
        assert abs(m['precision']-precision_score(y,p))<1e-12
        assert abs(m['recall']-recall_score(y,p))<1e-12 and abs(m['f1']-f1_score(y,p))<1e-12
        cm=confusion_matrix(y,p,labels=[0,1]); assert m['confusion_matrix']['matrix']==cm.tolist()
        tn,fp,fn,tp=cm.ravel(); assert abs(m['apcer']-fp/(fp+tn))<1e-12 and abs(m['bpcer']-fn/(fn+tp))<1e-12
        assert abs(m['acer']-(m['apcer']+m['bpcer'])/2)<1e-12
    # edge cases: missing class -> None, not 0
    m=metrics.evaluate([1,1,1],[.9,.8,.1]); assert m['apcer'] is None and m['roc_auc'] is None and m['acer'] is None
    m=metrics.evaluate([0,0],[.1,.2]); assert m['bpcer'] is None and m['recall'] is None
    # threshold selection
    y=[0]*50+[1]*50; s=list(np.linspace(0,.6,50))+list(np.linspace(.4,1,50)); t=metrics.choose_threshold_min_acer(y,s)
    assert 0.3<t<0.7, t
    # splits: identity disjoint + dedupe + determinism
    S=[]
    for i in range(40):
        for j in range(5): S.append(splits.Sample(f"p{i}_{j}.jpg", j%2, sha256=f"h{i}_{j}", identity=f"person{i}"))
    S.append(splits.Sample("dup.jpg",1,sha256="h0_0",identity="person0"))
    out,rep=splits.split(S,seed=1); splits.assert_no_leakage(out)
    assert sum(rep.counts.values())==200 and rep.identity_disjoint and not rep.warnings, rep
    out2,_=splits.split(S,seed=1); assert [s.path for s in out['test']]==[s.path for s in out2['test']]
    ids={n:{s.identity for s in v} for n,v in out.items()}
    assert not (ids['train']&ids['test']) and not (ids['train']&ids['val']) and not (ids['val']&ids['test'])
    assert all(0.55<len(out['train'])/200<0.85 for _ in [0]), rep.counts
    # leakage detector actually detects
    bad={'train':[S[0]],'test':[S[1]]}
    try: splits.assert_no_leakage(bad); raise SystemExit("leak not detected")
    except AssertionError: pass
    # no metadata -> identity_disjoint False
    _,r=splits.split([splits.Sample(f"{i}.jpg",i%2,sha256=str(i)) for i in range(30)]); assert not r.identity_disjoint
    assert splits.class_weights([0,0,0,1])=={0:4/(2*3),1:4/2} and splits.class_weights([1,1])=={}

