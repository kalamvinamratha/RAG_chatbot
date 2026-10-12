import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.registry import agent_registry
from app.db.models import ChatMessage, ChatSession, Citation, Document, HealthcareAgent
from app.db.postgres import AsyncSessionLocal, get_db
from app.rag.generator import rag_coordinator
from app.schemas.chat import (
    ChatMessageResponse,
    ChatQueryRequest,
    ChatSessionCreate,
    ChatSessionResponse,
)
from app.security import require_owner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Clinical Chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    """Create a new clinical consultation session."""
    agent = await db.get(HealthcareAgent, payload.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Healthcare agent {payload.agent_id} not found",
        )

    session = ChatSession(
        owner_id=owner,
        agent_id=payload.agent_id,
        title=payload.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    agent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    """List clinical consultation sessions."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.owner_id == owner)
        .order_by(ChatSession.updated_at.desc())
    )
    if agent_id:
        stmt = stmt.where(ChatSession.agent_id == agent_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    """Retrieve full chronological conversation history for a consultation."""
    session = await db.get(ChatSession, session_id)
    if not session or session.owner_id != owner:
        raise HTTPException(404, "Chat session not found")
    stmt = (
        select(ChatMessage)
        .options(selectinload(ChatMessage.citations))
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    res = await db.execute(stmt)
    messages = res.scalars().all()
    return [
        ChatMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            model_name=m.model_name,
            visual_payload=m.visual_payload,
            follow_up_suggestions=m.follow_up_suggestions,
            created_at=m.created_at,
            citations=[
                {
                    "citation_number": idx + 1,
                    "document_id": str(c.document_id) if c.document_id else None,
                    "chunk_id": str(c.chunk_id) if c.chunk_id else None,
                    "filename": c.document_name,
                    "page_number": c.page_number,
                    "excerpt": c.excerpt,
                    "score": c.relevance_score,
                    "sources": c.retrieval_source.split(","),
                }
                for idx, c in enumerate(m.citations)
            ],
        )
        for m in messages
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    """Delete a chat session and all associated messages."""
    session = await db.get(ChatSession, session_id)
    if not session or session.owner_id != owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    await db.delete(session)
    await db.commit()
    return None


@router.post("/stream")
async def stream_chat_response(
    payload: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(require_owner),
):
    """SSE streaming endpoint for clinical consultation answering."""
    # 1. Resolve agent
    agent_record = await db.get(HealthcareAgent, payload.agent_id)
    if not agent_record or not agent_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Healthcare agent {payload.agent_id} not found",
        )

    domain_agent = agent_registry.from_record(agent_record)
    if payload.document_ids is not None:
        ids = set(payload.document_ids)
        found = (
            (
                await db.execute(
                    select(Document.id).where(
                        Document.id.in_(ids),
                        Document.owner_id == owner,
                        Document.agent_id == payload.agent_id,
                        Document.status == "completed",
                    )
                )
            )
            .scalars()
            .all()
        )
        if set(found) != ids:
            raise HTTPException(404, "Selected documents are unavailable")

    # 2. Resolve or create chat session
    session_id = payload.session_id
    if not session_id:
        new_session = ChatSession(
            owner_id=owner,
            agent_id=payload.agent_id,
            title=payload.message[:40] + ("..." if len(payload.message) > 40 else ""),
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        session_id = new_session.id
    else:
        existing_session = await db.get(ChatSession, session_id)
        if not existing_session or existing_session.owner_id != owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session {session_id} not found",
            )
        if existing_session.agent_id != payload.agent_id:
            raise HTTPException(409, "Session belongs to a different specialty")

    history_rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

    # 3. Store user message in DB
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    active_sess = await db.get(ChatSession, session_id)
    if active_sess:
        active_sess.updated_at = datetime.now(UTC)
    await db.commit()

    doc_ids_str = (
        [str(d) for d in payload.document_ids] if payload.document_ids is not None else None
    )

    # 4. SSE streaming generator
    async def sse_event_generator():
        accumulated_text = ""
        stored_citations = []
        visual_payload = None
        follow_up_suggestions = []

        stored_graph_triples = []
        stored_keywords = []
        resolved_model_name = rag_coordinator.model_name

        # Yield session ID first
        yield f"event: session\ndata: {json.dumps({'session_id': str(session_id)})}\n\n"

        try:
            async for event in rag_coordinator.stream_rag_response(
                query=payload.message,
                agent=domain_agent,
                db_session=db,
                agent_id=str(payload.agent_id),
                document_ids=doc_ids_str,
                owner_id=owner,
                history=history,
            ):
                event_type = event["type"]

                if event_type == "citations":
                    stored_citations = event["citations"]
                    stored_graph_triples = event.get("graph_triples", [])
                    stored_keywords = event.get("matched_keywords", [])
                    yield f"event: citations\ndata: {json.dumps(event)}\n\n"

                elif event_type == "token":
                    accumulated_text += event["token"]
                    yield f"event: token\ndata: {json.dumps({'token': event['token']})}\n\n"

                elif event_type == "meta":
                    resolved_model_name = event.get("model_name", resolved_model_name)

                elif event_type == "visual_payload":
                    visual_payload = event["payload"]
                    yield f"event: visual_payload\ndata: {json.dumps(event['payload'])}\n\n"

                elif event_type == "follow_up_suggestions":
                    follow_up_suggestions = event["suggestions"]
                    yield f"event: follow_up_suggestions\ndata: {json.dumps(event['suggestions'])}\n\n"
                elif event_type == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event['message']})}\n\n"
                    return
        except Exception as exc:
            logger.exception("Chat retrieval failed: %s", exc)
            yield f"event: error\ndata: {json.dumps({'message': 'Clinical service unavailable. Please retry.'})}\n\n"
            return

        # Save assistant message to PostgreSQL in a separate session
        try:
            async with AsyncSessionLocal() as save_db:
                payload_to_save = visual_payload or {}
                if stored_graph_triples:
                    payload_to_save["graph_triples"] = stored_graph_triples
                if stored_keywords:
                    payload_to_save["matched_keywords"] = stored_keywords

                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=accumulated_text,
                    model_name=resolved_model_name,
                    visual_payload=payload_to_save if payload_to_save else None,
                    follow_up_suggestions=follow_up_suggestions,
                )
                save_db.add(assistant_msg)
                await save_db.flush()

                # Save citations
                for c in stored_citations:
                    doc_uuid = uuid.UUID(c["document_id"]) if c.get("document_id") else None
                    chunk_uuid = uuid.UUID(c["chunk_id"]) if c.get("chunk_id") else None
                    cite_record = Citation(
                        message_id=assistant_msg.id,
                        document_id=doc_uuid,
                        chunk_id=chunk_uuid,
                        document_name=c.get("filename", "Document"),
                        page_number=c.get("page_number"),
                        excerpt=c.get("excerpt", ""),
                        relevance_score=c.get("score", 1.0),
                        retrieval_source=",".join(c.get("sources", ["hybrid"])),
                    )
                    save_db.add(cite_record)

                sess = await save_db.get(ChatSession, session_id)
                if sess:
                    sess.updated_at = datetime.now(UTC)

                await save_db.commit()
        except Exception as save_err:
            logger.error("Failed to save assistant chat message: %s", save_err)
            yield f"event: error\ndata: {json.dumps({'message': 'Response could not be saved. Please retry.'})}\n\n"
            return

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
