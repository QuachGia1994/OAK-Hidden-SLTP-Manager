# Quickstart — Real Engineer Skills

Hướng dẫn cài đặt nhanh để dùng bộ skill này với các AI agents khác (Claude, Cursor, v.v.)

---

## 1. Cách nhanh nhất (Khuyến nghị)

1. Copy file `AGENTS.md` vào thư mục gốc của project bạn đang làm.
2. Đổi tên file thành tên mà agent của bạn hỗ trợ tốt nhất:

   - **Claude Code / Claude Projects**: Đổi thành `CLAUDE.md`
   - **Cursor**: Đổi thành `.cursor/rules/real-engineer-skills.mdc` (tạo thư mục nếu chưa có)
   - **Các agent khác**: Giữ nguyên `AGENTS.md` hoặc theo hướng dẫn của agent

3. Mở agent và bắt đầu dùng. Agent sẽ tự động đọc file này.

---

## 2. Hướng dẫn chi tiết theo từng agent

### Claude Code (Claude Projects)

```bash
# Trong thư mục project
cp AGENTS.md CLAUDE.md
```

Sau đó:
- Mở Claude Code
- Agent sẽ tự động load `CLAUDE.md` trong project
- Hoặc paste nội dung vào **Custom Instructions** của project

### Cursor

```bash
mkdir -p .cursor/rules
cp AGENTS.md .cursor/rules/real-engineer-skills.mdc
```

Sau đó restart Cursor hoặc reload project.  
Cursor sẽ tự động áp dụng rule này.

### Các agent khác (Codex, Devin, Gemini, v.v.)

- Đặt file `AGENTS.md` vào root của project/working directory.
- Nhiều agent hỗ trợ tự động load file `.md` có tên `AGENTS.md`, `CLAUDE.md`, hoặc `INSTRUCTIONS.md`.
- Nếu không tự động, bạn có thể:
  - Copy nội dung file vào phần **Project Instructions** / **Custom System Prompt**
  - Hoặc paste thủ công khi bắt đầu conversation mới

---

## 3. Sử dụng như thế nào?

Sau khi cài đặt, bạn chỉ cần nói tự nhiên:

- "Follow real engineer skills"
- "Apply ponytail + karpathy + strix check"
- "Grill me first, then use TDD and design dials"
- "Do a full strix vulnerability audit before finishing"

Agent sẽ tự động tuân theo các discipline phù hợp.

---

## 4. Nếu muốn dùng phiên bản chi tiết hơn

Nếu bạn muốn agent có thể đọc chi tiết từng reference (thay vì bản tóm tắt), bạn có thể:

1. Copy toàn bộ thư mục skill:
   ```
   /home/workdir/.grok/skills/real-engineer-skills/
   ```
2. Đặt vào project của bạn (ví dụ: `.agent-skills/real-engineer-skills/`)
3. Hướng dẫn agent: "Load skill from .agent-skills/real-engineer-skills/SKILL.md khi cần"

Tuy nhiên, với hầu hết các agent, file **`AGENTS.md`** (bản consolidated) đã đủ mạnh và dễ dùng hơn.

---

## 5. Khuyến nghị workflow

1. Bắt đầu task mới → Agent tự động đọc `AGENTS.md`
2. Với task phức tạp, bạn có thể nói rõ:  
   `"Use full real engineer skills flow: grill → domain model → ponytail + karpathy → strix check"`
3. Agent sẽ tuân thủ quy trình 11 disciplines một cách có kỷ luật.

---

## File liên quan

- `AGENTS.md` — File chính, dùng cho hầu hết các agent
- `QUICKSTART.md` — File này (hướng dẫn cài đặt nhanh)

---

**Bắt đầu ngay**: Chỉ cần copy `AGENTS.md` vào project và đổi tên phù hợp là xong!

Nếu cần hỗ trợ thêm (ví dụ: tạo version cho một agent cụ thể), cứ bảo mình nhé.
