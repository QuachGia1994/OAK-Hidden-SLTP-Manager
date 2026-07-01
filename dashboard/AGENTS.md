<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

<!-- BEGIN:taste-skill-rules -->
# Taste Skill Design Rules

## Anti-Slop Guidelines
- Never produce generic boilerplate UI
- Typography hierarchy: text-4xl headers, text-[10px] labels
- Spacing: 4px grid system (gap-2, gap-3, gap-4, gap-6)
- Cards: rounded-xl, shadow-sm, hover:shadow-md transitions
- Badges: rounded-md, px-2.5 py-1, font-semibold uppercase

## Color System
- Neutrals: zinc-50 to zinc-900
- Buy/Positive: emerald-400/500
- Sell/Negative: red-400/500
- Warning: amber-400/500

## Component Patterns
- StatusCard: border, rounded-xl, shadow-sm
- PairBadge: flex between, mono font, tabular-nums
- SignalCard: group hover effect, clear hierarchy
<!-- END:taste-skill-rules -->
