from fastapi.testclient import TestClient

from archive.serve.api import app

client = TestClient(app)

def _ask(case_id, vid):
    r = client.post("/ask", json={"case_id": case_id, "villager_id": vid, "question": "Where were you?"})
    assert r.status_code == 200
    return r.json()

def test_full_flow_wins():
    case = client.post("/case", json={"difficulty": "easy"}).json()
    cid = case["case_id"]
    motive = case["evidence_claims"][0]["claim_id"]
    tom = _ask(cid, "tom")["claims"][0]["claim_id"]
    gus = _ask(cid, "gus")["claims"][0]["claim_id"]
    nell = _ask(cid, "nell")["claims"][0]["claim_id"]
    for k in (tom, gus, nell, motive):
        assert client.post("/pin", json={"claim_id": k}).json()["ok"]
    assert client.post("/link", json={"claim_a": tom, "claim_b": gus}).json()["confirmed"]
    assert not client.post("/link", json={"claim_a": gus, "claim_b": nell}).json()["confirmed"]
    res = client.post("/accuse", json={"case_id": cid, "villager_id": "tom",
                                       "links": [[tom, gus], [tom, nell]], "motive_claim": motive}).json()
    assert res["correct"] and res["score"] > 0 and res["reveal"]["killer"] == "tom"

def test_red_claim_cannot_be_pinned_and_other_routes():
    cid = client.post("/case", json={"difficulty": "hard"}).json()["case_id"]
    claims = _ask(cid, "mara")["claims"]
    assert all(c["status"] == "unchecked" for c in claims)
    red = claims[1]["claim_id"]
    assert client.post("/verify", json={"claim_id": red}).json()["status"] == "unsupported"
    assert not client.post("/pin", json={"claim_id": red}).json()["ok"]
    assert client.post("/day/end", json={"case_id": cid}).json()["day"] == 2
    assert len(client.post("/rumour", json={"case_id": cid, "villager_id": "mara", "text": "x"}).json()["rounds"]) == 5
    assert client.get(f"/state/{cid}").status_code == 200
    assert client.get("/replay/demo").status_code == 200
