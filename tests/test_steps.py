from finseries.verifiers import ops, steps

R = [10, -20, 30, -40, 50, 5, -5, 100, -300, 20]
S = ops.Series(R)


def run(body, ans="0"):
    pt = steps.parse_completion(f"<think>\n{body}\n</think>\n<answer>{ans}</answer>")
    steps.check_steps(pt, S)
    return pt


def valid(pt):
    return [s.valid for s in pt.steps]


def test_valid_chain():
    pt = run("window=5\nS1: ret(0,4) = 30\nS2: ret(5,9) = -180\nS3: agg(sum,S1,S2) = -150", "-150")
    assert valid(pt) == [True, True, True] and pt.header == {"window": 5} and pt.answer == -150


def test_wrong_value_and_error_propagation():
    pt = run("S1: ret(0,4) = 31\nS2: ret(5,9) = -180\nS3: agg(sum,S1,S2) = -149")
    # S1 is wrong; S3 is consistent with the model's OWN S1,S2 so it stays valid (error is localised)
    assert valid(pt) == [False, True, True]
    assert steps.first_invalid(pt) == 0


def test_tolerance_one_percent():
    pt = run("S1: ret(0,9) = -150\nS2: vol(0,9) = 327")  # true vol 325.5; within 1%
    assert all(valid(pt))


def test_bad_lines():
    pt = run("S1: ret(0,4) = 30\nS1: ret(0,4) = 30\nS3: ret(0,40) = 5\nhello\n# a comment\nS5: foo(1,2) = 3")
    assert valid(pt) == [True, False, False, False, False]


def test_step_numbering_and_refs():
    assert valid(run("S2: ret(0,4) = 30")) == [False]
    assert valid(run("S1: ret(0,4) = 30\nS2: agg(sum,S1,S5) = 30")) == [True, False]
    assert valid(run("S1: agg(sum,S1) = 3")) == [False]


def test_duplicates_invalid():
    assert valid(run("S1: ret(0,4) = 30\nS2: ret(0,4) = 30")) == [True, False]


def test_segments_block():
    segs = S.segs
    block = "<segments>\n" + "\n".join(f"{i}:{g.text()}" for i, g in enumerate(segs)) + "\n</segments>"
    pt = run(block + "\nS1: seg_stat(0,ret) = %d" % ops.eval_prim(S, "seg_stat", [0, "ret"]))
    assert all(valid(pt)) and pt.has_segments_block
    wrong = "<segments>\n0:(0,%d,up,hv)\n</segments>" % (segs[0].end + 1)
    assert valid(run(wrong)) == [False]


def test_answer_parsing():
    assert steps.parse_completion("<think>\n</think>\n<answer>12.5</answer>").answer == 12.5
    assert steps.parse_completion("<think>\n</think>\n<answer>ABSTAIN</answer>").abstain
    p = steps.parse_completion("<think>\nS1: ret(0,1) = 1")
    assert p.truncated and p.answer is None
    p = steps.parse_completion("<think>\n</think>\n<answer>1</answer><answer>2</answer>")
    assert p.multi_answer and p.answer is None
    assert steps.parse_completion("<answer>5</answer><think>\n</think>").answer is None  # answer before think
    assert steps.parse_completion("<think>\n</think>\n<answer>1+1</answer>").answer is None
