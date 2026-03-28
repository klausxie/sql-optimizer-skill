# SQL Optimizer Web Dashboard - Implementation Plan

**Created:** 2026-03-28
**Feature:** Web Dashboard for sql-optimizer-skill pipeline visualization
**Status:** Draft for Approval

---

## 1. Concept & Vision

A standalone, shareable HTML dashboard that transforms the 5-stage pipeline outputs into an impressive, interactive visual experience. The dashboard should feel like a premium analytics tool—dark-themed, data-dense, with smooth animations and intuitive navigation between stages. Users can open the HTML file locally or host it anywhere, reading data from JSON files in `runs/{run_id}/{stage}/`.

---

## 2. Technical Approach

### Architecture Decision: Single HTML File

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Single HTML | Easy to share, no build step, CDN deps | Less maintainable for complex UI | **✓ Chosen** |
| Multi-file SPA | Better organization | Requires hosting, harder to share | ✗ |
| React/Vue app | Component reuse | Overkill, complex setup | ✗ |

**Rationale:** User requirement states "standalone", "static HTML", "easy to share". Single HTML with embedded CSS/JS meets all criteria.

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Charting | Chart.js 4.x (CDN) | Already used in project, lightweight, good animations |
| UI Framework | Vanilla CSS + CSS Variables | No framework needed for this scope |
| Icons | Inline SVG | No external dependency |
| Fonts | System fonts + Inter (CDN) | Fast load, consistent look |
| Data Loading | Fetch API + local JSON | Works with file:// protocol |

### Design Language

- **Theme:** Dark mode (matching existing `relationship_report_generator.py`)
- **Colors:** Blue (#60a5fa), Purple (#a78bfa), Green (#34d399), Orange (#fb923c), Red (#f87171)
- **Layout:** Tab-based navigation, card-grid for stats, responsive charts
- **Animations:** Chart.js built-in animations, subtle hover transitions

---

## 3. Dashboard Structure

### Tab Navigation (5 Stages)

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] SQL Optimizer Dashboard          [Run ID Selector] │
├─────────────────────────────────────────────────────────────┤
│  [Init] [Parse] [Recognition] [Optimize] [Result] [Summary]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    Stage Content Area                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Stage Visualizations

#### Init Tab
| Visualization | Chart Type | Data Source |
|---------------|------------|--------------|
| SQL Statement Types | Doughnut | sql_units[].statement_type distribution |
| SQL per Mapper File | Bar | sql_units[].mapper_file grouping |
| Table Hotspot Scores | Horizontal Bar TOP 10 | table_hotspots[].hotspot_score |
| Risk Level Distribution | Doughnut | table_hotspots[].risk_level counts |
| Table IN/OUT Degree | Scatter/Bubble | table_hotspots[].incoming/outgoing |
| Relationship Types | Doughnut | table_relationships[].is_explicit_join |
| Relationship Directions | Bar | table_relationships[].direction |

#### Parse Tab
| Visualization | Chart Type | Data Source |
|---------------|------------|--------------|
| Branch Count Distribution | Histogram | branches per sql_unit |
| Risk Flag Types | Horizontal Bar | risk_flags[] flattened |
| Validity Rate | Doughnut | branches[].is_valid |
| Risk Score Distribution | Bar | branches[].risk_score |
| Branches by Type | Doughnut | branches[].branch_type |

#### Recognition Tab
| Visualization | Chart Type | Data Source |
|---------------|------------|--------------|
| Cost Distribution | Histogram | baselines[].estimated_cost |
| Plan Node Types | Doughnut | baselines[].plan."Node Type" |
| Rows Returned vs Examined | Scatter | rows_returned vs rows_examined |
| Actual vs Estimated Time | Bar (if available) | actual_time_ms vs estimated |
| Cost by SQL Unit | Bar | baselines[].estimated_cost grouped |

#### Optimize Tab
| Visualization | Chart Type | Data Source |
|---------------|------------|--------------|
| Confidence Distribution | Bar/Histogram | proposals[].confidence |
| Gain Ratio Distribution | Histogram | proposals[].gain_ratio |
| Issue Types | Horizontal Bar | proposals[].actions[].issue_type |
| Before/After Cost Comparison | Grouped Bar | before_metrics vs after_metrics |
| Confidence by SQL Unit | Stacked Bar | proposals grouped by unit |

#### Result Tab
| Visualization | Chart Type | Data Source |
|---------------|------------|--------------|
| Patch Status | Doughnut | can_patch boolean |
| Optimization Summary | KPI Cards | Counts, confidence avg |
| Recommendations | List | report.recommendations[] |
| Risks | List with severity | report.risks[] |

#### Summary Tab (Cross-Stage)
| Visualization | Chart Type | Data Source |
|---------------|------------|--------------|
| Pipeline Overview | Custom Funnel | Stage counts |
| Stage Timing | Horizontal Bar | (future: timing data) |
| Overall Health Score | Gauge | Aggregate metrics |

---

## 4. File Structure

```
sql-optimizer-skill/
├── python/sqlopt/
│   └── common/
│       └── dashboard_generator.py    # NEW: Generates dashboard HTML
├── templates/
│   └── dashboard/
│       └── index.html               # NEW: Dashboard template
├── runs/
│   └── {run_id}/
│       └── dashboard/              # NEW: Generated dashboard output
│           └── index.html
```

**Note:** Dashboard can also be generated on-demand by the CLI or opened directly from template with user-provided run_id.

---

## 5. Data Loading Strategy

```javascript
// Proposed data loading flow
async function loadDashboard(runId) {
  const basePath = `runs/${runId}`;
  
  // Load all stage data in parallel
  const [init, parse, recognition, optimize, result] = await Promise.all([
    fetch(`${basePath}/init/sql_units.json`),
    fetch(`${basePath}/parse/sql_units_with_branches.json`),
    fetch(`${basePath}/recognition/baselines.json`),
    fetch(`${basePath}/optimize/proposals.json`),
    fetch(`${basePath}/result/report.json`),
  ]);
  
  // Additional data files
  const [hotspots, relationships, xmlMappings] = await Promise.all([
    fetch(`${basePath}/init/table_hotspots.json`),
    fetch(`${basePath}/init/table_relationships.json`),
    fetch(`${basePath}/init/xml_mappings.json`),
  ]);
  
  return { init, parse, recognition, optimize, result, hotspots, relationships, xmlMappings };
}
```

---

## 6. Implementation Waves

### Wave 1: Dashboard Core (HTML/CSS/JS Foundation)

| Task | Description | Owner |
|------|-------------|-------|
| 1.1 | Create `templates/dashboard/index.html` with tab structure and dark theme CSS | Atlas |
| 1.2 | Implement data loading module with fetch + local JSON | Atlas |
| 1.3 | Create Init tab visualizations (SQL types, hotspots, relationships) | Atlas |
| 1.4 | Create tab navigation and switching logic | Atlas |

### Wave 2: All Stage Visualizations

| Task | Description | Owner |
|------|-------------|-------|
| 2.1 | Implement Parse tab (branch distribution, risk flags) | Atlas |
| 2.2 | Implement Recognition tab (cost distribution, plan types) | Atlas |
| 2.3 | Implement Optimize tab (confidence, gain ratio, issue types) | Atlas |
| 2.4 | Implement Result tab (patch status, recommendations) | Atlas |
| 2.5 | Implement Summary tab (cross-stage funnel) | Atlas |

### Wave 3: Generator + Integration

| Task | Description | Owner |
|------|-------------|-------|
| 3.1 | Create `dashboard_generator.py` in common/ | Atlas |
| 3.2 | Add CLI command: `sqlopt dashboard --run-id <id>` | Atlas |
| 3.3 | Add `--open` flag to auto-open in browser | Atlas |

### Wave 4: Polish & Testing

| Task | Description | Owner |
|------|-------------|-------|
| 4.1 | Add empty state handling for missing data | Atlas |
| 4.2 | Add run ID selector dropdown | Atlas |
| 4.3 | Test with mock data templates | Atlas |
| 4.4 | Performance optimization (lazy chart rendering) | Atlas |

---

## 7. Acceptance Criteria

### Must Have
- [ ] Single HTML file that opens locally (file:// protocol works)
- [ ] All 5 stage tabs functional with correct visualizations
- [ ] Data loads from JSON files in `runs/{run_id}/{stage}/`
- [ ] Dark theme matching existing report style
- [ ] Responsive layout (works on laptop screens 1280px+)
- [ ] Chart.js CDN dependency loads correctly

### Should Have
- [ ] Empty state UI when data is missing
- [ ] Run ID selector to switch between runs
- [ ] Smooth tab transitions
- [ ] Loading indicator while fetching data

### Nice to Have
- [ ] Auto-refresh when JSON files change
- [ ] Export to PNG for charts
- [ ] Keyboard navigation between tabs

---

## 8. File Ownership Table

| File | Owner Task | Non-Overlapping Tasks |
|------|-----------|---------------------|
| `templates/dashboard/index.html` | Wave 1 (Task 1.1) | All Wave 2-4 tasks add content to this file |
| `python/sqlopt/common/dashboard_generator.py` | Wave 3 (Task 3.1) | None |
| `python/sqlopt/cli/dashboard.py` | Wave 3 (Task 3.2) | None |

---

## 9. Testing Strategy

| Test | Method | Success Criteria |
|------|--------|-----------------|
| Open locally | Double-click HTML file | Page loads without errors |
| Load mock data | Use templates/mock/ JSON | All charts render correctly |
| Tab switching | Click each tab | Content updates, charts resize |
| Missing data | Open with incomplete run | Empty states shown gracefully |
| Responsive | Resize browser to 1280px | Layout adapts without horizontal scroll |

---

## 10. Open Questions

1. **Q:** Should the dashboard auto-detect the latest run_id, or require explicit selection?
   - **A:** Explicit selection with "latest" as default option

2. **Q:** Should we support multiple run_id comparison view?
   - **A:** No, single run view for MVP. Comparison could be Phase 2.

3. **Q:** How to handle very large projects with hundreds of SQL units?
   - **A:** Top 20 items per chart, pagination for detailed lists in Phase 2.

---

## 11. Next Steps

1. Confirm this design approach meets requirements
2. Approve plan → Execute Wave 1
3. Review Wave 1 → Execute Wave 2
4. Review Wave 2 → Execute Wave 3
5. Final review → Polish & Test
