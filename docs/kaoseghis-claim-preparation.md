# Claim Preparation Preview

## Current Scope

`Macros > Scheduler > Claim preparation preview` opens a modeless, read-only
preview. It does not create a macro or a scheduled job. No eGHIS database access,
focus change, scrolling, keypress, selection, aggregation, submission, password
entry, or shutdown action is performed by this reader.

1. Open `[청구] 청구내역집계` in the connected EMR and select `주단위`.
2. In the preview, choose the intended claim date. This is not a scheduler trigger.
3. Select the required month in EMR; wait until its list has finished loading.
4. Press `Read selected EMR month`.
5. For a workweek spanning two months, select and read the other month as well.

The preview displays both periods, observed latest weeks, proposed next weeks,
and capture times. A zero-row history requires operator confirmation before it
becomes a first-week proposal. There is deliberately no Run/Aggregate button.

## Period and Week Rules

- The period is the current Monday through the selected weekday claim date.
  Weekend dates are rejected; holidays and claim-day calendar detection are not
  implemented.
- Split this date interval at the month boundary, including year boundaries.
- For **each month separately**, use the maximum week in that month's observed
  history plus one. Insurance rows may repeat a week; row order is not assumed.
- An explicitly read and confirmed empty month proposes week 1. A missing,
  unreadable, partial, ambiguous, changing, or timed-out list is never empty.
- Do not derive a month’s last week number from a calendar. It can be 5 or 6;
  the proposal still comes from the preceding recorded week plus one.
- The proposed week must have a visible, enabled week radio in that month.
  If not, the preview is blocked rather than clamped, skipped, or guessed.
- The selected EMR month comes from `mpDemandYm`, not today's date. The full
  date reported by UIA is reduced to year/month only.

### Confirmed Example: Friday 2026-10-02

| Month | Included dates | Observed latest | Proposal |
| --- | --- | --- | --- |
| 2026/09 | 2026-09-28 through 2026-09-30 | 4주 | 5주 |
| 2026/10 | 2026-10-01 through 2026-10-02 | Empty, confirmed | 1주 |

Two separate aggregations will eventually be needed. The preview does not run
either. If September's actual latest week is instead 5, it proposes 6 rather
than assuming 5 from this example. Missing October history stays `Month not read`.

## UIA Targets

These captures belong to the claim window, **not** the `H2OpdTreatment` anchor.
Native handles and screen coordinates are intentionally not persisted.

| Purpose | Selector | Scope |
| --- | --- | --- |
| Claim window | Name `[청구] 청구내역집계`, Window | Connected EMR process |
| Query panel | Name `조회구분`, Pane | Claim window |
| Claim month | Automation ID `mpDemandYm`, ComboBox | Query panel |
| Weekly mode | **Name** `rdoWeek`, RadioButton | Query panel |
| Week choice | Name `1주` through `6주`, RadioButton | Query panel |
| Idle check only | Automation ID `btnBuild`, Button | Query panel |
| Claim list | Name `청구리스트`, Pane | Claim window |
| Claim table | Name `MainView`, Table | Claim list |
| Rows | `Data Panel` (Custom) > `Row N` (ListItem) | Claim table |
| Row month | Name `진료년월 row N`, DataItem | Row N |
| Row week | Name `청구단위 row N`, DataItem | Row N |

`rdoWeek` is not an Automation ID. `btnBuild` has the same idle caption
`청구 집계 (F7) [집계 대기]` before and after an aggregation, so that caption
cannot prove success. This version reads the caption only to reject busy states.
It never clicks the button or sends F7, which has unrelated order-send behavior
in the treatment room.

## Read Safety and Limitations

- Reads are explicit, off the Qt UI thread, scoped to the connected process and
  claim window, with native UIA conditions. The worker initializes COM as MTA;
  the GUI thread's STA mode is unchanged. No broad desktop UIA enumeration and
  no treatment-grid cache mutation are used.
- Claim-window lookup checks both native top-level and child HWNDs in the connected
  EMR process. An MDI claim page is wrapped directly by HWND instead of searching
  the entire EMR UIA descendant tree. Multiple visible matches still block the read.
- If no native claim window exists, the UIA fallback searches layout containers
  only. Query/history pane, table, and data-panel discovery use immediate-child
  queries, with a 128-container/16-level bound, and never expand Tables/DataGrids
  to find sibling layout targets. Patient rows and patient cell values are not
  searched. Only after the exact claim-history table is found are its direct rows
  enumerated; month/week cells are looked up as direct children of each claim row.
- The table's GridPattern row count must equal the exposed Data Panel rows.
  Maximum 128 rows. A missing GridPattern or a virtualized/incomplete list is
  rejected, not silently accepted. This provider behavior still needs checking
  against the installed EMR while the claim screen is open.
- Only month/week values are read, never the lower patient table, claim numbers,
  amounts, patient names, or patient identifiers. Native exception payloads are
  not logged or displayed.
- Two matching snapshots are required. Month mismatch, missing values, invalid
  row identities, or a changed EMR connection discard the read.
- The read budget is 8 seconds between native calls; after 10 seconds the UI
  discards the request. An in-flight COM call cannot be forcibly interrupted:
  no second worker starts until it returns, and its late result is ignored.
  Reader timeouts identify the stage (window, query panel, weekly mode, history
  grid, or month/week rows) using fixed messages without native/provider contents.
- Previews live only in memory, expire after five minutes, and are cleared on
  claim-date change, connection change, or closing the dialog. They are planning
  snapshots, not authorization to run aggregation later without re-reading.
- Select each month manually. The preview does not change EMR filters and does
  not infer that an empty-looking screen has finished loading without operator
  confirmation. No automatic claim-day/Radicale integration is included.

### First Live Preview Timeout

On 2026-09-23 the operator's read-only preview timed out before inferring a week.
The previous implementation searched only native top-level windows, so an MDI
claim page forced a full EMR UIA descendant search; it also used descendant searches
to locate panes near large patient grids. These are plausible timeout contributors,
not a measured attribution of the original timeout to one exact call.

A read-only native-window check found one enabled claim child window and no
top-level claim window, in approximately 3 ms. It did not read patient fields,
change focus/selections, or run aggregation. The narrowed lookup now uses that
child-window path. Full live month/week reading still needs another preview run;
the deadline, row-count checks, and two-snapshot requirement have not been relaxed.

## Next Execution Stage (Not Implemented)

After real-screen read verification, an execution stage must require operator
review of both month/week targets, select and verify the intended query month
and week, and invoke `btnBuild` once in the claim-window scope. A newly present
row for that month/week is needed to verify aggregation creation. Idle status
alone is insufficient. If the second month's operation fails, the successful
first one must not be run again. Claim submission and final approval remain
manual and out of scope.
