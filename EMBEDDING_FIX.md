# Embedding dimension mismatch fix (retrieval error)

## Error
```
Tool 'knowledge_base_search' raised: Existing Qdrant collection is configured
for dense vectors with 768 dimensions. Selected embeddings are 3072-dimensional.
```

## Asli wajah (RAG-upgrade code se related NAHI)
- Tera Qdrant collection **768-dim** se index hua tha.
- `gemini-embedding-001` **default 3072-dim** vectors banata hai.
- 768 vs 3072 mismatch -> `knowledge_base_search` fail -> deep sawaalon pe
  "technical issue". (Trivial sawaal LLM se seedhe aate hain, isliye "DPSP kya hai"
  chal gaya tha.)

## Pehla attempt kyun fail hua (important)
`output_dimensionality` ko `GoogleGenerativeAIEmbeddings(...)` ke **constructor**
me daala tha -- par langchain-google-genai isko constructor field ke roop me
**ignore** kar deta hai. Wo sirf **har embed call** (embed_query/embed_documents)
ka kwarg hai. Isliye embeddings 3072 hi bante rahe.

## Asli fix (ab)
`src/core/vector_store.py` me ek chhota wrapper `_DimPinnedEmbeddings` add kiya
jo **har embed call pe** `output_dimensionality` inject karta hai. Ab embeddings
sach me 768-dim banenge -> existing collection se match -> **koi re-indexing
nahi** chahiye.

| File | Change |
|------|--------|
| `src/core/config.py` | `gemini_embedding_dim: int = 768` |
| `src/core/vector_store.py` | `_DimPinnedEmbeddings` wrapper + `_make_gemini_embeddings` use karta hai |

## Steps
1. Zip extract kar (2 files overwrite):
   ```powershell
   cd E:\upsc-agentic-ai
   Expand-Archive "$HOME\Downloads\embedding-fix-v2.zip" -DestinationPath . -Force
   ```
2. **Pehle confirm kar ki dimension ab 768 hai** (server chalane se pehle):
   ```powershell
   uv run python -c "from src.core.vector_store import get_embeddings; print('dim =', len(get_embeddings().embed_query('test')))"
   ```
   Output **`dim = 768`** aana chahiye. (Pehle 3072 aata tha.)
3. Server restart:
   ```powershell
   uv run uvicorn src.api.main:app --reload
   ```
4. Ek **alag deep sawaal** pooch (cache bypass ke liye), jaise:
   "Minerva Mills judgment me Supreme Court ne kya kaha tha, detail me"

## Log me ye dikhna chahiye (success)
- `mentor model tier=strong (...)`
- Koi `knowledge_base_search raised: ...dimension...` **NAHI**
- Koi `cross-encoder rerank skipped` / `multi-query expansion failed` **NAHI**
- Jawab knowledge base se, real content ke saath

## Agar `dim = 768` aaye par jawab phir bhi kamzor lage
Iska matlab collection kisi ALAG 768-model se bana tha (vector space alag).
Tab 3072 pe shift karke re-index karna behtar:
1. `.env`: `GEMINI_EMBEDDING_DIM=3072`
2. Qdrant collection **recreate + re-index** (NCERT/PYQ/docs dobara ingest).
3. Restart.
> Bina re-index kiye 3072 mat karna -- wahi mismatch error wapas aayega.

## Note
- `gemini_embedding_dim = 0` -> koi dimension force nahi (bilkul purana behaviour).
  100% backward-compatible + reversible.
