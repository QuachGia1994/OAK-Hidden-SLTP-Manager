# UNIFIED AGENT PROTOCOL — AGENTS.md / .agent/rules.md

Portable instruction set for AI coding agents (Antigravity IDE, Gemini 3.1 Pro, Claude Code, Cursor, Codex, Devin).

---

## 1. Core Philosophy & Engineering Disciplines

Real engineering with AI satisfies four core layers simultaneously:
1. **Disciplined Engineering**: Alignment first → Domain model → Specs & tickets → TDD → Architecture health.
2. **Extreme Minimalism (Ponytail)**: The best code is the code you never write. Always climb the Laziness Ladder.
3. **High-Quality Taste & Design Standards (Google Labs design.md)**: Interfaces must feel intentional, structured, and premium. Reject generic templates and AI slop.
4. **LLM Self-Correction & Security**: Surface assumptions, stay surgical, be goal-driven, and actively hunt for bugs/vulnerabilities before shipping.

### The 11 Core Disciplines
1. **Grilling (Alignment)**: Conduct structured clarification across goals, constraints, data model, and edge cases before writing code.
2. **Domain Modeling**: Maintain a precise, living model of entities, value objects, and ubiquitous language.
3. **Test-Driven Development (TDD)**: Red → Green (minimal) → Refactor.
4. **Codebase Design & Architecture**: Small, cohesive modules with clear seams. Favor composition and protocols.
5. **Specification & Decomposition**: Break tasks into small, independent, tracer-bullet tickets with clear acceptance criteria.
6. **Systematic Debugging**: Reproduce minimally → Hypothesize → Instrument → Fix → Verify with tests. Never fix without understanding the root cause.
7. **Code Review**: Review against spec, domain model, simplicity, test coverage, and style.
8. **Ponytail Minimalism (Laziness Ladder)**:
   - Does this need to exist? (YAGNI)
   - Already in codebase? → Reuse
   - Stdlib / native platform feature?
   - Installed dependency?
   - Can it be one line?
   - Only then → write the absolute minimum correct implementation.
9. **Karpathy 4 Principles**: Think Before Coding → Simplicity First → Surgical Changes → Goal-Driven Execution.
10. **Strix Bug & Security Gate**: Before finishing, audit for OWASP Top 10, access control, business logic flaws, race conditions, concurrency issues, and auth flaws.
11. **Cascading Impact Scan**: Always find and update every file affected by your changes.

---

## 2. Antigravity IDE & Gemini 3.1 Pro Execution Rules

### Rule 2.1: Mandatory Impact Scan & Related File Updates
Khi sửa lỗi, refactor hoặc thêm tính năng:
1. **Grep/Search Dependents**: BẮT BUỘC dùng codebase search/grep để tìm TẤT CẢ các file đang import hoặc sử dụng function, component, API handler, type hoặc prop vừa thay đổi.
2. **Cascade Fixes**: Tự động sửa tất cả các file liên quan ngay trong cùng lượt xử lý. Không dừng lại cho đến khi toàn bộ hệ thống đồng bộ.
3. **Build & Type Verification**:
   - Chạy `npx tsc --noEmit` hoặc `npm run build` (với Web/Vercel projects).
   - Chạy `swift build` hoặc `xcodebuild` (với Swift projects).
   - Nếu có lỗi, tiếp tục tự động sửa cho đến khi build pass 100%.

### Rule 2.2: Automatic Git & Vercel Deployment
Ngay khi code đã sửa xong, các file liên quan đã cập nhật và build verification PASS:
1. **Git Staging**: Execute `git add .`
2. **Git Commit**: Tạo commit message ngắn gọn theo chuẩn Conventional Commits (ví dụ: `fix(auth): update token handler and update dependent components`).
3. **Push / Vercel Deploy**: Execute `git push origin HEAD` để tự động kích hoạt Vercel build/deploy pipeline.
4. **Final Summary**: Báo cáo ngắn gọn cho người dùng: "Đã sửa X, cập nhật Y file liên quan, build pass và đã push Vercel thành công."

---

## 3. Web UI & Google Labs Design System Standards (`design.md`)

Khi phát triển hoặc chỉnh sửa giao diện Web (React, Next.js, HTML/CSS, Tailwind):

### 3.1. Design Principles & Aesthetic
- **Intentional Layout**: Sử dụng Grid & Flexbox chuẩn chỉnh, có không gian thở (padding/margin hợp lý).
- **Design Dials Default**:
  - `DESIGN_VARIANCE`: 6 (Sáng tạo vừa đủ, tránh phá vỡ khung trải nghiệm)
  - `MOTION_INTENSITY`: 5 (Animation mượt mà, chuyển cảnh có mục đích)
  - `VISUAL_DENSITY`: 3-5 (Thông tin thoáng đãng, dễ đọc)
- **Color System**:
  - Khai báo CSS Variables cho theme (`--background`, `--foreground`, `--primary`, `--muted`, `--accent`).
  - Đảm bảo độ tương phản (WCAG AA/AAA) cho Dark/Light mode.
  - Dùng màu nhấn (accent) có tiết chế, tránh lạm dụng gradient màu mè.
- **Typography & Hierarchy**:
  - Phân cấp rõ ràng: Title (Bold/Large) → Section Header → Body → Muted Metadata.
  - Sử dụng font Sans-serif hiện đại cho UI và Monospace cho code/data numeric.

### 3.2. Anti-Patterns (TẬP TRUNG TRÁNH AI SLOP)
- **KHÔNG** dùng layout thẻ (cards) lặp đi lặp lại một cách nhàm chán.
- **KHÔNG** sử dụng text giả (Lorem Ipsum) hay thông số placeholder vô nghĩa.
- **KHÔNG** dùng viền quá đậm, bóng đổ (drop shadow) lem nhem hoặc màu sắc không có nghĩa trong bảng thiết kế.
- **KHÔNG** bỏ qua trạng thái UI (mọi nút/input phải có đầy đủ state: `hover`, `focus-visible`, `active`, `disabled`, `loading`, `empty`).

---

## 4. Swift / SwiftUI Specific Rules (APPLE-TRADER)

Dành cho các dự án Swift / macOS / iOS:

- **Tech Stack**: Swift 6.2+, SwiftUI + `@Observable`, Protocol-Oriented Programming, Value types (`struct`/`enum`). `async/await` chỉ định. Không xài UIKit trừ khi cực kỳ cần thiết.
- **Performance**: Dùng `Span` & inline arrays cho hot paths/real-time trading data.
- **Clean Code**: Bắt buộc dùng `guard` early return. Hàm tối đa ~30 dòng. Rõ nghĩa. Không dùng `try!`. Không giấu lỗi.
- **Architecture**: Clean Architecture + Thinking in SwiftUI. Tách biệt UI layer và Business Logic (Domain).
- **Security**: Kiểm tra kỹ concurrency (`@MainActor`, `actor`), quản lý state giao dịch và mã hóa dữ liệu nhạy cảm.

---

## 5. Antigravity Quick Commands & Workflows

Khi làm việc trong Antigravity Chat:
- Để kích hoạt suy luận đa bước trước khi sửa code lớn:  
  `[Think Deep] <Yêu cầu công việc>`
- Để chạy workflow sửa code + push Vercel tự động:  
  `Sửa lỗi X, quét toàn bộ side-effects, typecheck và push Vercel khi hoàn tất.`