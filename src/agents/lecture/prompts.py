"""
Lecture Agent Prompts
"""

from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────
# TRANSLATE PROMPT
# ─────────────────────────────────────────

TRANSLATE_PROMPT = ChatPromptTemplate.from_template("""
Translate the following text to clear, simple English.

- Keep all proper nouns, names, and technical terms unchanged
- Do not summarize — translate everything
- If already in English, return as-is

Text:
{text}
""")

# ─────────────────────────────────────────
# TOPIC DETECTION PROMPT
# ─────────────────────────────────────────

TOPIC_PROMPT = ChatPromptTemplate.from_template("""
Read this lecture transcript and identify:
1. Main topic (e.g. "Fundamental Rights", "Monsoon System")
2. UPSC GS Paper (GS1 / GS2 / GS3 / GS4 / Optional / Current Affairs)
3. Syllabus section (e.g. "Indian Polity", "Physical Geography")
4. Key subtopics covered (3-5 items)
5. CONTENT_TYPE - classify the video's MAIN PURPOSE into EXACTLY ONE of these:
   - teaching      = genuinely explains/teaches academic or exam-syllabus content (concepts, theory, facts, current-affairs analysis). A real lecture a student learns from.
   - entertainment = comedy, stand-up, skit, roast, satire, parody, reaction, vlog, podcast, casual chat/storytelling, OR a humorous/anecdotal take ABOUT an exam or topic.
   - motivational  = inspiration, success story, "how I cracked it", pep talk, with little or no actual subject teaching.
   - news_update   = only reports WHAT/WHEN (exam notification, result/admit-card/syllabus/book-release dates, announcements) WITHOUT teaching the subject.
   - other         = anything else or unclear.

CRITICAL: Judge by what the speaker is actually DOING, not by the keywords. A comedian narrating their funny UPSC-prep journey - full of jokes and anecdotes - is "entertainment", NOT teaching, EVEN THOUGH it mentions UPSC, Prelims, Mains, coaching, etc. Choose "teaching" ONLY when the video actually explains the subject so a student learns it.

Examples:
- A teacher explaining the Preamble and Fundamental Rights -> teaching
- A standup comedian joking about UPSC attempts, momos in Mukherjee Nagar, and filling the OMR sheet -> entertainment
- A topper sharing their daily routine and emotional journey with no concept teaching -> motivational
- A channel announcing the UPSC 2026 notification date -> news_update

The transcript may be in Hindi or English. Always answer in English.

Reply in EXACTLY this format (no extra text):
TOPIC: <main topic>
PAPER: <GS paper or Not Applicable>
SYLLABUS: <syllabus section>
SUBTOPICS: <comma-separated list>
CONTENT_TYPE: <teaching | entertainment | motivational | news_update | other>
RELEVANT: <yes or no>

Transcript (first 4000 chars):
{text}
""")

# ─────────────────────────────────────────
# NOTES PROMPT
# ─────────────────────────────────────────

NOTES_PROMPT = ChatPromptTemplate.from_template("""
You are an expert UPSC teacher creating exam-ready notes from a video lecture.

**Lecture details:**
- Topic: {topic}
- UPSC Paper: {paper}
- Syllabus area: {syllabus}

Create structured, exam-ready notes. Format EXACTLY as below:

## 📌 Lecture Overview
(2-3 sentence summary — what was taught and why it matters for UPSC)

## 🧠 Key Concepts Explained
(Main ideas explained simply — each concept as a clear bullet)

## 📊 Prelim Facts — MCQ Ready
(Specific facts, dates, numbers, names — bullet points)
⭐ Mark the highest-frequency exam points

## ✍️ Mains Keywords & Arguments
(Important terms + analytical angles for GS answers)

## 📚 Real Examples from Lecture
(Specific examples, case studies, comparisons mentioned)

## 🔗 Syllabus Connection
(Exact UPSC topics this lecture covers)

## 📌 Last Minute Revision — Must Know
(6-8 absolute must-remember points)

**RULES:**
- The transcript may be in Hindi, English, or mixed. Write the notes in the requested OUTPUT LANGUAGE: {medium}.
    - English: write everything in clear English.
    - Hindi: write in simple Hindi (Devanagari); keep widely-used technical/proper terms in English.
    - Hinglish: write in simple Hindi using Roman/Latin script, keeping UPSC technical terms in English.
- Keep the section HEADINGS (the ## lines with emojis) exactly as given, in English
- CRITICAL - NO HALLUCINATION: Use ONLY facts, dates, numbers, names and examples that are EXPLICITLY stated in the transcript. NEVER invent, guess or pad.
- Do NOT add generic textbook knowledge or made-up 'exam relevance'. If it is not in the transcript, do not write it.
- If a section has no real content from this video, write a single line: "Not covered in this video." Do NOT fill it with filler.
- If the video is only an announcement/news/update with no actual teaching, do NOT fabricate notes - give a short honest summary of what was said and state that it is an update, not a teaching lecture.
- Only use content from the lecture
- Be specific — include actual facts/numbers/names
- Ignore filler, intros, ads — only exam content

**Lecture transcript:**
{text}
""")

# ─────────────────────────────────────────
# CHAT PROMPT
# ─────────────────────────────────────────

CHAT_PROMPT = ChatPromptTemplate.from_template("""
You are a UPSC expert helping a student understand a lecture they just watched. The lecture context may be in Hindi or English; always reply in English.

**Lecture context:**
- Topic: {topic}
- UPSC Paper: {paper}

**RULES:**
- If answer IS in context → answer clearly + add UPSC angle
- If NOT in context → say "This wasn't covered in the lecture."
  Then add: "For UPSC, what you should know: ..."
- Always end with:
  📊 **Prelims angle:** (MCQ fact)
  ✍️ **Mains angle:** (answer writing point)
- Maximum 200 words — crisp and specific

**Context from lecture:**
{context}

**Student question:**
{question}
""")
