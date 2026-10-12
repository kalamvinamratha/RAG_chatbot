import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseHealthcareAgent
from app.config import get_settings
from app.db.models import Document
from app.rag.bm25_search import bm25_retriever
from app.rag.evidence import chunk_payload, scoped_chunks
from app.rag.follow_up_generator import follow_up_generator
from app.rag.fusion import rrf_fusion
from app.rag.graph_search import graph_retriever
from app.rag.guardrails import domain_guardrail
from app.rag.multi_doc_synthesizer import multi_doc_synthesizer
from app.rag.reranker import reranker
from app.rag.vector_search import vector_retriever

logger = logging.getLogger(__name__)
settings = get_settings()


class GroundedRAGCoordinator:
    def __init__(self) -> None:
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL_NAME
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL_NAME
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.gemini_model_name = "gemini-2.5-flash"
        self.api_key = self.gemini_api_key
        self.model_name = self.gemini_model_name

    @staticmethod
    def _extract_matched_keywords(
        query: str,
        top_chunks: list[dict[str, Any]],
        graph_triples: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extracts high-value clinical terms, medication names, and query keywords matched in the evidence."""
        stopwords = {
            "what",
            "is",
            "the",
            "are",
            "there",
            "any",
            "for",
            "and",
            "in",
            "of",
            "to",
            "a",
            "an",
            "this",
            "that",
            "with",
            "from",
            "at",
            "by",
            "on",
            "patient",
            "clinical",
            "presentation",
            "show",
            "tell",
            "me",
            "how",
            "does",
            "can",
            "should",
            "could",
            "would",
            "about",
            "which",
            "when",
            "then",
            "its",
            "recommended",
        }

        keywords_map: dict[str, dict[str, Any]] = {}

        # 1. Add entities from knowledge graph triples with their high clinical relevance
        for g in graph_triples:
            s_name = g.get("source", "").strip()
            s_type = g.get("source_type", "Entity")
            if s_name and len(s_name) > 2:
                key = s_name.lower()
                keywords_map[key] = {
                    "term": s_name,
                    "category": s_type,
                    "source": "Knowledge Graph",
                    "count": keywords_map.get(key, {}).get("count", 0) + 3,
                }
            t_name = g.get("target", "").strip()
            t_type = g.get("target_type", "Entity")
            if t_name and len(t_name) > 2:
                key = t_name.lower()
                keywords_map[key] = {
                    "term": t_name,
                    "category": t_type,
                    "source": "Knowledge Graph",
                    "count": keywords_map.get(key, {}).get("count", 0) + 3,
                }

        # 2. Extract significant query tokens that appear in the retrieved chunks
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", query.lower())
        chunks_text = " ".join([c.get("content", "").lower() for c in top_chunks])

        for tok in tokens:
            if tok not in stopwords:
                occurrences = chunks_text.count(tok)
                if occurrences > 0:
                    if tok not in keywords_map:
                        cat = "Clinical Term"
                        if any(
                            tok.endswith(suf)
                            for suf in [
                                "lol",
                                "statin",
                                "mab",
                                "pril",
                                "sartan",
                                "xaban",
                                "parin",
                                "cillin",
                            ]
                        ):
                            cat = "Medication"
                        elif any(
                            tok.endswith(suf)
                            for suf in ["itis", "osis", "emia", "pathy", "oma", "syndrome"]
                        ):
                            cat = "Condition"
                        elif any(tok.endswith(suf) for suf in ["mg", "mcg", "g", "ml", "iu"]):
                            cat = "Dosage"

                        keywords_map[tok] = {
                            "term": tok.capitalize() if len(tok) > 3 else tok.upper(),
                            "category": cat,
                            "source": "BM25 Lexical",
                            "count": occurrences + 1,
                        }
                    else:
                        keywords_map[tok]["count"] += occurrences

        sorted_kw = sorted(keywords_map.values(), key=lambda x: x["count"], reverse=True)
        return sorted_kw[:12]

    @staticmethod
    def _is_conversational_or_greeting(query: str) -> bool:
        """Detect conversational greetings, introductions, and assistant meta-questions."""
        clean = re.sub(r"[^\w\s]", "", query).strip().lower()
        words = clean.split()
        if not words:
            return True

        companion_names = {
            "sage",
            "pip",
            "lumi",
            "bloom",
            "dr cardio",
            "dr neuro",
            "dr gynae",
            "dr internist",
        }
        greetings = {
            "hi",
            "hello",
            "hey",
            "greetings",
            "good morning",
            "good afternoon",
            "good evening",
            "howdy",
            "sup",
            "yo",
            "welcome",
            "thanks",
            "thank you",
            "ok",
            "okay",
            "bye",
            "goodbye",
            *companion_names,
        }
        if clean in greetings:
            return True
        if (
            words[0]
            in {
                "hi",
                "hello",
                "hey",
                "greetings",
                "good",
                "sage",
                "pip",
                "lumi",
                "bloom",
                "doc",
                "doctor",
            }
            and len(words) <= 5
        ):
            return True

        meta_phrases = [
            "who are you",
            "what can you do",
            "what are you",
            "what is your name",
            "whats your name",
            "what's your name",
            "how can you help",
            "how does this work",
            "help me",
            "introduce yourself",
            "what do you do",
            "tell me about yourself",
            "how are you",
            "capabilities",
            "are you sage",
            "are you pip",
            "are you lumi",
            "are you bloom",
        ]
        return any(phrase in clean for phrase in meta_phrases) and len(words) <= 10

    async def _stream_with_openai(
        self,
        query: str,
        system_context: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens using OpenAI as the primary provider."""
        if not self.openai_api_key:
            return

        import httpx

        messages: list[dict[str, str]] = [{"role": "system", "content": system_context}]
        for m in history or []:
            if m.get("role") in {"user", "assistant"}:
                messages.append({"role": m["role"], "content": m.get("content", "")[:12000]})
        messages.append({"role": "user", "content": query})

        try:
            async with (
                httpx.AsyncClient(timeout=60.0) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.openai_model_name,
                        "messages": messages,
                        "stream": True,
                        "temperature": 0.2,
                    },
                ) as response,
            ):
                if response.status_code != 200:
                    logger.warning(
                        "OpenAI model %s returned status %d: %s",
                        self.openai_model_name,
                        response.status_code,
                        await response.aread(),
                    )
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                        except Exception:
                            continue
        except Exception as exc:
            logger.warning("OpenAI streaming error: %s", exc)

    async def _stream_with_groq(
        self,
        query: str,
        system_context: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens using Groq as a fallback provider."""
        if not self.groq_api_key:
            return

        import httpx

        messages: list[dict[str, str]] = [{"role": "system", "content": system_context}]
        for m in history or []:
            if m.get("role") in {"user", "assistant"}:
                messages.append({"role": m["role"], "content": m.get("content", "")[:12000]})
        messages.append({"role": "user", "content": query})

        candidate_models = [
            m for m in [self.groq_model_name, "openai/gpt-oss-20b", "qwen/qwen3.8-27b"] if m
        ]
        unique_models = list(dict.fromkeys(candidate_models))

        for model in unique_models:
            try:
                async with (
                    httpx.AsyncClient(timeout=60.0) as client,
                    client.stream(
                        "POST",
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "stream": True,
                            "temperature": 0.2,
                        },
                    ) as response,
                ):
                    if response.status_code != 200:
                        logger.warning(
                            "Groq model %s returned status %d", model, response.status_code
                        )
                        continue

                    emitted_any = False
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                choices = chunk_data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        emitted_any = True
                                        yield content
                            except Exception:
                                continue
                    if emitted_any:
                        return
            except Exception as exc:
                logger.warning("Groq fallback error with model %s: %s", model, exc)
                continue

    async def execute_tri_hybrid_retrieval(
        self,
        query: str,
        agent_id: str,
        db_session: AsyncSession,
        document_ids: list[str] | None = None,
        owner_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Run scoped retrieval, fuse with RRF, and rerank. SQL reads share one session."""
        # PostgreSQL is authoritative for ownership, status and document scope.
        stmt = select(Document.id).where(
            Document.status == "completed", Document.agent_id == uuid.UUID(agent_id)
        )
        if owner_id:
            stmt = stmt.where(Document.owner_id == owner_id)
        if document_ids is not None:
            stmt = stmt.where(Document.id.in_([uuid.UUID(d) for d in document_ids]))
        document_ids = [str(d) for d in (await db_session.execute(stmt)).scalars().all()]
        if not document_ids:
            return [], []
        vector_candidates = await vector_retriever.retrieve(
            query=query, agent_id=agent_id, document_ids=document_ids, limit=15
        )
        bm25_candidates = await bm25_retriever.retrieve(
            query=query,
            db_session=db_session,
            agent_id=agent_id,
            document_ids=document_ids,
            limit=15,
            owner_id=owner_id,
        )
        graph_candidates, graph_triples = await graph_retriever.retrieve(
            query=query,
            db_session=db_session,
            agent_id=agent_id,
            limit=15,
            document_ids=document_ids,
            owner_id=owner_id,
        )

        # 2. Reciprocal Rank Fusion
        retrieval_streams = {
            "vector": vector_candidates,
            "bm25": bm25_candidates,
            "graph": graph_candidates,
        }
        fused_candidates = rrf_fusion.fuse(retrieval_streams, top_k=15)

        # Fallback for document summarization, overview, or sparse candidate streams
        is_summary_query = any(
            kw in query.lower()
            for kw in [
                "summar",
                "overview",
                "key finding",
                "key takeaway",
                "main point",
                "document",
                "protocol",
                "guideline",
                "findings",
                "recommendation",
                "explain",
                "review",
                "what does",
                "what is in",
                "highlights",
            ]
        )
        if (not fused_candidates or is_summary_query) and document_ids:
            doc_rows = await scoped_chunks(db_session, agent_id, document_ids, owner_id)
            if doc_rows:
                fallback_chunks = [
                    {
                        **chunk_payload(chunk, fname, "document"),
                        "score": 1.0,
                        "sources": ["document"],
                    }
                    for chunk, fname in doc_rows
                ]
                if not fused_candidates:
                    fused_candidates = fallback_chunks[:15]
                else:
                    existing_chunk_ids = {c.get("chunk_id") for c in fused_candidates}
                    for fb_c in fallback_chunks:
                        if fb_c.get("chunk_id") not in existing_chunk_ids:
                            fused_candidates.append(fb_c)
                            if len(fused_candidates) >= 15:
                                break

        # 3. Cross-Encoder Reranking
        top_reranked = await asyncio.to_thread(
            reranker.rerank, query=query, candidates=fused_candidates, top_k=5
        )
        if not top_reranked and fused_candidates:
            top_reranked = fused_candidates[:5]

        return top_reranked, graph_triples

    async def stream_rag_response(
        self,
        query: str,
        agent: BaseHealthcareAgent,
        db_session: AsyncSession,
        agent_id: str,
        document_ids: list[str] | None = None,
        owner_id: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Streaming generator yielding tokens, citations, and follow-up suggestions."""
        # 0. Domain guardrail check for off-topic query
        is_valid_query, refusal_message = domain_guardrail.check_query_domain(query)
        if not is_valid_query:
            yield {
                "type": "citations",
                "citations": [],
                "multi_doc_info": {"is_multi_doc": False, "contradictions": []},
                "graph_triples": [],
                "matched_keywords": [],
            }
            yield {"type": "token", "token": refusal_message}
            yield {
                "type": "follow_up_suggestions",
                "suggestions": [
                    "What clinical guidelines or medical questions can you assist with?",
                    "How do I upload clinical documents or patient records?",
                ],
            }
            return

        # 1. Retrieve top chunks & graph triples
        retrieval_query = "\n".join(
            [m["content"] for m in (history or []) if m["role"] == "user"][-2:] + [query]
        )[-6000:]
        top_chunks, graph_triples = await self.execute_tri_hybrid_retrieval(
            query=retrieval_query,
            agent_id=agent_id,
            db_session=db_session,
            document_ids=document_ids,
            owner_id=owner_id,
        )

        # 2. Check for multi-doc synthesis & contradictions
        multi_doc_info = multi_doc_synthesizer.analyze_cross_document_context(top_chunks)

        # 3. Build citations metadata
        citations: list[dict[str, Any]] = []
        context_snippets: list[str] = []
        for idx, chunk in enumerate(top_chunks):
            citation_num = idx + 1
            fname = chunk.get("filename", "Document")
            page_no = chunk.get("page_number")
            excerpt = chunk.get("content", "")[:350]
            score = chunk.get("rerank_score", chunk.get("rrf_score", 0.9))

            citations.append(
                {
                    "citation_number": citation_num,
                    "document_id": chunk.get("document_id"),
                    "chunk_id": chunk.get("chunk_id"),
                    "filename": fname,
                    "page_number": page_no,
                    "excerpt": excerpt,
                    "score": round(float(score), 3),
                    "chunk_type": chunk.get("chunk_type", "text"),
                    "image_path": chunk.get("image_path"),
                    "sources": chunk.get("sources", ["hybrid"]),
                }
            )

            cite_label = f"[{fname}, Page {page_no}]" if page_no else f"[{fname}]"
            context_snippets.append(
                f"Excerpt #{citation_num} {cite_label}:\n{chunk.get('content', '')}"
            )

        # 4. Construct grounded system instructions
        is_greeting = self._is_conversational_or_greeting(query)

        if is_greeting:
            companion_alias = getattr(agent, "companion_name", None) or {
                "cardiology": "Pip",
                "neurology": "Lumi",
                "gynaecology": "Bloom",
                "general_medicine": "Sage",
            }.get(agent.domain_key, "Assistant")
            system_context = (
                f"You are {agent.name} (also known as your companion name '{companion_alias}'), an expert AI consultant specialized in {agent.specialty}.\n"
                f"{agent.system_prompt}\n\n"
                "The user has sent a greeting, introductory message, or conversational question.\n"
                "Respond warmly, conversationally, and professionally as an expert clinical colleague. "
                f"Introduce yourself acknowledging both your companion name ({companion_alias}) and your clinical title ({agent.name}). "
                f"If the user addressed or greeted you by name (e.g. 'Hey {companion_alias}'), acknowledge it warmly and naturally. "
                f"Explain your specialty in {agent.specialty}, "
                "describe what clinical guidance, guideline checks, drug dosage calculations, or protocol analyses you can assist with, "
                "and invite the user to upload clinical documents or ask any clinical questions. "
                "Keep your response natural, helpful, engaging, and concise (2 paragraphs max)."
            )
        elif not top_chunks and not graph_triples:
            companion_alias = getattr(agent, "companion_name", None) or {
                "cardiology": "Pip",
                "neurology": "Lumi",
                "gynaecology": "Bloom",
                "general_medicine": "Sage",
            }.get(agent.domain_key, "Assistant")
            system_context = (
                f"You are {agent.name} (also known as your companion name '{companion_alias}'), an expert AI consultant specialized in {agent.specialty}.\n"
                f"{agent.system_prompt}\n\n"
                "### Mandatory Clinical Specialist Identity & Differentiation:\n"
                f"1. You are strictly {agent.name} (known as '{companion_alias}'), the dedicated clinical consultant for {agent.specialty}. "
                f"If addressed by name (e.g., '{companion_alias}'), acknowledge your identity. "
                "You must evaluate this query exclusively through your specialty's clinical lens, diagnostic hierarchy, and guideline frameworks.\n"
                "2. Never provide generic, interchangeable medical answers. Your assessment, prioritized diagnostic battery, and management strategy must clearly demonstrate the distinct depth and perspective of your specialty.\n\n"
                "### Clinical Context Notice:\n"
                "No specific uploaded patient records or institutional documents were selected for this query.\n"
                "Provide a rigorous, evidence-informed clinical consultation based on established medical guidelines (ACC/AHA, ACOG, AAN, ACP), "
                "while noting that no patient-specific documents were selected in this session. "
                "Adhere to your required specialty output structure."
            )
        else:
            system_context = agent.build_system_context(
                retrieved_contexts=context_snippets,
                graph_knowledge=graph_triples,
                is_multi_doc=multi_doc_info["is_multi_doc"],
            )

        # Extract matched clinical keywords and terms from query and retrieved evidence
        matched_keywords = self._extract_matched_keywords(
            query=query, top_chunks=top_chunks, graph_triples=graph_triples
        )

        # Yield citations and provenance matrix (documents, keywords, graph triples)
        yield {
            "type": "citations",
            "citations": citations,
            "multi_doc_info": multi_doc_info,
            "graph_triples": graph_triples,
            "matched_keywords": matched_keywords,
        }

        full_response_text = ""

        # If documents were specifically selected but yielded zero evidence, state insufficient evidence in selected documents
        if not is_greeting and not top_chunks and not graph_triples and document_ids is not None:
            yield {
                "type": "token",
                "token": "I do not have sufficient clinical evidence in the selected documents to answer this question accurately.",
            }
            yield {"type": "follow_up_suggestions", "suggestions": []}
            return

        # 5. Stream response via LLM (OpenAI primary, Groq / Gemini fallback)
        llm_success = False
        any_provider_attempted = False

        actual_model_used = "offline-synthesizer"

        # Attempt 1: OpenAI (Primary)
        if self.openai_api_key:
            any_provider_attempted = True
            logger.info(
                "Streaming response via primary OpenAI model (%s)...", self.openai_model_name
            )
            try:
                async for token in self._stream_with_openai(
                    query=query, system_context=system_context, history=history
                ):
                    full_response_text += token
                    yield {"type": "token", "token": token}
                if full_response_text.strip():
                    llm_success = True
                    actual_model_used = self.openai_model_name
            except Exception as oe:
                logger.warning("OpenAI primary stream failed: %s", oe)
                if full_response_text:
                    logger.error("OpenAI stream interrupted after partial emission")
                    yield {
                        "type": "error",
                        "message": "Response interrupted. Please retry.",
                    }
                    return

        # Attempt 2: Groq (Fallback 1)
        if not llm_success and self.groq_api_key:
            any_provider_attempted = True
            logger.info("Failing over to Groq model (%s)...", self.groq_model_name)
            try:
                async for token in self._stream_with_groq(
                    query=query, system_context=system_context, history=history
                ):
                    full_response_text += token
                    yield {"type": "token", "token": token}
                if full_response_text.strip():
                    llm_success = True
                    actual_model_used = self.groq_model_name
            except Exception as ge:
                logger.warning("Groq fallback stream failed: %s", ge)
                if full_response_text:
                    logger.error("Groq stream interrupted after partial emission")
                    yield {
                        "type": "error",
                        "message": "Response interrupted. Please retry.",
                    }
                    return

        # Attempt 3: Google Gemini (Fallback 2)
        gemini_key = self.gemini_api_key or self.api_key
        if not llm_success and gemini_key:
            any_provider_attempted = True
            logger.info("Failing over to Gemini model (%s)...", self.gemini_model_name)
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_key)

                contents = [
                    types.Content(
                        role="model" if m["role"] == "assistant" else "user",
                        parts=[types.Part.from_text(text=m["content"][:12000])],
                    )
                    for m in (history or [])
                    if m["role"] in {"assistant", "user"}
                ]
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                for attempt in range(3):
                    try:
                        response_stream = await client.aio.models.generate_content_stream(
                            model=self.gemini_model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(system_instruction=system_context),
                        )
                        async for chunk in response_stream:
                            token = chunk.text or ""
                            full_response_text += token
                            yield {"type": "token", "token": token}
                        if not full_response_text.strip():
                            raise RuntimeError("Provider returned no answer")
                        llm_success = True
                        actual_model_used = self.gemini_model_name
                        break
                    except Exception as exc:
                        code = getattr(exc, "code", None)
                        if (
                            full_response_text
                            or code not in {429, 500, 502, 503, 504}
                            or attempt == 2
                        ):
                            raise
                        delay = 30 if code == 429 else 2 ** (attempt + 1)
                        details = getattr(exc, "details", {})
                        if isinstance(details, dict):
                            error = details.get("error", details)
                            for info in error.get("details", []) if isinstance(error, dict) else []:
                                if not isinstance(info, dict):
                                    continue
                                retry_delay = info.get("retryDelay", "")
                                if isinstance(retry_delay, str) and re.fullmatch(
                                    r"\d+(?:\.\d+)?s", retry_delay
                                ):
                                    delay = max(delay, float(retry_delay[:-1]))
                        if delay > 60:
                            raise
                        await asyncio.sleep(delay)
            except Exception as e:
                logger.warning("Gemini primary stream failed or quota reached (%s)", e)
                if full_response_text:
                    logger.error("LLM streaming error after partial emission: %s", e)
                    yield {
                        "type": "error",
                        "message": "Response interrupted. Please retry.",
                    }
                    return

        if not llm_success:
            if any_provider_attempted:
                logger.error("All configured LLM providers failed or exhausted quota.")
                yield {
                    "type": "error",
                    "message": "Answer service unavailable or quota exhausted. Check provider quota and retry.",
                }
                return

            # Deterministic, grounded offline synthesis
            if is_greeting:
                companion_alias = getattr(agent, "companion_name", None) or {
                    "cardiology": "Pip",
                    "neurology": "Lumi",
                    "gynaecology": "Bloom",
                    "general_medicine": "Sage",
                }.get(agent.domain_key, "Assistant")
                fallback_text = (
                    f"Hello! I am **{companion_alias}** ({agent.name}), your clinical AI consultant specialized in **{agent.specialty}**.\n\n"
                    f"I provide evidence-based decision support, guideline interpretations, and medication checks. "
                    "You can upload clinical documents (PDF, DOCX, TXT) or ask any question to get started!"
                )
            elif not top_chunks and not graph_triples:
                fallback_text = (
                    f"I do not have specific uploaded documents matching '{query}' in the current session. "
                    f"However, as a **{agent.specialty}** specialist, I can assist with clinical questions, guideline interpretations, and protocol comparisons.\n\n"
                    "Please upload the relevant clinical PDF, DOCX, or patient chart to enable verified citation grounding."
                )
            else:
                fallback_text = (
                    f"### Clinical Synthesis ({agent.specialty})\n\n"
                    f"Based on the clinical evidence retrieved from {len(top_chunks)} document section(s):\n\n"
                )
                for c in citations:
                    fallback_text += (
                        f"- **{c['filename']}** *(Page {c.get('page_number') or 'N/A'}, relevance score {c['score']})*:\n"
                        f'  > "{c["excerpt"]}..."\n\n'
                    )

                if graph_triples:
                    fallback_text += "\n**Source-Extracted Knowledge Graph Relationships:**\n"
                    for g in graph_triples[:3]:
                        fallback_text += f"- `{g.get('source')}` ➔ **{g.get('relationship')}** ➔ `{g.get('target')}`\n"

                fallback_text += f"\n\n*{agent.get_specialized_disclaimer()}*"
            full_response_text = fallback_text
            yield {"type": "token", "token": fallback_text}

        # 6. Parse visual payloads (Mermaid diagrams, KaTeX formulas)
        mermaid_match = re.search(r"```mermaid\n(.*?)\n```", full_response_text, re.DOTALL)
        katex_match = re.search(r"\$\$(.*?)\$\$", full_response_text, re.DOTALL)

        visual_payload: dict[str, Any] = {}
        if mermaid_match:
            visual_payload["mermaid"] = mermaid_match.group(1).strip()
        if katex_match:
            visual_payload["katex"] = katex_match.group(1).strip()

        if visual_payload:
            yield {"type": "visual_payload", "payload": visual_payload}

        # 7. Generate follow-up suggestions (Add-on feature)
        if is_greeting:
            suggestions = [
                "What clinical guidelines do you specialize in?",
                "How do I upload and analyze patient documents?",
                "Can you calculate clinical risk scores or drug dosages?",
            ]
        else:
            suggestions = await follow_up_generator.generate_suggestions(
                domain_specialty=agent.specialty,
                user_query=query,
                assistant_response=full_response_text,
            )
        yield {"type": "meta", "model_name": actual_model_used}
        yield {"type": "follow_up_suggestions", "suggestions": suggestions}


rag_coordinator = GroundedRAGCoordinator()
