"""
Lecture Agent - YouTube transcript, translation, notes, RAG chat
"""

import re
import os
import logging
import requests

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.llm import get_llm
from src.core.observability import trace_config
from src.core.vector_store import create_vector_store, similarity_search, make_persist_key, persist_dir_for, vector_store_exists
from src.agents.lecture.prompts import (
    TRANSLATE_PROMPT, TOPIC_PROMPT, NOTES_PROMPT, CHAT_PROMPT
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────

# (Removed unused LectureResult dataclass - functions return plain dicts.)


# ─────────────────────────────────────────
# VIDEO ID EXTRACTION
# ─────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    if not url or not url.strip():
        return None
    url = url.strip()
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",
        r"(?:embed/)([0-9A-Za-z_-]{11})",
        r"(?:shorts/)([0-9A-Za-z_-]{11})",
        r"(?:live/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # Fallback: the user pasted a bare 11-char video ID with no URL wrapper.
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    return None


# ─────────────────────────────────────────
# TRANSCRIPT FETCHING
# ─────────────────────────────────────────

def _ytdlp_proxy() -> str:
    """Residential/HTTP proxy URL from env (YTDLP_PROXY). Empty => direct.

    Set this on the host (e.g. Render) to route YouTube caption traffic through
    a residential IP, since shared datacenter IPs are frequently bot-blocked.
    Format: http://user:pass@host:port  (or http://host:port for IP-auth).
    """
    return os.getenv("YTDLP_PROXY", "").strip()


def _fetch_json3(url: str) -> str:
    """Fetch and parse json3 subtitle format (through the proxy if configured)."""
    proxy = _ytdlp_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = requests.get(url, timeout=15, proxies=proxies)
    r.raise_for_status()
    data = r.json()
    text = " ".join([
        seg.get("utf8", "")
        for event in data.get("events", [])
        if event.get("segs")
        for seg in event["segs"]
    ]).strip()
    return text


def get_transcript(video_id: str) -> tuple[str, str]:
    """Get transcript using yt-dlp."""
    if not video_id:
        raise ValueError("🔗 This doesn’t look like a valid YouTube link. Please paste a full YouTube video URL and try again.")
    
    try:
        import yt_dlp
    except ImportError:
        raise ValueError("yt-dlp not installed. Run: pip install yt-dlp")
    
    url = "https://www.youtube.com/watch?v=" + video_id
    
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # Cloud hosts (e.g. Render) use shared datacenter IPs that YouTube
        # frequently bot-blocks for the default "web" client. Asking yt-dlp to
        # try the mobile API clients first markedly improves success from
        # server environments.
        "extractor_args": {
            "youtube": {"player_client": ["android", "ios", "web"]}
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }

    # Optional escape hatches for datacenter IP blocks (configured via env):
    #   YTDLP_PROXY   -> residential/HTTP proxy URL (host:port, optional auth)
    #   YTDLP_COOKIES -> path to a Netscape cookies.txt exported from a
    #                    logged-in YouTube session
    _proxy = _ytdlp_proxy()
    if _proxy:
        ydl_opts["proxy"] = _proxy
    _cookies = os.getenv("YTDLP_COOKIES", "").strip()
    if _cookies and os.path.exists(_cookies):
        ydl_opts["cookiefile"] = _cookies
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        err = str(e)
        logger.error(f"yt-dlp extract failed: {err}")
        low = err.lower()
        if any(s in low for s in (
            "sign in", "confirm you", "not a bot", "429",
            "too many requests", "blocked",
        )):
            raise ValueError(
                "⏳ YouTube temporarily blocked our server from reading "
                "this video — this can happen on shared cloud IPs. Please "
                "try again in a little while. If it keeps happening, this "
                "lecture’s captions can’t be fetched automatically from "
                "our server."
            )
        if "private" in low or "members-only" in low or "age" in low:
            raise ValueError(
                "🔒 This video looks private or age-restricted, so we "
                "can’t read its captions. Please try a publicly available "
                "lecture."
            )
        raise ValueError(
            "🔒 We couldn’t access this video. It may be "
            "unavailable, region-locked, or the link may be incorrect. Please "
            "check the URL and try a publicly available lecture."
        )
    
    auto_captions = info.get("automatic_captions", {})
    manual_subs = info.get("subtitles", {})
    
    for source in [manual_subs, auto_captions]:
        for lang in ["hi", "hi-orig", "en"]:
            if lang not in source:
                continue
            for fmt in source[lang]:
                if fmt.get("ext") == "json3":
                    try:
                        text = _fetch_json3(fmt["url"])
                        if text.strip():
                            detected_lang = "hi" if "hi" in lang else "en"
                            logger.info(f"Transcript fetched: {len(text)} chars, lang={detected_lang}")
                            return text, detected_lang
                    except Exception as e:
                        logger.warning(f"json3 fetch failed lang={lang}: {e}")
                        continue
    
    raise ValueError(
        "📝 We couldn’t generate notes for this video because it "
        "doesn’t have captions or subtitles, which we need to read the "
        "lecture. Most educational channels (StudyIQ, Drishti IAS, "
        "Unacademy, etc.) have captions enabled — please try a lecture "
        "where the CC button is available."
    )


# ─────────────────────────────────────────
# TRANSLATION
# ─────────────────────────────────────────

def _translate_if_needed(text: str, lang: str) -> str:
    """Translate Hindi to English if needed."""
    hindi_ratio = sum(1 for c in text if '\u0900' <= c <= '\u097f') / max(len(text), 1)
    
    if lang == "en" and hindi_ratio < 0.15:
        logger.info("Already English — skipping translation")
        return text
    
    logger.info(f"Translating (Hindi ratio: {hindi_ratio:.1%})")
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=9000, chunk_overlap=150)
    chunks = splitter.split_text(text)
    
    results = []
    chain = TRANSLATE_PROMPT | get_llm()
    for i, chunk in enumerate(chunks):
        logger.info(f"Translating chunk {i+1}/{len(chunks)}")
        try:
            results.append(chain.invoke({"text": chunk}, config=trace_config("lecture-translate")).content)
        except Exception as e:
            logger.warning(f"Chunk {i+1} translation failed: {e}")
            results.append(chunk)
    
    return " ".join(results)


# ─────────────────────────────────────────
# TOPIC DETECTION
# ─────────────────────────────────────────

def _detect_topic(text: str) -> dict:
    """Detect lecture topic and UPSC relevance."""
    try:
        chain = TOPIC_PROMPT | get_llm()
        res = chain.invoke({"text": text[:4000]}, config=trace_config("topic-detect")).content
        result = {
            "topic": "Unknown",
            "paper": "Unknown",
            "syllabus": "Unknown",
            "subtopics": [],
            "content_type": "teaching",
            "relevant": True,
        }
        for line in res.strip().split("\n"):
            line = line.lstrip("*-#> ").replace("**", "").strip()
            if line.startswith("TOPIC:"):
                result["topic"] = line.replace("TOPIC:", "").strip()
            elif line.startswith("PAPER:"):
                result["paper"] = line.replace("PAPER:", "").strip()
            elif line.startswith("SYLLABUS:"):
                result["syllabus"] = line.replace("SYLLABUS:", "").strip()
            elif line.startswith("SUBTOPICS:"):
                result["subtopics"] = [s.strip() for s in line.replace("SUBTOPICS:", "").split(",")]
            elif line.startswith("CONTENT_TYPE:"):
                result["content_type"] = line.replace("CONTENT_TYPE:", "").strip().lower()
            elif line.startswith("RELEVANT:"):
                result["relevant"] = "no" not in line.replace("RELEVANT:", "").strip().lower()
        return result
    except Exception as e:
        logger.error(f"Topic detection failed: {e}")
        return {"topic": "Unknown", "paper": "Unknown", "syllabus": "Unknown", "subtopics": [], "content_type": "teaching", "relevant": True}


# ─────────────────────────────────────────
# MAIN PROCESSING
# ─────────────────────────────────────────

def _build_from_transcript(transcript: str, lang: str, video_id: str, medium: str = "English") -> dict:
    """Shared pipeline: turn a raw transcript into notes, study aids and a RAG
    vector store. Used by the YouTube-caption, pasted-transcript and uploaded-
    audio entry points so all three behave identically downstream."""
    # Content floor - too little text means there is no real teaching content.
    MIN_TRANSCRIPT_CHARS = 2000
    if not transcript or len(transcript.strip()) < MIN_TRANSCRIPT_CHARS:
        raise ValueError(
            "📝 There isn’t enough lecture content here to build proper "
            "notes. Please provide a fuller lecture - a complete transcript, or "
            "the full audio of a teaching session."
        )

    # No bulk translation - Gemini reads Hindi/English directly. Translating the
    # full transcript was the biggest cost driver on long videos and is
    # unnecessary since the model is multilingual.
    english_text = transcript
    logger.info(f"Skipping bulk translation (lang={lang}) - using transcript directly")

    # Detect topic
    topic_info = _detect_topic(english_text)
    logger.info(f"Topic: {topic_info['topic']} | Paper: {topic_info['paper']}")

    # Relevance gate - only allow genuine TEACHING lectures.
    content_type = (topic_info.get("content_type") or "teaching").strip().lower()
    paper_raw = (topic_info.get("paper") or "").lower()
    non_teaching = (content_type in {"entertainment", "motivational", "news_update", "news", "other"}) or (not topic_info.get("relevant", True))
    paper_tokens = [t for t in ("gs1", "gs2", "gs3", "gs4", "optional", "current affairs") if t in paper_raw]
    multi_paper = len(paper_tokens) >= 3
    na_paper = ("not applicable" in paper_raw) or ("all paper" in paper_raw) or ("various" in paper_raw)
    if non_teaching or multi_paper or na_paper:
        logger.info(
            f"Relevance gate blocked: content_type={content_type}, "
            f"paper='{topic_info.get('paper')}', multi_paper={multi_paper}, na_paper={na_paper}"
        )
        raise ValueError(
            "🎬 This doesn’t look like a genuine teaching lecture - it seems to be "
            "entertainment, a personal/anecdotal story, a motivational talk, or just an "
            "announcement (even if it mentions UPSC). UPSC AI is built for study lectures that "
            "actually teach the syllabus, so we couldn’t create notes from it. Please share "
            "an educational lecture that explains a topic and we’ll prepare your notes."
        )

    # Smart truncation for notes
    max_chars = 14000
    if len(english_text) > max_chars:
        mid_start = len(english_text) // 2 - 1000
        sep = chr(10) + chr(10) + "[...]" + chr(10) + chr(10)
        text_for_notes = (
            english_text[:8000] + sep +
            english_text[mid_start:mid_start + 2000] + sep +
            english_text[-2000:]
        )
    else:
        text_for_notes = english_text

    # Generate notes
    try:
        chain = NOTES_PROMPT | get_llm()
        notes = chain.invoke({
            "text": text_for_notes,
            "topic": topic_info["topic"],
            "paper": topic_info["paper"],
            "syllabus": topic_info["syllabus"],
            "medium": medium,
        }, config=trace_config("lecture-notes", session_id=f"lecture:{video_id}")).content
    except Exception as e:
        logger.error(f"Notes generation failed: {e}")
        notes = "⚠️ Notes generation failed. Please retry."

    if notes and not notes.startswith("⚠️"):
        notes = "> ⚠️ AI-generated notes - cross-check key facts, dates, and names with a standard source." + chr(10) + chr(10) + notes

    # Chat RAG index is built lazily in the background (scheduled by the route)
    # rather than inline here. Building/loading the vector store inline kept the
    # notes HTTP response blocked behind a memory-heavy vector step; if that step
    # crashed the worker on a small host, the whole response was lost ("Failed to
    # fetch") even though the notes had already been generated. Deferring it lets
    # the notes return first; chat indexing then happens off the request path.

    # Generate study aids (mind map + practice questions) - skip when notes failed
    if notes and not notes.startswith("⚠️"):
        from src.core.study_aids import generate_study_aids
        mindmap_html, questions_html = generate_study_aids(
            text_for_notes, topic_info["topic"], topic_info["paper"]
        )
    else:
        mindmap_html, questions_html = "", ""

    return {
        "notes": notes,
        "mindmap_html": mindmap_html,
        "questions_html": questions_html,
        "topic_info": topic_info,
        "video_id": video_id,
        # Internal only: consumed by the route to build the chat RAG index in a
        # background task after the response is sent. Not part of the API schema.
        "_transcript": english_text,
    }


def build_lecture_chat_index(video_id: str, transcript: str) -> None:
    """Index a lecture transcript for chat RAG. Best-effort and deferred.

    Scheduled as a background task so it runs *after* the notes response has been
    returned to the client. Any failure here only reduces chat grounding for that
    video; it must never propagate to (or crash) the notes request.
    """
    if not transcript or not video_id:
        return
    try:
        key = make_persist_key("lecture", video_id)
        if vector_store_exists(key):
            return
        create_vector_store(transcript, persist_key=key)
        logger.info(f"Lecture chat index ready: {video_id}")
    except Exception as e:
        logger.warning(f"Lecture chat index build failed for {video_id}: {e}")


def process_lecture(youtube_url: str, medium: str = "English") -> dict:
    """Process a YouTube lecture via its captions and generate notes."""
    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise ValueError("🔗 This doesn’t look like a valid YouTube link. Please paste a full YouTube video URL and try again.")
    transcript, lang = get_transcript(video_id)
    return _build_from_transcript(transcript, lang, video_id, medium)


# -----------------------------------------------------------------
# ALTERNATIVE INPUTS - pasted transcript & uploaded audio (Groq Whisper)
#
# These bypass YouTube's server-side caption fetch entirely, which shared
# cloud hosts (e.g. Render) are frequently IP-blocked from. They also unlock
# lectures that have no captions at all.
# -----------------------------------------------------------------

import hashlib as _hashlib

# Groq exposes an OpenAI-compatible Speech-to-Text endpoint. Assembled from
# fragments so URL-rewriting tooling never mangles a full literal.
_GROQ_STT_URL = "https://" + "api.groq.com/openai/v1/audio/transcriptions"


def transcribe_audio_groq(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """Transcribe an audio file to text using Groq's Whisper endpoint.

    Returns plain transcript text, or raises ValueError with a user-friendly
    message (missing key, oversized/unsupported file, rate limit, etc.).
    """
    from src.core.config import settings
    if not settings.groq_api_key:
        raise ValueError(
            "🔑 Audio transcription needs a Groq API key on the server. "
            "Please paste the transcript instead, or ask the admin to set GROQ_API_KEY."
        )
    model = getattr(settings, "groq_whisper_model", "whisper-large-v3-turbo")
    try:
        resp = requests.post(
            _GROQ_STT_URL,
            headers={"Authorization": "Bearer " + settings.groq_api_key},
            files={"file": (filename or "audio.mp3", audio_bytes)},
            data={"model": model, "response_format": "text"},
            timeout=300,
        )
    except Exception as e:
        logger.error(f"Groq STT request failed: {e}")
        raise ValueError(
            "⚠️ We couldn’t reach the transcription service just now. Please "
            "try again in a moment, or paste the transcript instead."
        )
    if resp.status_code != 200:
        snippet = (resp.text or "")[:300]
        low = snippet.lower()
        logger.error(f"Groq STT HTTP {resp.status_code}: {snippet}")
        if resp.status_code == 429:
            raise ValueError(
                "⏳ Transcription is rate-limited right now. Please try again in a "
                "little while, or paste the transcript instead."
            )
        if resp.status_code in (400, 413) and ("large" in low or "size" in low or "decode" in low or "format" in low):
            raise ValueError(
                "🎧 This audio looks too large or is in an unsupported format. "
                "Please upload a shorter clip as MP3/M4A/WAV, or paste the transcript instead."
            )
        raise ValueError(
            "⚠️ Audio transcription failed. Please try a different file, or "
            "paste the transcript instead."
        )
    text = (resp.text or "").strip()
    if not text:
        raise ValueError(
            "🎧 We couldn’t hear any speech in that audio. Please upload a "
            "clear lecture recording, or paste the transcript instead."
        )
    return text


def process_lecture_from_text(transcript: str, medium: str = "English") -> dict:
    """Build a lecture study session from a user-pasted transcript.

    This path never touches YouTube, so it always works regardless of caption
    availability or server IP blocks.
    """
    if not transcript or not transcript.strip():
        raise ValueError("📝 Please paste the lecture transcript text first.")
    vid = "paste_" + _hashlib.md5(transcript.strip().encode("utf-8")).hexdigest()[:11]
    return _build_from_transcript(transcript, "auto", vid, medium)


def process_lecture_from_audio(audio_bytes: bytes, filename: str = "audio.mp3", medium: str = "English") -> dict:
    """Transcribe an uploaded audio file (Groq Whisper) and build notes.

    Works for lectures with no captions and for videos the server is blocked
    from, because the user supplies the audio directly.
    """
    if not audio_bytes:
        raise ValueError("🎧 The uploaded audio file appears to be empty.")
    transcript = transcribe_audio_groq(audio_bytes, filename)
    vid = "audio_" + _hashlib.md5(audio_bytes).hexdigest()[:11]
    return _build_from_transcript(transcript, "auto", vid, medium)



# ─────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────

def ask_lecture(
    question: str,
    video_id: str,
    topic_info: dict | None = None,
    chat_history: list | None = None,
):
    """Chat about lecture (streaming)."""
    if not question or not question.strip():
        yield "Please ask a specific question about the lecture."
        return
    
    # Load vector store (Qdrant in prod, local Chroma fallback)
    from src.core.vector_store import load_vector_store

    key = make_persist_key("lecture", video_id)
    db = load_vector_store(key)
    if db is None:
        yield "Please process the lecture first before chatting."
        return

    ctx = similarity_search(db, question.strip(), k=5, label="lecture")
    if not ctx:
        yield "Could not find relevant content in this lecture. Try rephrasing."
        return
    
    topic = topic_info.get("topic", "Unknown") if topic_info else "Unknown"
    paper = topic_info.get("paper", "Unknown") if topic_info else "Unknown"
    
    try:
        chain = CHAT_PROMPT | get_llm()
        for chunk in chain.stream({
            "context": ctx,
            "question": question.strip(),
            "topic": topic,
            "paper": paper,
        }, config=trace_config("lecture-chat")):
            if hasattr(chunk, "content"):
                yield chunk.content
    except Exception as e:
        logger.error(f"Lecture chat failed: {e}")
        yield "⚠️ Could not process your question. Please try again."
