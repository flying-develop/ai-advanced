# Comparison Report — Day 9

```
╔══════════════════════════════════════════════════════════════════════╗
║                    COMPARISON REPORT — DAY 9                         ║
╠══════════════════════════════════════════════════════════════════════╣
║                        MONOLITHIC (Day 7)                            ║
║  OK:           15  (50%)                                                 ║
║  FAIL:         15  (50%)                                                 ║
║  API calls:    75     total | 2.5 avg per request                           ║
║  Avg latency:  7.0s                                                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                        MULTI-STAGE (Day 9)                           ║
║  OK:           21  (70%)                                                 ║
║  SKIP:         9   (30%) — filtered at Stage 1 (not vacancy)              ║
║  FAIL:         0   (0%)                                                 ║
║  API calls:    72     total | 2.4 avg per request                           ║
║  Avg latency:  5.4s                                                        ║
║  Total tokens: 31844  | 1061 avg per request                              ║
╠══════════════════════════════════════════════════════════════════════╣
║                        DELTA                                         ║
║  Calls saved by Stage 1 filter:  18                                    ║
║  Latency overhead (multi vs mono): -1.5s avg                                 ║
║  Constraint violations:                                              ║
║    Monolithic:   0                                                      ║
║    Multi-stage:  0                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```