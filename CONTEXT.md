# Manufacturing Analysis

This context defines the language used for fictional semiconductor-manufacturing
records and deterministic analysis. It keeps recorded observations and calculated
results separate from model interpretation.

## Language

**Equipment**:
A fictional machine that processes or inspects production units.
_Avoid_: Machine, tool

**Production Lot**:
A named group of wafers tracked together through a synthetic manufacturing
scenario.
_Avoid_: Batch, run

**Wafer**:
The production unit counted by the first inspection scenario.
_Avoid_: Unit, item

**Inspection Record**:
A time-stamped observation of how many wafers from one Production Lot were
inspected, passed, and failed by one Equipment.
_Avoid_: Production record, measurement

**Defect Count**:
The number of failed wafers in an Inspection Record assigned to one fictional
defect category.
_Avoid_: Defect rate, issue count

**Alarm Event**:
A time-bounded, fictional equipment event recorded independently from inspection
results. Co-occurrence does not establish causation.
_Avoid_: Root cause, failure

**Time Range**:
A UTC interval that includes its start and excludes its end.
_Avoid_: Window, period

**Yield Rate**:
The calculated ratio of passed wafers to inspected wafers for a defined Time
Range. It is unavailable when no wafers were inspected.
_Avoid_: Pass rate

**Production Summary**:
A deterministic aggregation of Inspection Records, Defect Counts, and Alarm
Events for one Equipment and Time Range.
_Avoid_: Analysis answer, report
