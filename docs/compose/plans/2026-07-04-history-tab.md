# History Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make missed or prior-day signals discoverable from the website by exposing the existing history page in navigation.

**Architecture:** Reuse the existing `/signals` page instead of creating new data flow or UI. Limit the change to navigation copy so weekend users can reach the already-built 7-day grouped history view.

**Tech Stack:** Next.js App Router, React, Tailwind CSS

## Global Constraints

- Keep the diff minimal: no Redis, bot, or data-model changes.
- Reuse the existing `dashboard/src/app/signals/page.tsx` implementation as-is.
- Label the navigation item in Vietnamese as `Lịch sử`.

---

### Task 1: Expose Existing History Page In Navigation

**Files:**
- Modify: `dashboard/src/components/NavBar.tsx`
- Verify: `dashboard/src/components/NavBar.tsx`

**Interfaces:**
- Consumes: existing `links` array rendered by `NavBar()`
- Produces: a visible navbar link to `/signals` with Vietnamese copy

- [ ] **Step 1: Confirm the target page already exists**

Read and verify this file already provides the history screen:

```tsx
// dashboard/src/app/signals/page.tsx
export default async function SignalsPage(...) {
  // groups signals by date and renders up to 7 days
}
```

- [ ] **Step 2: Edit the navigation links array**

Update `dashboard/src/components/NavBar.tsx` to include the existing route:

```tsx
const links = [
  { href: "/", label: "Dashboard", mobile: "Dashboard" },
  { href: "/signals", label: "Lịch sử", mobile: "Lịch sử" },
  { href: "/factcheck", label: "Xác thực tin tức", mobile: "Xác thực" },
  { href: "/rules", label: "Rules", mobile: "Rules" },
];
```

- [ ] **Step 3: Verify the route is now reachable from nav**

Run a targeted diff check:

Run: `git diff -- dashboard/src/components/NavBar.tsx`
Expected: one added `/signals` nav entry labeled `Lịch sử`

- [ ] **Step 4: Verify no unrelated files changed**

Run: `git status --short`
Expected: only `dashboard/src/components/NavBar.tsx` modified for this task

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/NavBar.tsx
git commit -m "feat: add history tab to dashboard nav"
```
