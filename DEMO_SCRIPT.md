# 🎬 KỊCH BẢN DEMO — Multi-Agent Research Lab

> **Dự án**: Lab 20 — Production-Grade Multi-Agent Research System  
> **Thời lượng**: ~20 phút  
> **Yêu cầu**: Terminal đã activate `.venv`, có `OPENAI_API_KEY` và `ANTHROPIC_API_KEY` trong `.env`

---

## 📋 Tổng quan kịch bản

| Phase | Nội dung | Thời gian |
|-------|----------|-----------|
| 1 | Giới thiệu dự án & Kiến trúc | 3 phút |
| 2 | Show API Routes & Project Structure | 2 phút |
| 3 | Demo Baseline (Single-Agent) | 3 phút |
| 4 | Demo Multi-Agent (Orchestrator-Workers) | 4 phút |
| 5 | Demo Multi-Agent + Critic (Self-correction) | 3 phút |
| 6 | Full Evaluation Pipeline (Judge) | 3 phút |
| 7 | Failure Mode Analysis & Kết luận | 2 phút |

---

## Phase 1: Giới thiệu dự án & Kiến trúc (3 phút)

### 🎤 Lời dẫn

> *"Hôm nay mình sẽ demo Multi-Agent Research Lab — một hệ thống multi-agent production-grade để so sánh hiệu quả giữa single-agent và multi-agent workflow trong tác vụ research. Hệ thống sử dụng pattern Orchestrator-Workers với self-correction loop."*

### Mở README.md — show Architecture Diagram

```bash
# Mở README để show Mermaid diagram
cat README.md | head -32
```

### 🗣️ Key Points cần nói:

1. **6 Agent chuyên biệt**:
   - 🛡️ **Guardrail** — Lọc input (safe / sensitive / out_of_scope / policy_violation)
   - 🧭 **Supervisor** — Orchestrator, quyết định route đến worker nào
   - 🔍 **Researcher** — Tìm kiếm và tổng hợp nguồn
   - 📊 **Analyst** — Trích xuất claims, phân tích gaps
   - ✍️ **Writer** — Viết bài với citations
   - ⚖️ **Critic** (bonus) — Đánh giá chất lượng 4 trục, yêu cầu sửa nếu chưa đạt

2. **Cross-provider architecture**:
   - OpenAI (gpt-4o-mini): Guardrail, Supervisor, Researcher, Analyst
   - Anthropic (claude-haiku-4-5): Writer, Critic, Judge — vì Claude có prose quality tốt hơn

3. **3-tier Search Fallback**: Tavily API → Mock Corpus → LLM Knowledge

---

## Phase 2: Show API Routes & Project Structure (2 phút)

### 🎤 Lời dẫn

> *"Hệ thống cung cấp dual interface — cả CLI lẫn REST API. Mình show routes trước."*

### Command 1: Show API routes

```bash
source .venv/bin/activate
python -m multi_agent_research_lab.cli routes
```

### 📺 Expected Output:

```
┌─────────────────────────── API Routes ────────────────────────────┐
│ Method  │ Path                │ Name                              │
│ POST    │ /run/baseline       │ Run single-agent baseline         │
│ POST    │ /run/multi-agent    │ Run multi-agent workflow          │
│ POST    │ /benchmark/run      │ Run benchmark comparison          │
│ GET     │ /benchmark/{id}     │ Get benchmark results             │
│ GET     │ /trace/{run_id}     │ Get run trace/planning log        │
│ GET     │ /health             │ Liveness check                    │
└───────────────────────────────────────────────────────────────────┘
```

### 🗣️ Key Points:

- **RESTful API** với FastAPI — production-ready, có Swagger UI tại `/docs`
- Dual interface: CLI cho development, API cho integration
- Mỗi endpoint tương ứng 1 CLI command

### Command 2: Show Project Structure

```bash
tree src/multi_agent_research_lab/ -L 2 --dirsfirst
```

### 🗣️ Giải thích cấu trúc:

> *"Codebase tổ chức theo clean architecture: agents/ chứa 6 agent, mỗi agent có prompt template riêng trong prompts/ folder. core/ chứa schemas, state management, pricing. graph/ chứa workflow orchestration. evaluation/ chứa benchmark và LLM-as-Judge."*

---

## Phase 3: Demo Baseline — Single-Agent (3 phút)

### 🎤 Lời dẫn

> *"Bắt đầu với baseline — đây là cách tiếp cận đơn giản nhất: 1 agent duy nhất nhận query, tìm kiếm, và trả lời trực tiếp. Không có planning, không có self-correction."*

### Command:

```bash
python -m multi_agent_research_lab.cli baseline \
  -q "What is GraphRAG and how does it differ from traditional RAG?"
```

### 📺 Expected Output:

```
╭────────────────────────────────────────────────────────────────────╮
│ 🤖 Baseline: What is GraphRAG and how does it differ from ...     │
╰────────────────────────────────────────────────────────────────────╯
WARNING  Tavily search failed: No module named 'tavily'
INFO     Loaded 12 mock documents
INFO     Mock search returned 5 results for: ...
INFO     Baseline: ~434 words, 0 citations

╭──────────────────── Single-Agent Baseline ────────────────────────╮
│ GraphRAG, or Graph-Based Retrieval-Augmented Generation, is ...   │
│ ...                                                               │
╰──────────── ⏱ ~15s | 💰 $0.0004 | 📝 ~434 words ────────────────╯
```

### 🗣️ Phân tích kết quả:

1. **Tavily fallback**: Không có API key → fall back sang mock corpus (12 documents)
2. **Chi phí**: Chỉ ~$0.0004 (rất rẻ với gpt-4o-mini)
3. **Thời gian**: ~15 giây
4. **Hạn chế**: 0 citations, không có self-verification, chỉ 1 LLM call
5. **Chất lượng**: Nội dung tốt nhưng không có structured reasoning

---

## Phase 4: Demo Multi-Agent — Orchestrator-Workers (4 phút)

### 🎤 Lời dẫn

> *"Bây giờ cùng câu hỏi, nhưng dùng multi-agent workflow. Supervisor sẽ orchestrate 4 workers: Researcher tìm nguồn → Analyst phân tích → Writer viết bài. Chú ý planning log ở cuối."*

### Command:

```bash
python -m multi_agent_research_lab.cli multi-agent \
  -q "Compare GraphRAG vs traditional RAG approaches, including pros and cons, in 500 words"
```

### 📺 Expected Output:

```
╭────────────────────────────────────────────────────────────────────╮
│ 🧭 multi-agent: Compare GraphRAG vs traditional RAG ...           │
╰────────────────────────────────────────────────────────────────────╯
INFO     Starting multi-agent workflow
INFO     Guardrail: SAFE ✓
INFO     Supervisor → researcher (iteration 1)
INFO     Executing worker: researcher
INFO     Mock search returned 5 results
INFO     Supervisor → analyst (iteration 2)
INFO     Executing worker: analyst
INFO     Analyst extracted 8 claims, 2 gaps found
INFO     Supervisor → researcher (iteration 3)    ← self-correction!
INFO     Executing worker: researcher
INFO     Supervisor → writer (iteration 4)
INFO     Executing worker: writer (claude-haiku-4-5)
INFO     Supervisor decided: done

╭──────────────────── Multi-Agent Result ───────────────────────────╮
│ [Bài viết 500 words với citations]                                │
│ ...                                                               │
│ Citations:                                                        │
│   📎 [1] Microsoft Research - From Local to Global...             │
│   📎 [2] GraphRAG implementation benchmark...                     │
╰──── ⏱ ~35s | 💰 $0.0017 | 📝 ~500 words | 🔄 5 iterations ─────╯

┌──────────────── Planning Log ─────────────────┐
│ Iter │ Agent      │ Reason                     │
│ 1    │ researcher │ Need sources for query      │
│ 2    │ analyst    │ Analyze research findings   │
│ 3    │ researcher │ Fill knowledge gaps          │ ← gap-filling!
│ 4    │ writer     │ Ready to write final answer │
│ 5    │ done       │ Answer complete             │
└───────────────────────────────────────────────┘
```

### 🗣️ Phân tích kết quả:

1. **Orchestrator-Workers pattern**: Supervisor quyết định route dựa trên state hiện tại
2. **Self-correction loop**: Analyst phát hiện 2 gaps → Supervisor gửi lại Researcher → fill gaps
3. **Cross-provider**: Writer dùng Claude (claude-haiku-4-5) cho prose quality
4. **Chi phí**: ~$0.0017 (~4x baseline) — nhưng chất lượng cao hơn đáng kể
5. **Citations**: Multi-agent produce citations, baseline thì không
6. **Planning log**: Transparent — có thể trace được toàn bộ reasoning chain

### 🗣️ So sánh nhanh:

> | Metric | Baseline | Multi-Agent |
> |--------|----------|-------------|
> | Cost | $0.0004 | $0.0017 |
> | Latency | ~15s | ~35s |
> | Citations | 0 | 2-5 |
> | Self-correction | ❌ | ✅ |
> | Structured reasoning | ❌ | ✅ |

---

## Phase 5: Demo Multi-Agent + Critic (3 phút)

### 🎤 Lời dẫn

> *"Bây giờ bật Critic agent — đây là bonus feature. Critic sẽ đánh giá bài viết trên 4 trục (factual, coherence, completeness, citation) và yêu cầu Writer sửa lại nếu score dưới 7/10."*

### Command:

```bash
python -m multi_agent_research_lab.cli multi-agent \
  -q "Research the state-of-the-art in agentic AI frameworks, identify gaps, and suggest future directions" \
  --critic
```

### 📺 Expected Output:

```
╭────────────────────────────────────────────────────────────────────╮
│ 🧭 multi-agent + critic: Research the state-of-the-art ...        │
╰────────────────────────────────────────────────────────────────────╯
INFO     Guardrail: SAFE ✓
INFO     Supervisor → researcher (1)
INFO     Supervisor → analyst (2)
INFO     Analyst: 10 claims, 3 gaps
INFO     Supervisor → researcher (3)     ← gap-filling
INFO     Supervisor → writer (4)
INFO     Writer produced 600 words (claude-haiku-4-5)
INFO     Supervisor → critic (5)         ← quality review!
INFO     Critic score: 7.5/10 — PASS ✓
INFO     Supervisor decided: done

╭──────────────────── Multi-Agent Result ───────────────────────────╮
│ [Bài viết chi tiết với citations]                                 │
╰──── ⏱ ~40s | 💰 $0.0019 | 📝 ~600 words | 🔄 6 iterations ─────╯
```

### 🗣️ Key Points:

1. **Critic agent**: Thêm chỉ ~$0.0002 nhưng đảm bảo quality gate
2. **4-axis rubric**: factual, coherence, completeness, citation_quality
3. **Revision loop**: Nếu score < 7 → Writer phải sửa lại (có thể loop 1-2 lần)
4. **Trade-off**: Thêm 3-5s latency, nhưng output quality ổn định hơn

---

## Phase 6: Full Evaluation Pipeline (3 phút)

### 🎤 Lời dẫn

> *"Cuối cùng, chạy full evaluation pipeline — đây là command chạy tất cả: baseline → multi-agent → critic → LLM-as-Judge scoring → generate report. Để tiết kiệm thời gian demo, mình chạy với 2 queries."*

### Command (rút gọn cho demo):

```bash
python -m multi_agent_research_lab.cli evaluate \
  -q "What is GraphRAG?,Compare single-agent and multi-agent workflows" \
  --skip-critic
```

### 📺 Expected Output:

```
╭────────────────────────────────────────────────────────────────────╮
│ 🔬 Full Evaluation Pipeline                                       │
│ baseline → multi-agent → multi-agent+critic → judge → report      │
╰────────────────────────────────────────────────────────────────────╯
Queries: 2 | Modes: baseline, multi-agent
Total runs: 4

━━━ Query 1/2 ━━━
What is GraphRAG?

  [1/4] Running baseline...     ✓ ⏱ 12s | 💰 $0.0003 | 📝 350w | 🔗 0 cites
  [2/4] Running multi-agent...  ✓ ⏱ 30s | 💰 $0.0015 | 📝 480w | 🔗 3 cites

━━━ Query 2/2 ━━━
Compare single-agent and multi-agent workflows

  [3/4] Running baseline...     ✓ ⏱ 14s | 💰 $0.0004 | 📝 400w | 🔗 0 cites
  [4/4] Running multi-agent...  ✓ ⏱ 38s | 💰 $0.0018 | 📝 550w | 🔗 4 cites

━━━ LLM-as-Judge Scoring (Claude) ━━━

  Judging [baseline] What is GraphRAG?...       ✓ avg=3.5/5
  Judging [multi-agent] What is GraphRAG?...    ✓ avg=4.2/5
  ...

━━━ Pairwise Comparisons ━━━

  Comparing: What is GraphRAG?...               ✓ Winner: B (multi-agent)
  Comparing: Compare single-agent and multi...  ✓ Winner: B (multi-agent)

━━━ Generating Report ━━━

  📄 Raw data: reports/evaluation_results.json
  📋 Report:   reports/evaluation_report.md

┌─────────────── 🔬 Evaluation Complete ────────────────┐
│ Mode        │ Avg Latency │ Avg Cost │ Avg Words │ ... │
│ baseline    │ 13.0s       │ $0.0004  │ 375       │ 3.4 │
│ multi-agent │ 34.0s       │ $0.0017  │ 515       │ 4.1 │
└───────────────────────────────────────────────────────┘

✅ Reports saved to reports/
```

### Sau đó show report:

```bash
cat reports/evaluation_report.md
```

### 🗣️ Key Points:

1. **LLM-as-Judge**: Dùng Claude (cross-provider) để đánh giá — tránh bias khi OpenAI judge chính nó
2. **4 axes**: accuracy, completeness, coherence, citation_quality (1-5 mỗi trục)
3. **Pairwise comparison**: So sánh trực tiếp baseline vs multi-agent cho cùng 1 query
4. **Auto-generated reports**: JSON (raw data) + Markdown (human-readable)

---

## Phase 7: Failure Mode Analysis & Kết luận (2 phút)

### 🎤 Lời dẫn

> *"Cuối cùng, mình muốn nói về failure modes — vì production system cần handle edge cases."*

### Show failure mode report:

```bash
cat reports/failure_mode.md
```

### 🗣️ 5 Failure Modes đã xử lý:

| # | Failure Mode | Mitigation |
|---|-------------|------------|
| 1 | Search API unavailable | 3-tier fallback: Tavily → Mock → LLM |
| 2 | JSON parse failures (~5%) | Fallback extraction + defaults |
| 3 | Context length limits | Cap 10 sources, summarize trước khi pass |
| 4 | Analyst over-requesting | Hard cap 2 research loops |
| 5 | Critic value assessment | Retained — adds ~$0.0002, improves citations |

### 🗣️ Kết luận:

> *"Tóm lại, hệ thống multi-agent research lab này demonstrate được:"*

1. ✅ **Orchestrator-Workers pattern** với Supervisor routing
2. ✅ **Self-correction loop** qua Analyst gap-filling → Researcher
3. ✅ **Quality gate** qua Critic agent (4-axis rubric)
4. ✅ **Cross-provider architecture** (OpenAI + Anthropic)
5. ✅ **Production guardrails**: cost cap, timeout, max iterations, input filtering
6. ✅ **Structured observability**: Planning log, cost tracking, Rich logging
7. ✅ **Dual interface**: CLI + REST API
8. ✅ **Automated evaluation**: LLM-as-Judge + pairwise comparison

> *"Kết quả benchmark cho thấy multi-agent tốn ~4x chi phí nhưng cho output chất lượng cao hơn đáng kể, đặc biệt với complex synthesis tasks. Recommendation: dùng baseline cho simple queries, multi-agent cho synthesis, multi-agent+critic cho high-stakes output."*

---

## 🚀 Quick Commands Reference (Cheat Sheet)

```bash
# Activate environment
source .venv/bin/activate

# Phase 2: Routes
python -m multi_agent_research_lab.cli routes

# Phase 3: Baseline
python -m multi_agent_research_lab.cli baseline \
  -q "What is GraphRAG and how does it differ from traditional RAG?"

# Phase 4: Multi-agent
python -m multi_agent_research_lab.cli multi-agent \
  -q "Compare GraphRAG vs traditional RAG approaches, including pros and cons, in 500 words"

# Phase 5: Multi-agent + Critic
python -m multi_agent_research_lab.cli multi-agent \
  -q "Research the state-of-the-art in agentic AI frameworks, identify gaps, and suggest future directions" \
  --critic

# Phase 6: Full evaluation (short version)
python -m multi_agent_research_lab.cli evaluate \
  -q "What is GraphRAG?,Compare single-agent and multi-agent workflows" \
  --skip-critic

# Phase 6: Full evaluation (all 9 queries, including critic)
python -m multi_agent_research_lab.cli evaluate

# Bonus: Start API server
python -m multi_agent_research_lab.cli serve
# Rồi mở browser: http://localhost:8000/docs

# Bonus: Test API với curl
curl -s -X POST http://localhost:8000/run/baseline \
  -H "Content-Type: application/json" \
  -d '{"query": "What is GraphRAG?"}' | python -m json.tool
```

---

## ⚠️ Lưu ý trước khi demo

1. **Kiểm tra `.env`** có `OPENAI_API_KEY` và `ANTHROPIC_API_KEY`
2. **Activate venv**: `source .venv/bin/activate`
3. **Test nhanh**: `python -m multi_agent_research_lab.cli --help`
4. **Internet**: Không cần Tavily — mock corpus sẽ tự động fallback
5. **Chi phí ước tính**: Full demo ~$0.02-0.05 (rất rẻ với mini models)
6. **Nếu bị timeout**: Giảm query complexity hoặc tăng `TIMEOUT_SECONDS` trong `.env`
