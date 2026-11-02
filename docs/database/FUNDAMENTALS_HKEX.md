# HKEX ASBE/CASBE fundamentals qualification

Offline qualification only. No database connection, provider import, GitHub Actions run, deployment, or PDF archive was performed. The two official PDFs were retrieved once each into a temporary directory; the retained artifact is compact derived Evidence JSON only.

## Source and scope

Both reports are consolidated ASBE/CASBE statements for calendar FY2025/FY2024. The source unit is `RMB’000`, retained as `CNY_THOUSAND` with `scale_numerator=1000` and `scale_denominator=1`; no HKD conversion was made.

| issuer | ISIN | official PDF | response SHA-256 | Evidence SHA-256 |
| --- | --- | --- | --- | --- |
| BYD Company Limited | CNE100000296 | [HKEX FY2025 report](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0327/2026032703008.pdf) | `7906b6647eb7cf3ab5986e9b8eda8f707969c64dc54c67b83b606744ef9f4846` | `c651651b94d48f015b1652fded3575302d2122b6da274f2d39dcb5118d64a052` |
| UBTECH ROBOTICS CORP LTD | CNE100006CQ4 | [HKEX FY2025 report](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0414/2026041401168.pdf) | `f5736f8d7b3794d92f69d2ad04cba8fe1607734c507e853b6109581b4224024d` | `5a249199e96f40840c68279047c68eb10dece4714a039aafc72b36880b71f7` |

The corresponding official [BYD title search](https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&market=SEHK&stockId=2696) and [UBTECH title search](https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&lang=EN&market=SEHK&stockId=1000208870) identify stock codes `01211` and `09880`. Publication dates are 2026-03-27 and 2026-04-14.

## Qualified observations

All values below are consolidated, in `RMB’000`, with exact PDF page/column locators. `Operating Profit / Loss` is a distinct explicit-row metric; it is not mapped to EBIT.

| issuer | metric | FY2025 | FY2024 | PDF pages |
| --- | --- | ---: | ---: | --- |
| BYD | revenue | 803,964,958 | 777,102,455 | 144 / FY2025,FY2024 |
| BYD | operating_profit | 40,184,709 | 50,486,047 | 144 / FY2025,FY2024 |
| BYD | profit_before_tax | 39,753,049 | 49,680,677 | 144 / FY2025,FY2024 |
| BYD | profit_after_tax | 33,760,758 | 41,587,940 | 144 / FY2025,FY2024 |
| BYD | operating_cashflow | 59,135,544 | 133,453,873 | 148 / FY2025,FY2024 |
| UBTECH | revenue | 2,000,999 | 1,305,361 | 185 / FY2025,FY2024 |
| UBTECH | operating_profit | (779,210) | (1,143,112) | 185 / FY2025,FY2024 |
| UBTECH | profit_before_tax | (774,680) | (1,149,259) | 185 / FY2025,FY2024 |
| UBTECH | profit_after_tax | (789,823) | (1,159,924) | 185 / FY2025,FY2024 |
| UBTECH | operating_cashflow | (784,111) | (883,636) | 187 / FY2025,FY2024 |

Gaps: none. Each plan contains 10 observations, 5 metric groups, and an independently validated identity, standard, consolidation, period, unit, sign, row, column, page, and coordinate locator.

## Verification boundary

Focused adapter tests, negative identity/unit/year/scope tests, PHP lints, PHP writer/current/readback/replay, Evidence-tamper rejection, and analysis-input validation passed. The real offline pipeline passed for both plans. Counts were 20 observations and 10 current projections in the in-memory writer proof only; the MOSA-2 test database was not accessed or changed.

Provider retrievals: 2 official PDF GETs total (one per company); no retry. Pipeline provider requests: 0. Actions: 0. Database writes: 0.
