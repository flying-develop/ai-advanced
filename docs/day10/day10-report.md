# Micro-Model Report — Day 10

```
╔══════════════════════════════════════════════════════════════════════╗
║                    MICRO-MODEL REPORT — DAY 10                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  MICRO-MODEL ACCURACY (30 requests)                                  ║
║                        qwen2.5:0.5b    qwen2.5:3b                   ║
║  Correct (vacancy/not): 20/30 (67%)     23/30 (77%)                   ║
║  UNSURE cases:          21   (70%)     8    (27%)                  ║
║  Avg latency:           4485ms           28706ms                          ║
║  UNSURE→cloud fixed:    8              4                           ║
╠══════════════════════════════════════════════════════════════════════╣
║  PIPELINE COMPARISON (30 requests)                                   ║
║                     Day 9    0.5b-first  3b-first                   ║
║  OK:                 21(70%)   21(70%)      18(60%)                ║
║  SKIP/REJECT:         9(30%)    0(30%)       9(40%)                ║
║  Cloud calls total: 72       65         44                   ║
║  Avg cloud calls:   2.4      2.2         1.5                   ║
║  Avg total latency: 4.1s     8.5s        33.3s                  ║
╠══════════════════════════════════════════════════════════════════════╣
║  SAVINGS vs Day 9 (best micro model: 3b)                        ║
║  Cloud calls saved: 28  (39% reduction)                       ║
║  Micro latency add: +30268ms avg                                  ║
║  Net latency delta: +29.3s avg                                     ║
╚══════════════════════════════════════════════════════════════════════╝
```