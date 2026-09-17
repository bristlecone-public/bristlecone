# State and local government price deflator

`bea_state_local_deflator.csv` — BEA implicit price deflator for **state and local government
consumption expenditures and gross investment**, annual, index 2017 = 100.

- Series: `A829RD3A086NBEA`, from FRED: https://fred.stlouisfed.org/graph/fredgraph.csv?id=A829RD3A086NBEA
- Underlying source: Bureau of Economic Analysis, NIPA.
- Downloaded 2026-09-16.

## Why it is here

CPI-U measures what households buy. A city budget is overwhelmingly labour, so its costs track public
sector wages rather than consumer goods, and the two diverge: over 1971-2021 this index rose 8.24x
against roughly 7x for consumer prices. Deflating municipal spending by CPI-U therefore overstates
how much *more service* the money bought.

Both are published. CPI-U answers "how much household purchasing power did cities take"; this index
answers "how much more policing and fire protection did they actually buy". The second is the better
question for whether spending grew, and it is the more conservative answer.

Raised by the adversarial audit, section 2C; see `docs/ADVERSARIAL_AUDIT_REPORT_RESPONSE.md`.
