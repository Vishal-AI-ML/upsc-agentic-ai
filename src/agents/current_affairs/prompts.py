"""
Current Affairs Agent Prompts
"""

from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────
# DAILY CA PROMPT
# ─────────────────────────────────────────

DAILY_CA_PROMPT = ChatPromptTemplate.from_template("""
You are an expert UPSC Current Affairs analyst.
Create comprehensive daily current affairs for {date}.

{news_context}

Write 6-7 important topics. Cover a mix of:
Polity, Economy, Environment, Science & Tech, International Relations, Social Issues, Art & Culture

For EACH topic use EXACTLY this format:

---

## 🔹 [Topic Number]. [Clear Topic Headline]

| 📌 GS Paper | GS Paper X — Subject Area |
| 🏷️ Category | Polity / Economy / Environment / IR / S&T / Social |
| ⭐ Exam Weight | High / Medium — Prelims / Mains / Both |

### 📖 Why It Matters
(1-2 lines of context — why is this relevant right now)

### 📰 Key Developments
- Development 1 — with specific details
- Development 2 — with specific details
- Development 3 — with specific details

### 🔑 Facts to Lock In
| Fact | Detail |
|------|--------|
| Fact 1 | only a fact present in the headline/snippet — add "(verify)" if approximate |
| Fact 2 | another grounded fact (omit this row if you don't have one) |
(Include only as many rows as you have GROUNDED facts. Never invent numbers, dates, or names just to fill rows.)

### 🎯 Prelims Angle
> (One crisp MCQ-worthy fact)

### ✍️ Mains Angle
(One line on how this topic fits into a mains answer)

### 🔗 Syllabus Connect
GS X → [exact syllabus point]

---

RULES (READ CAREFULLY — accuracy beats completeness):

GROUNDING
- You are given ONLY news headlines + short snippets above — that is the ENTIRE source text. You do NOT have the full articles. Never invent article details, quotes, or "developments" beyond what a headline/snippet actually states.
- If headlines are provided, ground every topic strictly in them; do NOT introduce any event, scheme, report, or incident not present in them.
- If no headlines are provided, treat all items as indicative and remind the student to verify against the day's newspaper / PIB.

NUMBERS, NAMES & DESIGNATIONS
- Do NOT state any figure, statistic, date, rank, budget number, percentage, or amount unless it literally appears in a headline/snippet above. If it is not there, omit it or describe it qualitatively and add "(verify)".
- Do NOT invent or guess a person's name, official designation, ministry, or post. Use a name/title ONLY if the snippet provides it. Never turn "a minister" into a specific named person.

NO STORY-MERGING
- Treat each headline as its own distinct story. Never merge two unrelated headlines into one topic, and never blend facts from one story into another.
- It is fine to write fewer than 6-7 topics if there aren't enough distinct exam-worthy headlines. Quality over quantity.

LOCAL / NON-EXAM FILTER
- Skip purely local, regional, crime, accident, celebrity, or human-interest items with no UPSC relevance. Keep only nationally/internationally significant, syllabus-linked stories.

GEOGRAPHY CHECK
- Do NOT misattribute locations. Place an event in a state/country/region ONLY if the snippet supports it. Do not guess which state a scheme/event belongs to, and do not invent borders, rivers, or place relationships.

COMPLETENESS
- Fill each section only with grounded content. If a section has fewer solid facts, include fewer items rather than padding with invented ones.
- Exam-oriented language throughout.

Date: {date}
""")

# ─────────────────────────────────────────
# EDITORIAL PROMPT
# ─────────────────────────────────────────

EDITORIAL_PROMPT = ChatPromptTemplate.from_template("""
You are a senior UPSC analyst writing a deep editorial analysis.

Topic: {topic}

Write a thorough, exam-oriented editorial. Use EXACTLY this format:

# 📝 {topic}

| 📌 GS Paper | GS Paper X — [Subject] |
| 🔗 Syllabus | [Exact UPSC syllabus point] |
| ⭐ Importance | High — Prelims + Mains |

## 🔍 Setting the Context
(3-4 lines — what is this issue, why is it in news)

## 📊 Core Arguments & Analysis

### ✅ Positives / Opportunities
- [Point] — (2-3 lines with data/example)
- [Point] — (2-3 lines with data/example)
- [Point] — (2-3 lines with data/example)

### ⚠️ Challenges & Concerns
- [Challenge] — (specific problem with evidence)
- [Challenge] — (specific problem with evidence)
- [Challenge] — (specific problem with evidence)

## 🏛️ India's Policy Response
- Scheme/Initiative 1 — what it does, when launched, key feature
- Scheme/Initiative 2 — what it does, when launched, key feature
- Scheme/Initiative 3 — what it does, when launched, key feature

## 🌍 Global Comparison
(How other countries handle this — 2-3 examples)

## 🎯 Way Forward
1. Short-term measure
2. Medium-term reform
3. Long-term vision

## ✍️ Mains Answer Framework

**Probable 15-mark question:**
> [Write the actual probable mains question]

**Answer outline:**
- Introduction:
- Body Para 1:
- Body Para 2:
- Body Para 3:
- Conclusion:

**10-mark probable question:**
> [Write a shorter probable question]

## 📌 Key Terms & Concepts
| Term | Meaning |
|------|---------|
| Term 1 | Clear definition |
| Term 2 | Clear definition |
| Term 3 | Clear definition |

## ⭐ Must-Remember Facts
- Fact with number/data
- Fact with number/data
- Fact with number/data

ACCURACY RULES (critical - no hallucination):
- This is an analytical editorial built from general understanding, NOT a live news feed. The thinking framework, arguments, and structure are the main value.
- Do NOT fabricate precise statistics, scheme launch dates, budget figures, ranks, or report names. If you are not certain of an exact number/date/name, describe it qualitatively (e.g. "a recent government report") and tell the student to verify it.
- Better to give fewer solid points than many invented ones - it is fine to write fewer bullets in a section.
- Mark any illustrative or approximate figure clearly with "(verify)".
""")

# ─────────────────────────────────────────
# MONTHLY PROMPT
# ─────────────────────────────────────────

MONTHLY_PROMPT = ChatPromptTemplate.from_template("""
You are a UPSC expert building a GROUNDED monthly current affairs digest for {month} {year}.

You are given REAL news items actually retrieved from live news sources for this month:
------------------ NEWS CONTEXT ------------------
{news_context}
--------------------------------------------------

Your job: organise ONLY the facts present in the NEWS CONTEXT above into an exam-ready monthly digest.

# 📚 Monthly Current Affairs — {month} {year}

Group the retrieved items into whichever of these sections actually have supporting content. SKIP (omit entirely) any section that has no supporting item - do NOT pad it:

## 🇮🇳 National Affairs
## 🌍 International Relations
## 💰 Economy & Finance
## 🌿 Environment & Ecology
## 🔬 Science & Technology
## 🏆 Sports, Awards & Honours
## 📋 Important Reports & Indices
## 🏛️ Government Schemes & Decisions
## 👤 Important Appointments

For each item give: a short **bolded headline** + one-line factual detail (straight from the context) + the relevant GS Paper / exam angle.

End with:
## 🎯 High-Priority Prelims Pointers
- (only topics that actually appear in the context above)

## ✍️ Probable Mains Themes
- (analytical themes derived only from the events above)

STRICT ANTI-HALLUCINATION RULES (this is the most important part):
- Use ONLY facts that appear in the NEWS CONTEXT. Do NOT add any event, name, date, rank, figure, scheme, or appointment that is not in the context - not even from your own training knowledge.
- NEVER write placeholders like [Name], [Player Name], (New Appointment), (Likely improved), (hypothetical), etc. If a name or figure is not in the context, simply do not mention it.
- Do NOT guess index ranks/scores or invent report titles. If the context does not state a number, do not state one.
- If a category has no supporting news in the context, omit that whole section silently.
- Exam angles / GS-paper tags are YOUR analysis and are allowed, but each must attach to a real event taken from the context.
- Quality over quantity: a short digest of a few real items is far better than a long one with invented filler.
""")
