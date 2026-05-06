# Lab 20 — Multi-Agent Research System: Plan triển khai

> Plan này hợp nhất: yêu cầu starter repo, tinh thần *Anthropic — Building effective agents*,
> và các ràng buộc bổ sung của giảng viên (model rẻ, kiến trúc cố định, FastAPI + CLI).

---

## 0. Triết lý xuyên suốt

Bài này thực ra là **orchestrator-workers workflow**, không phải "autonomous agent" theo
nghĩa Anthropic (LLM tự do tool-call vô hạn). Ba nguyên tắc cốt lõi cần thấm vào code:

1. **Simplicity** — chạy baseline "augmented LLM" (1 LLM + search) nghiêm túc trước,
   chỉ thêm complexity khi đo được giá trị tăng thêm.
2. **Transparency** — mỗi quyết định routing phải được log với `reason`, không chỉ kết quả.
3. **ACI (Agent-Computer Interface)** — tool description quan trọng ngang prompt design.

Đề bài thật sự không phải "multi-agent đẹp hơn single-agent" mà là **chứng minh kiến trúc
multi-agent giúp model rẻ vượt qua chính nó nhờ self-correction loop**.

### 0.1 Mapping với Lab Guide chính thức

Plan này phân thành 8 phase chi tiết, nhưng phải cover đủ 4 milestone của Lab Guide:

| Lab Guide milestone | Phase tương ứng trong plan |
|---|---|
| M1 — Baseline | Phase 1 (LLM client) + Phase 4 (`graph/baseline.py`) |
| M2 — Supervisor | Phase 3 (`agents/supervisor.py`) + Phase 4 (`graph/workflow.py`) |
| M3 — Worker agents | Phase 3 (researcher / analyst / writer) |
| M4 — Trace + benchmark | Phase 5 (observability) + Phase 7 (benchmark + report) |

### 0.2 Justify Critic agent (đối chiếu rule "không thêm agent vô lý")

Lab Guide ghi rõ: *"không thêm agent nếu không có lý do rõ ràng, mỗi agent phải có
responsibility riêng"*. Critic agent của plan này **không vi phạm** vì:

- Researcher/Analyst/Writer có chung blind spot: cùng "phe" tạo ra output, không ai
  dám phủ nhận chất lượng cuối.
- Critic có **responsibility orthogonal**: chấm điểm draft theo rubric độc lập, không
  tham gia tạo content.
- Giải quyết một failure mode đo được: Writer thường trả output thiếu citation hoặc
  lệch word_count → Critic flag → revision 1 lần.
- Nếu benchmark cho thấy Critic không cải thiện quality > 0.5 điểm trên rubric 10,
  **bỏ Critic** và ghi chú vào failure_mode.md. Đây mới là tinh thần Anthropic.

---

## 1. Ba ràng buộc bổ sung của giảng viên

### Ràng buộc 1 — Dùng model rẻ nhất có thể

Không dùng Opus/GPT-4o cho worker rồi khoe output đẹp. Phải đẩy chất lượng bằng kiến
trúc, không phải bằng sức mạnh model thô.

| Vai trò             | Model đề xuất         | Lý do |
|---------------------|-----------------------|-------|
| Guardrail filter    | `claude-haiku-4-5`    | Classify nhạy cảm, output 1 token |
| Supervisor router   | `gpt-4o-mini` hoặc `claude-haiku-4-5` | Structured decision |
| Researcher          | `gpt-4o-mini`         | Tool-calling search, summarize |
| Analyst             | `claude-haiku-4-5`    | Critique + gap analysis |
| Writer              | `claude-haiku-4-5`    | Prose tự nhiên |
| Critic (bonus)      | `gpt-4o-mini`         | Cross-provider giảm bias đồng thuận |
| **Judge benchmark** | `claude-sonnet-4-6` hoặc `gpt-4o` | Chỉ chạy offline 1 lần |
| Baseline single     | `gpt-4o-mini`         | So sánh fair với multi-agent rẻ |

**Năm đòn bẩy để model rẻ ra output ngang model đắt:**

1. Query decomposition (Researcher chia 2-3 sub-query).
2. Loop self-correction (Analyst flag gaps → quay lại Researcher tối đa 2 lần).
3. Critic review + Writer revision (1 lần).
4. Schema validation chặt → bắt hallucination format ngay.
5. Few-shot trong system prompt → output style stable.

### Ràng buộc 2 — Bắt buộc tuân thủ kiến trúc repo

Bảy folder top-level (`agents/`, `core/`, `graph/`, `services/`, `evaluation/`,
`observability/`, `cli.py`) là cố định. Mọi extension phải fit vào subfolder bên trong.

### Ràng buộc 3 — FastAPI + CLI dual interface

CLI gọi vào FastAPI endpoints. Lệnh `cli routes` show toàn bộ endpoints — vừa để demo
vừa để sanity check.

---

## 2. Cấu trúc repo cuối cùng

```text
src/multi_agent_research_lab/
├── agents/
│   ├── prompts/
│   │   ├── supervisor.md
│   │   ├── researcher.md
│   │   ├── analyst.md
│   │   ├── writer.md
│   │   ├── critic.md            # bonus
│   │   └── guardrail.md
│   ├── base.py                  # AgentProtocol
│   ├── supervisor.py
│   ├── researcher.py
│   ├── analyst.py
│   ├── writer.py
│   ├── critic.py                # bonus
│   └── guardrail.py
├── core/
│   ├── config.py                # Pydantic Settings từ .env + YAML
│   ├── state.py                 # AgentState TypedDict
│   ├── schemas.py               # ResearchNote, AnalysisNote, ...
│   ├── errors.py                # LLMError, MaxIterationsExceeded, ...
│   └── pricing.py               # Cost calc theo bảng giá
├── graph/
│   ├── workflow.py              # LangGraph multi-agent
│   └── baseline.py              # Augmented LLM single-agent
├── services/
│   ├── llm_client.py            # Multi-provider + fallback
│   ├── search_client.py         # Tavily + Mock + LLM-fallback
│   ├── mock_data/
│   │   └── graphrag_corpus.json
│   └── api/                     # FastAPI
│       ├── main.py
│       ├── routers/
│       │   ├── agents.py        # /run/baseline, /run/multi-agent
│       │   ├── benchmarks.py    # /benchmark/run, /benchmark/{id}
│       │   └── traces.py        # /trace/{run_id}
│       └── dependencies.py
├── evaluation/
│   ├── benchmark.py
│   ├── judge.py                 # LLM-as-judge (bonus)
│   ├── queries.yaml
│   └── metrics.py
├── observability/
│   ├── logging.py               # Structured + Rich console
│   ├── tracing.py               # LangSmith/Langfuse hook
│   └── planning_log.py
└── cli.py

configs/
├── default.yaml                 # max_iter, timeout, model assignment
├── pricing.yaml                 # USD per 1M tokens
└── lab_variants.yaml            # baseline / multi / multi+critic

reports/
├── benchmark_report.md          # Deliverable chính
└── failure_mode.md              # Deliverable

tests/
├── test_schemas.py
├── test_supervisor_routing.py   # Mock LLM
├── test_fallback.py             # Provider switch
├── test_guardrail.py
└── test_api.py                  # FastAPI TestClient
```

---

## 3. Plan theo phase

### Phase 0 — Setup (10')

- Clone, venv, `pip install -e ".[dev]"`, copy `.env.example` → `.env`.
- Điền `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Optional: `TAVILY_API_KEY`, `LANGSMITH_API_KEY`.
- `.gitignore` chặn `.env`, `runs/`, `__pycache__/`.
- Pre-commit hook check `git diff` không chứa pattern `sk-`, `ant-` để khỏi leak key.
- `make test` smoke test.

### Phase 1 — Service layer với fallback (30')

**`services/llm_client.py`** — trái tim của fallback strategy.

```python
class LLMClient:
    def __init__(self, primary: ProviderConfig,
                 fallback: ProviderConfig | None = None,
                 max_retries=3, timeout_s=30): ...

    async def complete(self, ...) -> LLMResponse:
        try:
            return await self._call_with_retry(self.primary, ...)
        except (RateLimitError, ProviderError) as e:
            log.warning(f"Primary {self.primary.provider} failed: {e}, falling back")
            if self.fallback:
                return await self._call_with_retry(self.fallback, ...)
            raise
```

`LLMResponse` chứa: `text, input_tokens, output_tokens, latency_ms, provider, model, cost_usd`.
Cost tính ngay tại layer này theo `core/pricing.py`.

**`services/search_client.py`** — fallback chain 3 tầng:

1. **Tavily** (nếu có key)
2. **Mock data** retrieve theo embedding/keyword match từ `mock_data/graphrag_corpus.json`
3. **Direct LLM** với system prompt: "you are a research assistant, answer based on
   training knowledge, mark uncertain with [unverified]"

Mock corpus: 10-15 chunks về GraphRAG (paraphrased từ paper abstracts, không copy nguyên
văn). Method này được chấp nhận vì các search API miễn phí dễ hết quota.

### Phase 2 — Schemas + State (15')

```python
class AgentState(TypedDict):
    query: str
    guardrail_passed: bool
    research_notes: list[ResearchNote]
    analysis_notes: list[AnalysisNote]
    critic_feedback: list[CriticNote] | None
    final_answer: FinalAnswer | None
    planning_log: list[PlanStep]              # transparency
    iteration: int
    total_cost_usd: float
    fallback_events: list[FallbackEvent]
    error: ErrorInfo | None                   # friendly error
```

**Quy tắc vàng:** agent chỉ append vào state, không overwrite — giúp trace dễ và debug được.

### Phase 3 — Agents (50')

**`agents/guardrail.py`** (bắt buộc, bonus):

```python
async def check_query(query: str) -> GuardrailDecision:
    """Returns: {passed: bool, category: str, reason: str}
    Categories: 'safe', 'sensitive', 'out_of_scope', 'policy_violation'
    """
```

Dùng haiku 1 call. Nếu fail → `state.error = friendly message`, skip pipeline.

**`agents/supervisor.py`** — orchestrator-router:

```python
class RouteDecision(BaseModel):
    next_agent: Literal["researcher", "analyst", "writer", "critic", "done"]
    reason: str
    sub_queries: list[str] | None = None
```

**Routing policy — trả lời 5 câu hỏi thiết kế của Lab Guide:**

| Câu hỏi | Quy tắc cụ thể |
|---|---|
| Khi nào gọi **Researcher**? | (a) `research_notes` rỗng, hoặc (b) Analyst flag `needs_more_research=True` và `research_loops < 2`. Pass `sub_queries` từ gaps. |
| Khi nào gọi **Analyst**? | Có ≥ 1 `ResearchNote` và chưa có `AnalysisNote` cho lần research mới nhất. |
| Khi nào gọi **Writer**? | Có `AnalysisNote` với `needs_more_research=False` HOẶC đã đạt `max_research_loops`. |
| Khi nào gọi **Critic** (bonus)? | Có `final_answer` và chưa có `critic_feedback`. Sau Critic: nếu `score < 7/10` → quay lại Writer revise (max 1 lần). |
| Khi nào **stop**? | (a) `final_answer` đã pass Critic, hoặc (b) `iteration >= max_iterations`, hoặc (c) `total_cost_usd >= cost_cap`, hoặc (d) `error != None`. |
| **Agent fail thì sao**? | Retry 3 lần exponential backoff trong `LLMClient`. Hết retry → fallback provider. Vẫn fail → set `error`, route thẳng `done` với friendly message. **Không** dừng cả pipeline ở giữa. |

Logic routing thông minh:
- Query đơn giản (factual lookup) → có thể skip Analyst.
- Query phức tạp → loop Researcher tối đa 2 lần với gaps từ Analyst.
- Tăng `iteration` mỗi lần, max 8.

**`agents/researcher.py`** — augmented LLM với search tool. Tool description theo ACI:
- Có example usage trong docstring.
- Param `query`: "concise search query, 3-8 keywords, avoid full sentences".
- Trả structured output (title, url, snippet, published_date).
- Document boundaries: "use for current/factual info, not opinion synthesis".

**`agents/analyst.py`** — output gồm `claims`, `gaps`, `needs_more_research: bool`,
`confidence: float`.

**`agents/writer.py`** — đọc analysis + (optional) critic feedback. Tôn trọng word_count
constraint từ query.

**`agents/critic.py`** (bonus) — score draft trên 4 axes:
`factual / coherence / completeness / citations`.
Nếu score < threshold → request revision (max 1 lần).

Tách prompt ra file `.md` riêng để A/B test khi benchmark.

### Phase 4 — LangGraph workflow (20')

`graph/workflow.py` (multi-agent) + `graph/baseline.py` (augmented LLM single-agent).
**Cả 2 phải xài cùng search client** để benchmark fair.

```python
graph = StateGraph(AgentState)
graph.add_node("guardrail", guardrail_agent)
graph.add_node("supervisor", supervisor_agent)
graph.add_node("researcher", researcher_agent)
graph.add_node("analyst", analyst_agent)
graph.add_node("writer", writer_agent)
graph.add_node("critic", critic_agent)        # bonus

graph.set_entry_point("guardrail")
graph.add_conditional_edges("guardrail", lambda s: "supervisor" if s["guardrail_passed"] else END)
graph.add_conditional_edges("supervisor", route_fn, {...})

# Worker xong quay về supervisor
for w in ["researcher", "analyst", "writer", "critic"]:
    graph.add_edge(w, "supervisor")
```

**Guardrails bắt buộc:**
- `max_iterations=8`
- `max_research_loops=2`
- `max_total_tokens=50_000` (cost cap)
- `timeout_seconds=120` (asyncio.wait_for)

Tất cả 4 cờ trong `configs/default.yaml`, không hard-code.

### Phase 5 — Logging + Tracing (20')

**`observability/logging.py`** dùng `rich` để console log đẹp:

```text
[14:23:01] 🛡️  Guardrail        passed (safe)              42ms  $0.0001
[14:23:02] 🧭 Supervisor       → researcher (gaps: none)   180ms $0.0003
[14:23:05] 🔍 Researcher       searched 3 sources          2.1s  $0.0012
[14:23:07] 🧭 Supervisor       → analyst                   150ms $0.0003
[14:23:10] 📊 Analyst          3 claims, 2 gaps           1.8s  $0.0008
[14:23:11] 🧭 Supervisor       → researcher (loop 2)       140ms $0.0003
...
```

Phân biệt visual: baseline 1 màu, multi-agent mỗi agent 1 màu (đúng yêu cầu giảng viên).

**Persistence:**
- `runs/<run_id>/events.jsonl` — parsing automation.
- `runs/<run_id>/planning.jsonl` — transparency, paste vào benchmark report.
- LangSmith optional cho ai có key.

### Phase 6 — FastAPI service + CLI (25')

**`services/api/main.py`:**

```python
app = FastAPI(title="Multi-Agent Research Lab", version="0.1")
app.include_router(agents_router, prefix="/run")
app.include_router(benchmarks_router, prefix="/benchmark")
app.include_router(traces_router, prefix="/trace")

@app.get("/")
def root(): return {"docs": "/docs", "version": app.version}
```

**Endpoints:**

| Method | Path | Body / Returns |
|--------|------|----------------|
| POST | `/run/baseline` | `{query}` → `{answer, trace_id, cost, latency}` |
| POST | `/run/multi-agent` | `{query, enable_critic}` → `{..., agents_called}` |
| POST | `/benchmark/run` | `{query_set, modes, repeats}` → `{benchmark_id}` (background) |
| GET | `/benchmark/{id}` | Kết quả + bảng so sánh |
| GET | `/trace/{run_id}` | planning_log + events |
| GET | `/health` | Liveness |

**`cli.py`** dùng Typer:

```python
@app.command()
def serve(host="0.0.0.0", port=8000):
    """Start FastAPI server."""
    uvicorn.run("multi_agent_research_lab.services.api.main:app", host=host, port=port)

@app.command()
def routes():
    """Show all API routes — câu lệnh giảng viên yêu cầu."""
    from .services.api.main import app
    for r in app.routes:
        if hasattr(r, "methods"):
            print(f"{','.join(r.methods):10} {r.path:40} {r.name}")

@app.command()
def baseline(query: str, via_api: bool = False): ...

@app.command()
def multi_agent(query: str, critic: bool = False, via_api: bool = False): ...

@app.command()
def benchmark(suite: str = "default"): ...
```

### Phase 7 — Benchmark + LLM judge (30')

**`evaluation/queries.yaml`** chia 3 tier:

| Tier | Ví dụ | Kỳ vọng |
|---|---|---|
| Simple factual | "Who founded Anthropic?" | Single-agent thắng (latency, cost) |
| Multi-source synthesis | "Compare GraphRAG vs traditional RAG, 500 words" | Multi-agent thắng (quality) |
| Iterative research | "Research SOTA in agentic frameworks, identify gaps" | Multi-agent thắng đậm |

3-5 query/tier × 2-3 mode × 3 lần = ~60 runs.

**5 metric bắt buộc từ Lab Guide:**

| Metric | Cách đo | Implementation |
|---|---|---|
| Latency | Wall-clock time | `time.perf_counter()` quanh graph invoke, log per-agent từ `events.jsonl` |
| Cost | Token usage × bảng giá | `total_cost_usd` accumulate trong state, breakdown VND (×25,000) |
| Quality | **Rubric 0-10 do peer review** (primary) | Form Google Forms, 4 axes × 2.5đ: accuracy / completeness / coherence / citations |
| Citation coverage | Số claims có source / tổng claims chính | Parse `final_answer.citations` vs `analyst.claims`, ratio |
| Failure rate | Số query fail / tổng query | Count run có `state.error != None` hoặc raise exception |

**LLM-as-judge (bonus, không thay thế peer review):**

```python
class JudgeRubric(BaseModel):
    accuracy: int           # 1-5
    completeness: int       # 1-5
    coherence: int          # 1-5
    citation_quality: int   # 1-5
    reasoning: str

async def judge(query, answer_a, answer_b) -> ComparisonResult:
    """Pairwise comparison + rubric, dùng claude-sonnet-4-6 làm judge."""
```

LLM judge có 2 mục đích phụ:
1. Cross-check với peer review — nếu lệch nhiều, ghi chú vào failure_mode.md.
2. Scale lên nhiều query mà không cần kéo người review thủ công.

**Citation coverage — implementation chi tiết** (vì đây là metric dễ làm sai):

```python
def citation_coverage(final: FinalAnswer, claims: list[Claim]) -> float:
    """Ratio of main claims with at least one supporting citation."""
    main_claims = [c for c in claims if c.is_main]   # Analyst flag
    if not main_claims: return 1.0
    covered = sum(1 for c in main_claims if c.citation_ids)
    return covered / len(main_claims)
```

Số này tự nó nói lên một điều: nếu baseline citation_coverage = 0.4 còn multi-agent
= 0.85, đó là **hard evidence** Researcher + Analyst worth their tokens, không cần
peer review chủ quan.

**`reports/benchmark_report.md`** template:
- Setup: model assignment, query set, repeats.
- Bảng tổng hợp 5 metric × (single / multi / multi+critic).
- Cost breakdown VND.
- 3 case study (1 mỗi tier).
- Failure modes + cách fix.
- **Exit ticket** (xem section 7 cuối plan này).
- Conclusion: khi nào multi-agent đáng, khi nào không.

### Phase 8 — README + Demo prep (15')

README phải có:

```markdown
# Multi-Agent Research Lab

## Architecture diagram
[ASCII hoặc mermaid]

## Fallback strategy ⚠️ giảng viên yêu cầu giải thích rõ
- LLM fallback: OpenAI ↔ Anthropic, retry 3 lần exponential backoff
- Search fallback: Tavily → Mock data → Direct LLM
- Timeout: 30s per call, 120s end-to-end
- Friendly error khi fail hoàn toàn

## Guardrails
- Pre-filter classifier (safe / sensitive / out-of-scope / policy_violation)
- Max iterations: 8
- Max research loops: 2
- Cost cap: $X per run

## Quickstart
make install && make test
cli serve              # terminal 1
cli routes             # show endpoints
cli multi-agent --query "..." --critic

## Extra features (bonus)
- [x] Critic agent với revision loop
- [x] LLM-as-judge benchmark automation
- [x] FastAPI dual interface
- [x] Cost tracking + VND conversion
- [x] Mock search fallback chain
- [x] Cross-provider LLM fallback
- [x] Rich console logging với agent-level color coding

## Demo flow
1. cli routes → show endpoints
2. POST /run/baseline → so sánh
3. POST /run/multi-agent --critic → highlight loop
4. GET /benchmark/{id} → bảng so sánh
5. Open LangSmith trace
```

---

## 4. Demo timeline (target < 1h để ăn bonus)

| Mốc    | Task |
|--------|------|
| T+0    | Setup, smoke test |
| T+10'  | LLM client + fallback chạy được |
| T+25'  | Search client + mock data |
| T+35'  | Guardrail + Supervisor + 1 worker |
| T+50'  | Đủ Researcher → Analyst → Writer |
| T+60'  | **Demo lần 1 cho giảng viên** ← bonus |
| T+75'  | Critic agent + FastAPI |
| T+90'  | Benchmark + judge |
| T+105' | Report + README polish |
| T+115' | Tests + push GitHub |

---

## 5. Deliverables checklist

- [ ] GitHub repo cá nhân (không leak API key)
- [ ] `reports/benchmark_report.md` so sánh single vs multi (+critic)
- [ ] `reports/failure_mode.md` (1 trang)
- [ ] Screenshot trace hoặc link LangSmith
- [ ] README đầy đủ: kiến trúc, fallback, guardrail, extra features
- [ ] Demo trước 1h ăn bonus
- [ ] Mock data corpus + ít nhất 9 query benchmark
- [ ] Tests pass: `pytest tests/`

---

## 6. Anti-patterns cần tránh

- **Loop vô hạn ở supervisor:** state không đổi giữa iterations → log iteration count
  ngay từ đầu, đừng đợi debug sau.
- **Context bloat:** history append mãi → cap 20 messages hoặc summarize cũ.
- **Schema mismatch:** LLM trả JSON sai format → dùng `response_format` của OpenAI hoặc
  tool-use của Anthropic, đừng regex parse.
- **Cost runaway khi benchmark:** hard cap token mỗi call và mỗi run, log realtime.
- **Analyst tự gọi Researcher:** vi phạm "supervisor là single source of routing truth",
  trace sẽ rối. Luôn route qua Supervisor.
- **Hard-code model name trong agent code:** đặt trong `configs/default.yaml` để dễ A/B test.
- **Demo output đẹp nhưng không có benchmark:** rubric chấm benchmark report, không
  chấm output nào nhìn xịn nhất.

---

## 7. Exit ticket — draft sẵn để paste vào report

Lab Guide yêu cầu trả lời 2 câu khi nộp. Đừng đợi đến lúc nộp mới nghĩ — viết draft
ngay từ đầu, tinh chỉnh sau khi có benchmark data thật.

### Câu 1: Case nào nên dùng multi-agent? Vì sao?

**Draft:**

Multi-agent đáng dùng khi đồng thời thoả 3 điều kiện:

1. **Query có thể phân tách thành sub-task không tương tự** — ví dụ "research X, compare
   với Y, viết summary 500 từ". Mỗi sub-task có yêu cầu prompt khác nhau (search vs
   critique vs prose), nên specialization có lợi.
2. **Output cần self-correction loop** — câu hỏi mở, không có ground truth ngắn gọn.
   Analyst flag gaps → Researcher search lại là cơ chế bù lỗi không thể có ở single-agent.
3. **Quality matters hơn latency/cost** — vì multi-agent latency × 2-3 và cost × 2-4.

Bằng chứng từ benchmark: tier "iterative research" (X queries), multi+critic đạt
citation_coverage Y vs baseline Z; quality rubric 8.5 vs 6.2.

### Câu 2: Case nào không nên dùng multi-agent? Vì sao?

**Draft:**

Single-agent đủ (hoặc tốt hơn) khi:

1. **Factual lookup ngắn** — "Who founded Anthropic?". Multi-agent overhead lãng phí,
   query này 1 LLM call + search là xong.
2. **Latency-sensitive** — chatbot real-time, người dùng đợi < 3s. Multi-agent end-to-end
   hiếm khi dưới 5s với loop.
3. **Budget chặt** — multi-agent cost gấp 2-4 lần. Nếu volume lớn (10K+ queries/day),
   tier giá quan trọng hơn 0.5đ rubric.
4. **Task có ground truth rõ** — math, code execution, structured extraction. Loop
   self-correction không thêm gì khi output đã verify được tự động.

Bằng chứng: tier "simple factual", baseline cost $0.0008 vs multi $0.0034, latency
1.2s vs 4.5s, **quality bằng nhau** trong rubric 8.0/10.

### Quy tắc rút ra

> Multi-agent là *self-correction architecture*, không phải *better LLM*. Khi không có
> gì để correct, nó chỉ thêm latency và cost.

---