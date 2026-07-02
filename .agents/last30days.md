# Last30Days Agent — Research Methodology

Based on [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill). Adapted for trading bot context.

## Core Concept

Search what real people discuss about a topic across multiple sources, score by engagement (upvotes, likes, views), and synthesize into a grounded summary. Not SEO rankings — real human attention.

## Sources (Priority Order)

| Source | Signal Type | Free? |
|--------|-------------|-------|
| Reddit | Community opinion, upvote-ranked | Yes (public JSON) |
| X/Twitter | Hot takes, breaking reactions | Browser cookies or API key |
| YouTube | Deep dives, transcripts | yt-dlp (free) |
| Hacker News | Developer consensus | Yes (public API) |
| Polymarket | Real-money odds | Yes |
| GitHub | PR velocity, releases | Yes (if `gh` installed) |
| Web | Editorial coverage | Brave Search key (2K free/mo) |

## Research Flow

1. **Resolve entity**: Find X handles, GitHub repos, subreddits, YouTube channels for the topic
2. **Search in parallel**: All sources at once, not serial
3. **Score by engagement**: Upvotes, views, likes — what people actually care about
4. **Cluster same stories**: Same story on Reddit + X = one cluster, not three
5. **Synthesize**: Bold-lead-in paragraphs, cite by source, rank by engagement

## Output Format

```
What I learned:

**Bold lead-in** with key finding. Supporting detail from source.

**Another pattern** with community evidence. Quote from top comment.

KEY PATTERNS from the research:
1. Pattern one - source
2. Pattern two - source
3. Pattern three - source
```

## For Trading Context

Adapt this methodology for market research:
- **Reddit**: r/Forex, r/wallstreetbets, r/algotrading for sentiment
- **X/Twitter**: Financial analysts, traders, news accounts
- **YouTube**: Market analysis channels, earnings calls
- **Hacker News**: Quant/algorithmic trading discussions
- **Polymarket**: Prediction market odds on economic events
- **GitHub**: Trading bot repos, strategy implementations

## Rules

- No invented titles — let the data speak
- No `Sources:` block at the end — cite inline
- No em-dashes — use ` - ` instead
- Weave community voice — quote actual comments
- Never narrate the tooling — present findings only

---
*Based on last30days-skill v3.8.3 by mvanhorn*
