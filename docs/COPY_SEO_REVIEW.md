# Copy, SEO and AI-search review — 2026-11-26

Scope: five public product pages, English and Spanish, desktop/mobile, public demo entry.
Goal: help newsroom editors understand the product and try the demo. Primary CTA: explore
the interactive demo. The product is a pilot/MVP, not a self-service paid offering.
Skills applied: existing `copywriting` and `seo-audit`; no additional installation needed.

## Findings and fixes

| ID | Issue and evidence before changes | Category | Severity / confidence | Deduction | Resolution |
|---|---|---|---|---|---|
| A | No application sitemap route; edge-generated robots had no sitemap reference | Crawlability & Indexation | High / High | −10 | Ten canonical language URLs in XML; sitemap advertised in origin robots |
| B | English and Spanish shared a canonical without language; no hreflang links | Crawlability & Indexation | High / High | −10 | Self-canonical `?lang=en/es`, reciprocal alternates and English x-default |
| C | Demo and authenticated pages lacked an explicit indexing exclusion | Crawlability & Indexation | Medium / High | −5 | Response `noindex, follow` outside public pages; API crawling disallowed; authentication retained |
| D | Home title “One agenda. More perspective.” and H1 “Your sources…” did not identify the product category | On-Page Optimization | High / High | −10 | Media monitoring for newsrooms; coverage comparison and editorial planning titles |
| E | Closing CTA favored login and still displayed “demo / demo” | Content Quality & E-E-A-T | High / High | −10 | Direct demo CTA; no-signup and fictional-content explanation |
| F | Public pages lacked a concise definition of coverage gaps and a compact factual product summary | Content Quality & E-E-A-T | Medium / High | −5 | Server-rendered definition, demo scope, real-news prerequisites and optional AI status |
| G | No verifiable customer outcomes, independent references or pilot evaluation results available in reviewed material | Authority & Trust Signals | High / Medium | −5 | Remains open; no invented testimonials, ROI claims, ratings or clients |
| H | Mobile screenshot showed the example card overlapping the next section because a percentage grid gap persisted in the single-column layout | Technical Foundations | Medium / High | −5 | Fixed mobile gap in pixels; browser checks now assert sections do not overlap |

SEO readiness index for this scoped inspection: **87 → 100 / 100 (Excellent)** for resolved
technical/content checks, **not** an exhaustive site or ranking score. The residual authority
deduction means the exact weighted result is 99.5, rounded to 100; this rounding does not
mean the site has established authority. No unresolved critical blocker was observed.

| Category | Before | After | Weight | Before contribution | After contribution |
|---|---:|---:|---:|---:|---:|
| Crawlability & Indexation | 75 | 100 | 30% | 22.5 | 30 |
| Technical Foundations | 95 | 100 | 25% | 23.75 | 25 |
| On-Page Optimization | 90 | 100 | 20% | 18 | 20 |
| Content Quality & E-E-A-T | 85 | 100 | 15% | 12.75 | 15 |
| Authority & Trust Signals | 95 | 95 | 10% | 9.5 | 9.5 |

Technical checks cover HTTPS, server-rendered content, response semantics and responsive
layout. They do not include field Core Web Vitals or a new performance benchmark. Search
Console, analytics, backlink data and actual AI citation data were unavailable. Score reflects
the listed checks only, not guaranteed rankings. Competition and algorithm effects are excluded;
authority assessment is directional. Do not use this score as marketing proof.

## Copy decisions

Chosen headline: “Spot gaps in your news coverage. Prepare your next editorial meeting.”
It names the task and connects comparison to a familiar newsroom workflow. The lead identifies
Agenda Radar as a media monitoring tool for newsrooms. Spanish copy is written for editors,
not a word-for-word keyword translation. Demo numbers remain explicitly fictional.

Alternatives reserved for later user testing (not proven winners):
- “Bring coverage evidence to your next editorial meeting.” — narrower meeting use case.
- “See what your newsroom could investigate next.” — stronger discovery focus, less category clarity.

Chosen CTA: “Explore the interactive demo.” Alternatives: “Try coverage comparison” or
“Explore a sample newsroom.” No signup, payment, time-saving or AI-performance promise.

## AI-search decisions

- Product identity, audience, workflow and limitations are visible in initial HTML without JS.
- `SoftwareApplication` microdata describes the visible product. No invented rating, price,
  organization credentials or unsupported rich-result eligibility claims.
- English and Spanish have explicit crawlable links, stable language URLs and matching canonicals.
- Fictional demo content is noindex; it must not become evidence of real news or customer results.
- No hidden AI instructions, keyword stuffing or `llms.txt` ranking claim.
- Origin robots allows public crawling, including OAI-SearchBot via the wildcard group.
  Cloudflare injects separate managed policies blocking several training crawlers, including
  GPTBot and Google-Extended. These existing policies were preserved. Accessibility to a
  browser or spoofed user-agent does not prove access by a verified crawler or inclusion in answers.

Primary references checked 2026-11-26:
- https://developers.google.com/search/docs/appearance/ai-features — existing SEO fundamentals apply; no special AI markup required.
- https://developers.google.com/search/docs/specialty/international/localized-versions — language alternates and reciprocal links.
- https://developers.openai.com/api/docs/bots — search crawling and training crawling are distinct.

## Priorities and validation

Critical blockers: none observed. High-impact work A/B/D/E completed. Quick wins C/F completed.
Remaining work G: collect real, consented pilot evidence and publish results with methodology;
validate index coverage in Search Console and crawler access in edge logs when available.
Those steps can improve confidence and trust; no ranking gain or delivery date is promised.

Local checks: seven focused SEO/public/demo tests passed; 19 public/account pages in both
languages and desktop/mobile passed browser checks. Production validation recorded in STATUS.md.
