# Project Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立不依赖聊天记忆的项目规则、机器可读编辑政策、本地状态结构、决策记录和发布检查表。

**Architecture:** `AGENTS.md` 提供最高行为约束，YAML 文件保存稳定政策与本地状态结构，Markdown 文件保存决策理由和人工检查。公开仓库只提交通用规则与示例，本地真实状态继续被 Git 忽略。

**Tech Stack:** Markdown、YAML、Python `unittest`

## Global Constraints

- 不提交真实账号、私人来源、生成稿件、API Key 或本机绝对路径。
- 不改变现有内容生成和发布行为。
- `raw/` 内容只读；平台发布仍由人工完成。
- 使用测试先证明治理文件缺失，再创建最小文件使测试通过。

---

### Task 1: 治理配置回归测试

**Files:**
- Create: `tests/test_governance.py`

**Interfaces:**
- Consumes: `AGENTS.md`、`content-ops/config/editorial-policy.yaml`、`content-ops/config/project-state.example.yaml`
- Produces: 治理文件结构与关键阈值的自动验证

- [ ] **Step 1: Write failing tests**

```python
def test_editorial_policy_keeps_evidence_and_human_gates(self):
    policy = load_yaml(ROOT / "content-ops/config/editorial-policy.yaml")
    self.assertEqual(policy["selection"]["minimum_total_score"], 75)
    self.assertEqual(policy["human_gates"], ["topic_selection", "final_review", "platform_publish"])
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest tests.test_governance -v`
Expected: FAIL because governance files do not exist.

- [ ] **Step 3: Create the minimal policy and state example**

Add the exact selection thresholds, evidence ladder, cold-start mix, stop conditions, human gates and public/private state fields.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m unittest tests.test_governance -v`
Expected: all governance tests PASS.

### Task 2: Codex project constitution and human documents

**Files:**
- Create: `AGENTS.md`
- Create: `docs/DECISIONS.md`
- Create: `docs/content-release-checklist.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: governance design and YAML policy
- Produces: startup/shutdown protocol, stable decisions, release checklist and discoverable documentation links

- [ ] **Step 1: Add constitution-content assertions**

Extend `tests/test_governance.py` to require startup reads, source boundaries, no automatic publishing, conflict reporting and final verification.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest tests.test_governance -v`
Expected: FAIL because `AGENTS.md` is missing.

- [ ] **Step 3: Create documents and README links**

Write concise project rules, initial decisions and the manual release checklist without private data.

- [ ] **Step 4: Run and verify GREEN**

Run: `python -m unittest tests.test_governance -v`
Expected: all governance tests PASS.

### Task 3: Local state and complete verification

**Files:**
- Local ignored file: `content-ops/state/project-state.yaml`

**Interfaces:**
- Consumes: `project-state.example.yaml`
- Produces: current local stage, verified runtime facts, blockers and next actions

- [ ] **Step 1: Create local state from verified facts only**

Record that code is merged, API key presence is verified without storing the key, scheduler is not installed, old smoke candidate is invalid, platform account status is not confirmed, and real demand input is still missing.

- [ ] **Step 2: Run full verification**

Run: `python -m unittest discover -s tests -v`
Expected: zero failures and zero errors.

- [ ] **Step 3: Check repository hygiene**

Run: `git diff --check` and `git status --short`
Expected: public changes contain no local state or private material.
