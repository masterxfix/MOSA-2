# ESEF / Inline XBRL / IFRS pilot

Starting point: `c0e52bff7270a998a05117f816aba1224e37051c`, 63 fundamental
observations / 32 current rows, market 28 / 5, nine equities. Existing five
covered issuers and all asset masters are protected before/after each write.

## Qualification and boundaries

`scripts/fundamentals/esef.py` is shared by all issuers. Small reviewed profiles
bind ISIN, LEI, names, official publication, download domains, reporting year,
expected currency and source catalog identity. No result constants exist.

Arelle **2.47.3** performs Inline transformations (format, scale, sign), context,
unit and dimension parsing. It runs offline with `skipDTS` and Arelle's WebCache
fallback to the pinned wheel's built-in official XHTML/Inline-XBRL/W3C schemas.
The resolver accepts only the temporary report directory and that built-in cache.
The XHTML/Inline schema validation remains active; schema-load errors are fatal.
The initial adapter incorrectly rejected schema URLs before WebCache could map
them to bundled resources. No schema download, dummy schema, or Arelle source
change was necessary. This is qualification of a narrow standard
IFRS concept allowlist, **not full ESEF/DTS conformance validation**. No taxonomies
are fetched. Issuer extensions, including anchored extensions, remain gaps until
their semantics are reviewed; there is no automatic mapping by similar names.
The initial implementation requires one document containing its own tagged
identity, consolidated nature and report-end anchors; fragmented document sets
without those anchors are not silently merged.

Accepted IFRS monetary duration concepts:

| Concept | Existing/new catalog metric |
|---|---|
| Revenue | revenue |
| ProfitLossFromOperatingActivities | ifrs_operating_profit (new) |
| ProfitLossBeforeTax | profit_before_tax |
| ProfitLoss | profit_after_tax |
| CashFlowsFromUsedInOperatingActivities | operating_cashflow |

The existing `operating_income` definition explicitly says US GAAP. It remains
unchanged; IFRS operating profit gets a distinct controlled definition. Neither
is asserted to be EBIT or EBITDA. Other existing definitions are reused exactly.

LEI and tagged reporting-entity name must agree with the reviewed profile.
`DescriptionOfNatureOfFinancialStatements` must explicitly identify consolidated
statements. Only dimensionless contexts or the standard explicit
ConsolidatedAndSeparateFinancialStatementsAxis/ConsolidatedMember are allowed.
Parent, segment, typed and unknown dimensions are excluded. The nature, identity,
end-date anchors and qualified facts must belong to the same report member.
Only annual duration contexts (364/365/366/371 days) with unique consecutive
periods are eligible; profile FY labels are checked against actual reported end
dates and `DateOfEndOfReportingPeriod2013`. No fabricated periods or FX conversion.
Each report retains its original ISO4217 currency, validated against the profile.

Equal exact duplicates retain all compact locators. Conflicting duplicates or
units leave that metric/year unqualified while other qualified facts continue.
Current selection and contradictory existing values still use the shared writer.

## Source profiles

- NEL: [official publication](https://nelhydrogen.com/press-release/nel-asa-annual-report-2025/),
  [ESEF](https://mb.cision.com/Main/115/4313005/3952680.zip),
  [issuer LEI disclosure](https://mb.cision.com/Public/115/3938728/8e35de89d84f4a27.pdf).
- Pandora: [official publication](https://pandoragroup.com/news/27816),
  [ESEF](https://ml-eu.globenewswire.com/Resource/Download/d40a5896-840e-456c-8d39-161e25b7771e),
  [issuer LEI/ISIN disclosure](https://attachment.news.eu.nasdaq.com/aaa1988622eac713d60d229a620e1096f).
- [Arelle release](https://github.com/Arelle/Arelle/releases/tag/2.47.3),
  [offline/skipDTS API behavior](https://arelle.readthedocs.io/en/latest/command_line.html).

## One-time execution and retention

New manual workflow `fundamentals-esef-once.yml`, Run 1 / Attempt 1 only,
authorization `MOSA2-ESEF-20261101:<exact commit>`, main/repository/commit guards,
existing SSH host-key pinning and DB secrets. One exclusive private reservation
per issuer before its acquisition. At most one package acquisition each, at most
two HTTPS redirects within reviewed publisher domains, every HTTP hop counted.
No HTTP retries. Unknown write outcomes stop the entire pilot, including the
second issuer. A source/qualification failure before writes permits the other
issuer independently. Final readback also verifies failed issuers remained empty.

ZIP limit 64 MiB; 2048 entries, 256 MiB expanded, 64 MiB per entry, ratio 250.
Paths, duplicates, links, encryption, CRC, DTD/entity declarations checked. The
standard OASIS XML Catalog doctype is accepted only at `META-INF/catalog.xml`
and removed from the temporary copy before parsing; all entities and other
DOCTYPE forms remain blocked, so no external DTD is resolved.
Only XHTML/XML/XSD members are written under a temporary directory removed in a
finally path. No complete ZIP/XHTML/PDF is persisted or uploaded as an artifact.
Only compact evidence (<=128 KiB) is privately archived with the existing secure
archive functions, hash-verified before write and after independent DB readback.

Evidence includes full-response SHA-256 separately from stored-evidence SHA-256,
retrieval time/URL/redirect chain, report-member hash, LEI, taxonomy namespace,
tag, context/dimensions, exact Arelle element position and original ID, original
lexical value, transformation/scale/sign/decimals, normalized original-currency
value, qualified status, duplicate references and gaps. The PHP evidence adapter
independently checks profile, identity, scope, period, tag, unit and fact/plan
bindings. It does not reimplement Arelle's transformation engine.

The existing atomic Schema-6 writer, separate DB connection readback and fresh
`mosa2-ai-analysis-input-v1` / assessment input validator are reused. No OpenAI
call. Existing PRIMARY/history-index queries report SQL iterator and client+tunnel
timing separately. No new network-latency probes or index changes.

## Focused verification

Synthetic real-Arelle packages cover two issuers/currencies, 2024/2025 and
non-calendar years, parent/segment/instant/quarter exclusion, scale/sign,
taxonomy versions, extension gaps, duplicate conflicts, ZIP safety/cleanup,
evidence hash/binding, shared writer/current/replay/rollback and one-shot guards.
Offline acceptance on 2026-11-01: one targeted diagnostic run, one focused
correction test PASS, followed by one complete run of the existing ESEF suite:
**10/10 PASS** (3.748 s). No additional SEC/PNE/Zeiss suite was run in this
bounded acceptance order. Shared writer/current/replay and analysis validation
are exercised by the ESEF suite itself.

The diagnostic established `ix11.10.1.1:transformValueError` for synthetic
`ifrs:Revenue`, context Y2025, lexical value `nonsense`, transformation
`ixt:num-dot-decimal`. Arelle logs this during validation and retains it in
`model.errors`, even though the adapter already discards the invalid value.
The adapter now checks every occurrence of this exact code against a single
Arelle object reference, an actual nonFraction fact and INVALID validation
status. Those facts are excluded and classified as INVALID_NUMERIC_TRANSFORM.
Unbound occurrences, other/unknown codes and schema/document errors still stop.
The focused test also proves a missing required contextRef remains blocking.

No downloads, live DB access, model calls or Actions runs took place. The manual
workflow is preparation only; live NEL/Pandora acceptance remains a separate
follow-up order. No UI change or Chrome check.

Next shared source family after this pilot: HKEX issuer filings for BYD and
Ubtech, with source identity, annual-period/currency and consolidated-scope
qualification. Not implemented by this order.
