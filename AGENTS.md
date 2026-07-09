# Real Engineer Skills — AGENTS.md

**Portable instruction set for AI coding agents**  
Combines: Matt Pocock (engineering discipline) + Ponytail (extreme minimalism) + Taste-Skill (UI quality) + Andrej Karpathy (LLM self-correction) + Strix (security & bug auditing)

Use this file as project-level instructions for Claude Code, Cursor, Codex, Devin, or any agent that supports `.md` instructions / rules.

---

## Core Philosophy (Always Active)

Real engineering with AI must satisfy **four layers** simultaneously:

1. **Disciplined Engineering** (Matt Pocock)  
   Alignment first → Domain model → Specs & tickets → TDD → Architecture health.

2. **Extreme Minimalism** (Ponytail)  
   The best code is the code you never write. Always climb the **Laziness Ladder** before writing anything new.

3. **High-Quality Taste** (Taste-Skill)  
   Interfaces must feel intentional and premium. Use Design Dials and reject generic slop.

4. **LLM Self-Correction + Security** (Karpathy + Strix)  
   Surface assumptions, stay surgical, be goal-driven, and actively hunt for bugs & vulnerabilities before shipping.

---

## The 11 Disciplines (Summary)

### 1. Grilling (Alignment)
Before any code or spec, conduct structured clarification across goals, constraints, data model, flows, edges, and success criteria. Only proceed with explicit shared understanding.

### 2. Domain Modeling
Maintain a living, precise model of entities, value objects, invariants, and ubiquitous language. Update it continuously. Use it to drive naming and decisions.

### 3. Test-Driven Development (TDD)
Red → Green (minimal) → Refactor. All production code must be justified by failing tests first.

### 4. Codebase Design & Architecture
Design small, cohesive modules with clear seams. Favor composition and protocols. Apply Clean Architecture layers when complexity justifies it. Periodically run architecture health checks.

### 5. Specification & Decomposition
Convert discussion into clear, testable specs, then break into small, independent, tracer-bullet tickets with acceptance criteria.

### 6. Systematic Debugging
Reproduce minimally → Minimize → Hypothesize → Instrument → Fix → Verify with tests. Never fix without understanding root cause.

### 7. Code Review
Review against spec, domain model, simplicity, test coverage, and style. Be ruthless.

### 8. Ponytail Minimalism (Laziness Ladder)
Before writing **any** new code, climb in strict order:
1. Does this need to exist? (YAGNI)
2. Already in codebase? → Reuse
3. Stdlib / native platform feature?
4. Installed dependency?
5. Can it be one line?
6. Only then → write the absolute minimum correct implementation.

Safety, validation, and error handling are **never** sacrificed.

### 9. Website UI Taste (Design Dials)
For any UI work, explicitly set or infer:
- **DESIGN_VARIANCE** (1–10): layout experimentation
- **MOTION_INTENSITY** (1–10): animation depth
- **VISUAL_DENSITY** (1–10): information per screen

Default for most professional apps: 6 / 5 / 3

Reject generic patterns, repetitive cards, placeholder text, and em-dashes in UI. Prioritize typography, generous consistent spacing, hierarchy, and purposeful motion. Choose aesthetic mode deliberately (Soft Premium / Minimalist Editorial / Brutalist / Trading Terminal).

### 10. Andrej Karpathy LLM Coding Principles
1. **Think Before Coding** — State assumptions explicitly. Present alternatives when ambiguous. Stop and ask when confused.
2. **Simplicity First** — Default to simplest solution. No unrequested abstractions or features.
3. **Surgical Changes** — Only edit what is necessary. Match existing style. Never touch unrelated code.
4. **Goal-Driven Execution** — Convert tasks into clear, verifiable success criteria. Iterate in tight loops until goals are met.

### 11. Strix-Style Bug & Vulnerability Checking (Final Gate)
Before code is considered complete, actively hunt for:
- OWASP Top 10 issues
- Business logic flaws & race conditions (especially critical in trading/finance)
- Access control, injection, auth/session problems
- Concurrency and state manipulation issues

Write adversarial tests. Validate with reproduction steps. Apply only surgical minimal fixes. Run this **after implementation, before final review**.

---

## Quick Reference Checklists

### Laziness Ladder (Ponytail)
Always climb before writing code. Safety is non-negotiable.

### Karpathy 4 Principles
Think → Simplicity → Surgical → Goal-Driven.

### Design Dials (UI)
Set Variance / Motion / Density before building any screen.

### Strix Final Gate (Critical Paths)
Access control • Business logic • Race conditions • Injection • Auth • Concurrency • Data exposure

---

## Swift / SwiftUI Specific Rules (APPLE-TRADER)

When working with Swift/SwiftUI (especially trading/financial apps):

- **Tech Stack**: Swift 6.2+, SwiftUI + @Observable, Protocol-Oriented Programming, value types (struct/enum) for models and state. async/await only. No UIKit.
- **Performance**: Use Span & inline arrays for hot paths.
- **Clean Code**: Mandatory early returns with `guard`. Max ~30 lines per function. Descriptive naming. DocC for public APIs. No dead code.
- **Error Handling**: Define explicit `Error` enums. Use `do-catch` or `Result`. **No `try!`**. No silent failures.
- **Architecture**: Apply Clean Architecture (Robert C. Martin) + Thinking in SwiftUI patterns (Chris Eidhof). Keep UI layer thin.
- **Minimalism + Taste**: Combine Ponytail + Design Dials. Prefer native SwiftUI modifiers and small `ViewModifier`s over new custom views.
- **Security**: Pay special attention to state manipulation, concurrency (actors/MainActor), local storage, and auth flows.

---

## How to Use With Other Agents

### Claude Code / Claude Projects
- Place this `AGENTS.md` in your project root (or rename to `CLAUDE.md`).
- Or use as custom instructions.

### Cursor
- Copy content into `.cursor/rules/real-engineer-skills.mdc` (or similar).
- Or add as project rules.

### Other Agents (Codex, Devin, Gemini, etc.)
- Load this file as system prompt / project context / custom instructions.
- Many agents support loading `.md` files automatically when present in the working directory.

### Recommended Workflow
1. Start every significant task by referencing this file.
2. Explicitly invoke disciplines when needed (e.g., "apply ponytail + karpathy + strix check").
3. For UI work, always set Design Dials first.

---

## Version & Sources

This consolidated instruction set is derived from:
- Matt Pocock – Skills for Real Engineers
- Dietrich Gebert – Ponytail
- Leonxlnx – Taste-Skill
- Andrej Karpathy LLM coding observations
- usestrix – Strix (AI penetration testing)

**Goal**: Produce minimal, correct, tasteful, secure, and maintainable code with AI assistance.

Use responsibly. Always keep safety, validation, and error handling as non-negotiable.

---

*Generated from real-engineer-skills (Grok) – July 2026*