# Candidate Schema and Review Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 阻止错误模型结构进入候选页和生产流程，修复候选审核页的逐字排版与失败交互，并作废当前失真的冒烟候选。

**Architecture:** 新建无依赖的 `content_ops/contracts.py` 作为通用 JSON 数据契约层；候选模块和生产模块在消费数据前调用契约校验。Jinja 页面只负责展示已验证数据，浏览器交互通过 `data-*` 和事件监听实现。

**Tech Stack:** Python 3.11、unittest、Jinja2、原生 JavaScript、PyYAML

## Global Constraints

- 不新增第三方依赖。
- 模型输出在落盘或创建任务目录前校验。
- 保留现有视觉语言与本地人工审核流程。
- `wiki/smoke-test.md` 只能用于连通性测试，不能作为真实需求证据。
- 所有实现使用测试驱动的红—绿—重构循环。

---

### Task 1: 通用数据契约

**Files:**
- Create: `content_ops/contracts.py`
- Create: `tests/test_contracts.py`

**Interfaces:**
- Produces: `require_mapping(value, label) -> dict`
- Produces: `require_exact_fields(value, fields, label) -> None`
- Produces: `require_nonempty_string(value, label) -> str`
- Produces: `require_string_list(value, label, allow_empty=False) -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
def test_string_is_not_accepted_as_string_list():
    with self.assertRaisesRegex(ValueError, "candidate.demand_evidence must be a list"):
        require_string_list("逐字错误", "candidate.demand_evidence")

def test_exact_fields_rejects_extras():
    with self.assertRaisesRegex(ValueError, "unexpected fields"):
        require_exact_fields({"a": 1, "b": 2}, {"a"}, "value")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_contracts -v`
Expected: FAIL because `content_ops.contracts` does not exist.

- [ ] **Step 3: Implement minimal validators**

```python
def require_string_list(value, label, allow_empty=False):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    if not allow_empty and not value:
        raise ValueError(f"{label} must not be empty")
    for index, item in enumerate(value):
        require_nonempty_string(item, f"{label}[{index}]")
    return value
```

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m unittest tests.test_contracts -v`
Expected: all contract tests PASS.

### Task 2: 候选响应严格校验

**Files:**
- Modify: `content_ops/candidates.py`
- Modify: `content_ops/prompts.py`
- Modify: `tests/test_candidates.py`

**Interfaces:**
- Consumes: validators from `content_ops.contracts`
- Produces: `validate_candidate(candidate, label) -> None`

- [ ] **Step 1: Add regression tests for string lists, non-list top level and duplicate IDs**

```python
def test_candidate_string_evidence_fails_clearly(self):
    model = SingleCandidateModel(candidate("bad", demand_evidence="逐字错误"))
    with self.assertRaisesRegex(ValueError, "candidate.demand_evidence must be a list"):
        generate_candidate_batch("2026-07-13", [{"id": "s1"}], model)
```

- [ ] **Step 2: Run candidate tests and verify RED**

Run: `python -m unittest tests.test_candidates -v`
Expected: new malformed-shape tests FAIL.

- [ ] **Step 3: Validate candidate types and strengthen prompt schema**

Validate exact candidate keys, non-empty string fields, list fields, unique IDs and exact score schema before scoring. Extend `CANDIDATE_SYSTEM` with explicit JSON types.

- [ ] **Step 4: Run candidate tests and verify GREEN**

Run: `python -m unittest tests.test_candidates -v`
Expected: all candidate tests PASS.

### Task 3: 生产阶段结构校验

**Files:**
- Modify: `content_ops/production.py`
- Modify: `content_ops/prompts.py`
- Modify: `tests/test_production.py`

**Interfaces:**
- Consumes: validators from `content_ops.contracts`
- Produces: `_validate_source_pack`, `_validate_master`, `_validate_platform_copy`, `_validate_packaging`

- [ ] **Step 1: Add malformed source-pack and packaging tests**

```python
def test_source_pack_string_risks_fails_before_task_creation(self):
    with self.assertRaisesRegex(ValueError, "source_pack.risks must be a list"):
        produce_selected_candidate(...)

def test_packaging_titles_requires_exactly_five_strings(self):
    with self.assertRaisesRegex(ValueError, "packaging.titles must contain exactly 5 items"):
        produce_selected_candidate(...)
```

- [ ] **Step 2: Run production tests and verify RED**

Run: `python -m unittest tests.test_production -v`
Expected: malformed outputs reach later code or fail with the wrong message.

- [ ] **Step 3: Implement stage validators and exact prompt types**

Source pack validates sources, claims, risks and markdown; master and platform copy validate non-empty strings; packaging validates exact title/cover/opening counts and non-empty card structures.

- [ ] **Step 4: Run production tests and verify GREEN**

Run: `python -m unittest tests.test_production -v`
Expected: all production tests PASS.

### Task 4: 候选审核页交互和空状态

**Files:**
- Modify: `content_ops/templates/candidates.html.j2`
- Modify: `tests/test_candidate_server.py`

**Interfaces:**
- Consumes: validated candidate batch
- Produces: accessible review HTML without inline candidate JavaScript

- [ ] **Step 1: Add template behavior tests**

```python
def test_page_renders_each_evidence_as_one_item(self):
    self.assertEqual(html.count("<li>"), 2)

def test_page_has_no_inline_onclick_and_has_live_status(self):
    self.assertNotIn("onclick=", html)
    self.assertIn('aria-live="polite"', html)
```

- [ ] **Step 2: Run server tests and verify RED**

Run: `python -m unittest tests.test_candidate_server -v`
Expected: inline-event and empty-state tests FAIL.

- [ ] **Step 3: Implement event listeners, loading recovery, focus and empty state**

Use `document.querySelectorAll('[data-candidate-id]')`, a `try/catch/finally` submit flow, disabled buttons during requests, and an explanatory empty-state article.

- [ ] **Step 4: Run server tests and verify GREEN**

Run: `python -m unittest tests.test_candidate_server -v`
Expected: all server tests PASS.

### Task 5: 作废旧候选、全量验证与发布

**Files:**
- Modify runtime: `content-ops/candidates/2026-07-12.yaml`
- Generated runtime: `content-ops/candidates/2026-07-12.html`

**Interfaces:**
- Consumes: repaired validators and template
- Produces: invalidated old batch and verified local review page

- [ ] **Step 1: Mark old smoke batch invalid**

Set status to `invalid_schema`, clear selectable candidates, and retain an explicit invalid reason without exposing secrets.

- [ ] **Step 2: Run full automated verification**

Run: `python -m unittest discover -s tests -v`
Expected: zero failures and zero errors.

- [ ] **Step 3: Render and inspect desktop and narrow-page screenshots**

Open `http://127.0.0.1:8766/`, verify empty invalid state, then render a valid synthetic candidate and confirm full evidence items, score placement and recoverable button behavior.

- [ ] **Step 4: Check diff and repository hygiene**

Run: `git diff --check` and `git status --short`
Expected: no whitespace errors; only intended source, test and documentation files are tracked.

- [ ] **Step 5: Commit and push**

```text
git add <intended files>
git commit -m "fix: validate AI content schemas and review page"
git push origin main
```
