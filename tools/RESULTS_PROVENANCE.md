# Website results provenance

Snapshot: 2026-11-02. Tables II and IV of the current AnchorHEC manuscript.

## Files

- `docs/assets/data/results.json`: 150 method/condition records plus definitions and notes.
- `docs/assets/data/results.csv`: the same 150 records; empty error fields mean no output, never zero.

## Sources

- `HEVFM/paper/04_experiments.tex` — SHA256 `326bdf8b5583b32b73e25c55395cf07b39a164cbedfcd367cb87f687ca7ac4d5`.
- `HEVFM/results/paper_v2_manuscript/numbers_v1.json` — SHA256 `c8291e3452a80c395c6acd7c3e966227b0da02a14606ba1785aa12222ce756a5`.
- `HEVFM/results/paper_v2_manuscript/numbers_fixedreg_v3.json` — SHA256 `d5d045385560e3d39854fd05c80ec3e5e191beffa9925c658ff4c8fa4ac668bc`.

Paths above describe the private research workspace used to prepare this release; they are not website dependencies.

## Extraction and verification

Displayed numeric entries were parsed from the TeX table rows, expanding Fail multicolumn entries into two null error fields. Every record was independently matched, after two-decimal rounding, to the canonical JSON cells. Simulation wrist JCR/AnchorHEC use `numbers_v1.tables.main`; simulation fixed results use `numbers_fixedreg_v3.tables.main_fixed`; Zhi results and output counts use `.tables.main_zhi`; physical results use `.tables.physical_all`.

- Verified 150/150 records against canonical JSON; 120 simulation records and 30 physical records.
- Output status counts: {'complete': 137, 'partial': 8, 'failed': 5}.
- All five failed records have null errors; all eight partial-output records retain means over returned estimates and output counts.
- Zhi simulation entries repeat across four backbone panels exactly as the manuscript does; this baseline does not use a 3DFM.
- The physical tabletop wrist Nw=15 rotation comparison is retained: Zhi 1.09 deg, AnchorHEC 1.11 deg. There is no uniform-best claim.
- No calibration runs, statistical intervals, or new performance measurements were created.

## Headline

The 86.4% translation and 71.6% rotation reductions are rounded from the canonical `prose.headline_simulation_3dfm_camera_types` entry, verified here as 36 equally weighted conditions: three 3DFMs × two scene types × three wrist budgets × two camera types. Each condition uses `(baseline - AnchorHEC) / baseline`; wrist baseline is JCR, fixed baseline is JCR + SF. ViPE and physical experiments are excluded. Headline calculation uses full-precision canonical means; exported table records contain only rounded printed values.

## Interpretation

Output availability is distinct from calibration correctness. A complete record can include initial-estimate fallback or rejected registration. Relevant ViPE simulation Nw=5 and physical tabletop Nw=5 fallback notes are retained in JSON/CSV. Subsets from a physical acquisition are not independent robot remounts. No new confidence interval or generalized success probability is implied.
