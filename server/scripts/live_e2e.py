"""Opt-in real-provider E2E checks; leaves synthetic records for UI inspection.

Run from server: uv run python scripts/live_e2e.py
Only the temporary deletion fixture is removed. Never touches existing records.
Secrets are loaded by Settings and are never written into the JSON report.
"""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "server/tests/fixtures/live"
REPORT = ROOT / "server/live-e2e-report.json"
STORAGE_ONLY = "--storage-only" in sys.argv
RESUME_REPORT = REPORT
if STORAGE_ONLY:
    REPORT = ROOT / "server/live-e2e-storage-report.json"
checks = []
created = []
run_id = uuid.uuid4().hex[:8]
if "--resume" in sys.argv and (REPORT.exists() or RESUME_REPORT.exists()):
    previous = json.loads((REPORT if REPORT.exists() else RESUME_REPORT).read_text())
    created = previous["documents"]
    run_id = previous["run_id"]


def check(name, condition, detail=None):
    checks.append({"name": name, "passed": bool(condition), "detail": detail})
    print(f"{'PASS' if condition else 'FAIL'} {name}", flush=True)
    REPORT.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "storage_only": STORAGE_ONLY,
                "checks": checks,
                "documents": created,
            },
            indent=2,
        )
    )
    if not condition:
        raise AssertionError(f"Failed: {name}; {detail}")


def stream(client, agent, docs, question, session=None):
    payload = {"agent_id": agent, "document_ids": docs, "message": question}
    if session:
        payload["session_id"] = session
    events = []
    with client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
        response.raise_for_status()
        event = "message"
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                events.append((event, json.loads(line[6:])))
    check(
        "SSE completed without provider error",
        any(e == "done" for e, _ in events) and not any(e == "error" for e, _ in events),
        events[-1],
    )
    answer = "".join(d["token"] for e, d in events if e == "token")
    citations = next((d["citations"] for e, d in events if e == "citations"), [])
    session_id = next(d["session_id"] for e, d in events if e == "session")
    return answer, citations, session_id


def upload(client, agent, filename, *, temporary=False):
    upload_name = f"e2e-{run_id}-{'temporary-' if temporary else ''}{filename}"
    for doc in created:
        if not temporary and doc["filename"] == upload_name and not doc.get("deleted"):
            print(f"Reuse synthetic fixture {doc['filename']}", flush=True)
            return doc["id"]
    with (FIXTURES / filename).open("rb") as source:
        response = client.post(
            "/api/v1/documents/upload",
            data={"agent_id": agent},
            files={"file": (upload_name, source, "text/plain")},
        )
    check(f"Upload/index {filename}", response.status_code == 201, response.json())
    data = response.json()
    created.append({"id": data["document_id"], "agent_id": agent, "filename": data["filename"]})
    check(
        f"Chunks/entities {filename}",
        data["chunks_indexed"] > 0 and data["entities_extracted"] >= 0,
        data,
    )
    chunks = client.get(f"/api/v1/documents/{data['document_id']}/chunks").json()
    check(
        f"Durable source chunks {filename}",
        bool(chunks) and all(c["document_id"] == data["document_id"] for c in chunks),
    )
    return data["document_id"]


async def verify_retrieval(cases, domain_docs, agents):
    from app.db.postgres import AsyncSessionLocal, engine
    from app.db.qdrant_client import qdrant_service
    from app.rag.bm25_search import bm25_retriever
    from app.rag.fusion import rrf_fusion
    from app.rag.reranker import reranker
    from app.rag.vector_search import vector_retriever

    try:
        async with AsyncSessionLocal() as db:
            for domain, _, question, _ in cases:
                ids = domain_docs[domain]
                vectors = await vector_retriever.retrieve(question, agents[domain], ids)
                check(
                    f"Real semantic retrieval {domain}",
                    bool(vectors) and all(c["document_id"] in ids for c in vectors),
                )
                lexical = await bm25_retriever.retrieve(
                    query=question, db_session=db, agent_id=agents[domain], document_ids=ids
                )
                check(
                    f"Real lexical retrieval {domain}",
                    bool(lexical) and all(c["document_id"] in ids for c in lexical),
                )
                fused = rrf_fusion.fuse({"vector": vectors, "bm25": lexical}, top_k=15)
                ranked = await asyncio.to_thread(
                    reranker.rerank, query=question, candidates=fused, top_k=5
                )
                check(
                    f"Real fusion/reranking {domain}",
                    bool(ranked)
                    and all(c["document_id"] in ids and "rerank_score" in c for c in ranked),
                )
    finally:
        await qdrant_service.close()
        await engine.dispose()


def main():
    settings = get_settings()
    key = next(iter(settings.API_KEYS.values()))
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=240) as client:
        check(
            "All storage services healthy", client.get("/health").json().get("status") == "healthy"
        )
        check("Unauthenticated access blocked", client.get("/api/v1/documents").status_code == 401)
        check(
            "Invalid access key blocked",
            client.post("/api/v1/auth/session", json={"api_key": "e2e-invalid"}).status_code == 401,
        )
        auth = client.post(
            "/api/v1/auth/session",
            json={"api_key": key},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        check(
            "Cookie login",
            auth.status_code == 200 and "httponly" in auth.headers.get("set-cookie", "").lower(),
        )
        check("Cookie identity", client.get("/api/v1/auth/session").status_code == 200)
        check(
            "Untrusted cookie mutation blocked",
            client.post(
                "/api/v1/chat/sessions", json={}, headers={"Origin": "https://untrusted.invalid"}
            ).status_code
            == 403,
        )
        agents = {a["domain_key"]: a["id"] for a in client.get("/api/v1/agents").json()}
        check(
            "Four specialties available",
            set(agents) >= {"cardiology", "gynaecology", "general_medicine", "neurology"},
        )
        card = agents["cardiology"]
        check(
            "Unsupported upload rejected",
            client.post(
                "/api/v1/documents/upload",
                data={"agent_id": card},
                files={"file": ("bad.exe", b"test")},
            ).status_code
            == 400,
        )
        check(
            "Empty question rejected",
            client.post("/api/v1/chat/stream", json={"agent_id": card, "message": ""}).status_code
            == 422,
        )
        cases = [
            (
                "cardiology",
                ["cardiology-baseline.txt", "cardiology-followup.md"],
                "Compare baseline and follow-up LVEF and metoprolol doses. Give exact values and dates, cite each source. Do not give treatment advice.",
                ["42", "51", "25", "50"],
            ),
            (
                "gynaecology",
                ["gynaecology.txt"],
                "Summarize recorded haemoglobin and ferritin changes and the fibroid size, with exact values and citations. Do not give treatment advice.",
                ["9.8", "11.1", "3.2"],
            ),
            (
                "general_medicine",
                ["general-medicine.txt"],
                "Compare recorded HbA1c and fasting glucose over time, with exact values and citations. Do not give treatment advice.",
                ["8.4", "7.2", "172", "132"],
            ),
            (
                "neurology",
                ["neurology.txt"],
                "Compare recorded headache days and topiramate doses over time, with exact values and citations. Do not give treatment advice.",
                ["12", "5", "25", "50"],
            ),
        ]
        domain_docs = {}
        for domain, filenames, question, facts in cases:
            print(f"Testing real providers: {domain}", flush=True)
            ids = [upload(client, agents[domain], f) for f in filenames]
            domain_docs[domain] = ids
            if STORAGE_ONLY:
                listed = client.get("/api/v1/documents", params={"agent_id": agents[domain]}).json()
                check(
                    f"Completed document listing {domain}",
                    all(
                        any(d["id"] == i and d["status"] == "completed" for d in listed)
                        for i in ids
                    ),
                )
                graph = client.get(
                    "/api/v1/graph/subgraph",
                    params=[("agent_id", agents[domain]), *[("document_ids", i) for i in ids]],
                )
                check(f"Scoped graph endpoint {domain}", graph.status_code == 200, graph.json())
                check(
                    f"Specialty selection isolation {domain}",
                    client.post(
                        "/api/v1/chat/stream",
                        json={
                            "agent_id": agents["neurology"] if domain != "neurology" else card,
                            "message": "test",
                            "document_ids": ids,
                        },
                    ).status_code
                    == 404,
                )
                continue
            answer, citations, session = stream(client, agents[domain], ids, question)
            check(f"Grounded numeric facts {domain}", all(f in answer for f in facts), answer)
            check(
                f"Citations match selected sources {domain}",
                bool(citations) and all(c["document_id"] in ids for c in citations),
                citations,
            )
            if len(ids) > 1:
                check("Multi-document retrieval", {c["document_id"] for c in citations} == set(ids))
            history = client.get(f"/api/v1/chat/sessions/{session}/messages").json()
            check(
                f"Persisted history/citations {domain}",
                len(history) == 2
                and history[-1]["content"] == answer
                and len(history[-1]["citations"]) == len(citations),
            )
            graph = client.get(
                "/api/v1/graph/subgraph",
                params=[("agent_id", agents[domain]), *[("document_ids", i) for i in ids]],
            )
            check(
                f"Evidence graph {domain}",
                graph.status_code == 200
                and graph.json()["total_nodes"] > 0
                and graph.json()["total_edges"] > 0,
                graph.json(),
            )
            check(
                f"Wrong-specialty document blocked {domain}",
                client.post(
                    "/api/v1/chat/stream",
                    json={
                        "agent_id": agents["neurology"] if domain != "neurology" else card,
                        "message": "test",
                        "document_ids": ids,
                    },
                ).status_code
                == 404,
            )
            follow, cites, _ = stream(
                client,
                agents[domain],
                ids,
                "Is there a recorded LDL cholesterol value? Say explicitly if not documented; do not invent a value.",
                session,
            )
            check(
                f"Missing evidence acknowledged {domain}",
                any(word in follow.lower() for word in ["not", "no ", "doesn't", "does not"])
                and "ldl" in follow.lower(),
                follow,
            )
            check(
                f"Follow-up history {domain}",
                len(client.get(f"/api/v1/chat/sessions/{session}/messages").json()) == 4,
            )
        if STORAGE_ONLY:
            asyncio.run(verify_retrieval(cases, domain_docs, agents))
        answer, citations, session = stream(
            client,
            card,
            [],
            "What is the recorded LVEF? Use only selected documents; do not invent a result.",
        )
        check("Explicit empty selection has no citations", not citations, answer)
        check(
            "Cross-specialty session blocked",
            client.post(
                "/api/v1/chat/stream",
                json={
                    "agent_id": agents["neurology"],
                    "session_id": session,
                    "message": "test",
                    "document_ids": [],
                },
            ).status_code
            == 409,
        )
        temporary = upload(client, card, "cardiology-baseline.txt", temporary=True)
        retry = client.post(f"/api/v1/documents/{temporary}/retry")
        check(
            "Real reindex/retry",
            retry.status_code == 200 and retry.json()["status"] == "completed",
            retry.json(),
        )
        check(
            "Delete temporary fixture",
            client.delete(f"/api/v1/documents/{temporary}").status_code == 204,
        )
        created[-1]["deleted"] = True
        check(
            "Deleted chunks inaccessible",
            client.get(f"/api/v1/documents/{temporary}/chunks").status_code == 404,
        )
        check(
            "Deleted evidence cannot be selected",
            client.post(
                "/api/v1/chat/stream",
                json={"agent_id": card, "message": "test", "document_ids": [temporary]},
            ).status_code
            == 404,
        )
        check(
            "Unsupported audio rejected",
            client.post(
                "/api/v1/voice/transcribe", files={"file": ("test.txt", b"test", "text/plain")}
            ).status_code
            == 415,
        )
        logout = client.delete("/api/v1/auth/session")
        check("Sign out", logout.status_code == 200 and logout.json()["status"] == "signed_out")
        check("Signed-out access blocked", client.get("/api/v1/documents").status_code == 401)
        check("Final service health", client.get("/health").json()["status"] == "healthy")
    print(f"Report: {REPORT}; {len(checks)} checks passed", flush=True)


if __name__ == "__main__":
    started = time.monotonic()
    try:
        main()
    finally:
        print(f"Elapsed: {time.monotonic() - started:.1f}s", flush=True)
