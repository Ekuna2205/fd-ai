"""Challenge state machine: pure logic, loaded directly so the test needs neither FastAPI nor a database."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location("challenge", Path(__file__).parents[1] / "app" / "services" / "challenge.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["challenge"] = m
_spec.loader.exec_module(m)
C, K, O = m.Config(), m.Kind, m.Observation


def run(seq, frames, cfg=C):
    s=m.ChallengeSession(cfg, seq); 
    for f in frames: s.feed(f)
    return s

def test_challenge_engine():
    # blink: open, open, closed, closed, open
    blink=[O(i*.1,1,e,0.0) for i,e in enumerate([.3,.3,.15,.15,.3])]
    assert run([K.BLINK],blink).outcome=="PASSED"
    # eyes closed from the start and staying closed (e.g. photo with closed eyes) -> no pass
    assert run([K.BLINK],[O(i*.1,1,.1,0.0) for i in range(30)]).outcome is None
    # static open eyes -> no pass
    assert run([K.BLINK],[O(i*.1,1,.3,0.0) for i in range(30)]).outcome is None
    # closed during large head turn doesn't count
    assert run([K.BLINK],[O(i*.1,1,e,0.8) for i,e in enumerate([.3,.3,.15,.15,.3])]).outcome is None
    # turn left (mirrored display => image yaw positive)
    tl=[O(i*.1,1,.3,y) for i,y in enumerate([0,0,.2,.4,.5,.5])]
    assert run([K.TURN_LEFT],tl).outcome=="PASSED"
    assert run([K.TURN_RIGHT],tl).outcome is None            # wrong direction doesn't pass
    tr=[O(i*.1,1,.3,y) for i,y in enumerate([0,0,-.2,-.4,-.5,-.5])]
    assert run([K.TURN_RIGHT],tr).outcome=="PASSED"
    # pre-turned head (never neutral) can't pass
    assert run([K.TURN_LEFT],[O(i*.1,1,.3,.6) for i in range(10)]).outcome is None
    # single-frame spike doesn't pass (hold_frames=2)
    assert run([K.TURN_LEFT],[O(0,1,.3,0),O(.1,1,.3,.6),O(.2,1,.3,0),O(.3,1,.3,0)]).outcome is None
    # timeout
    s=run([K.BLINK],[O(0,1,.3,0),O(9,1,.3,0)]); assert s.outcome=="TIMED_OUT" and s.can_retry()
    s.retry(); assert s.attempt==2 and not s.finished
    for f in [O(20+i*.1,1,e,0) for i,e in enumerate([.3,.3,.15,.15,.3])]: s.feed(f)
    assert s.outcome=="PASSED"
    # retry limit
    s=run([K.BLINK],[O(0,1,.3,0),O(9,1,.3,0)]); s.retry(); s.feed(O(100,1,.3,0)); s.feed(O(120,1,.3,0)); assert s.outcome=="TIMED_OUT" and not s.can_retry()
    # multiple faces / no face resets progress and never passes
    s=m.ChallengeSession(C,[K.BLINK])
    for f in [O(0,1,.3,0),O(.1,1,.15,0),O(.2,2,None,None),O(.3,1,.3,0)]: s.feed(f)
    assert s.outcome is None
    # sequence of two
    s=run([K.BLINK,K.TURN_LEFT], blink+[O(1+i*.1,1,.3,y) for i,y in enumerate([0,0,.3,.5,.5])]); assert s.outcome=="PASSED", s.progress()
    # random sequence: deterministic by seed, no immediate repeats
    a=m.make_sequence(m.Config(sequence_length=6),seed=3); assert a==m.make_sequence(m.Config(sequence_length=6),seed=3)
    assert all(x!=y for x,y in zip(a,a[1:])) and m.make_sequence(m.Config(sequence_length=1,allowed=(K.BLINK,)),1)==[K.BLINK]
    # geometry: synthetic 68 landmarks
    def lm(ear_h=.3, nose_x=.5):
        p=[(0.5,0.5)]*68
        p=list(p); p[0]=(0.2,.5); p[16]=(0.8,.5); p[30]=(0.2+0.6*nose_x,.55)
        for base in (36,42):
            x0=0.3 if base==36 else 0.55
            p[base]=(x0,.4); p[base+3]=(x0+.1,.4)
            p[base+1]=(x0+.03,.4-ear_h*.05); p[base+5]=(x0+.03,.4+ear_h*.05); p[base+2]=(x0+.07,.4-ear_h*.05); p[base+4]=(x0+.07,.4+ear_h*.05)
        return p
    e,y=m.measure(lm(.3,.5)); assert abs(y)<1e-9 and abs(e-0.3*.1/.1*.5*.1/.1*1)>=0 
    e1,_=m.measure(lm(.3)); e2,_=m.measure(lm(.1)); assert e1>e2>0
    _,y=m.measure(lm(nose_x=.9)); assert y>.7
    try: m.measure([(0,0)]*10); raise AssertionError("no error")
    except ValueError: pass
    assert "does not prove" in m.verdict_note("PASSED")

