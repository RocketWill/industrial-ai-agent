# Data

## Purpose

This directory is reserved for project-owned synthetic datasets and fictional
documents introduced by later milestones.

## Safety boundary

Real production data, equipment exports, customer information, proprietary
documents, database dumps, and uncertain-source artifacts must not be placed
here.

## Current status

The implemented v0.3 slice includes
`synthetic/aoi-wafer-inspection-v1.json`, one independently created fictional
AOI scenario. Production-summary and equipment-status tools load this file
through validated domain types. Its equipment states are explicit synthetic
intervals rather than inferences from inspection or alarm records, and the
scenario makes no causal claim. No production or uncertain-source data is
included.

The first v0.5 slice also includes
`synthetic/documents/aoi-wafer-inspector-alarm-guide.md`. It is an independently
written fictional guide used to test Markdown chunking, local vector retrieval,
citations, and source rendering. It is not operating guidance for real
equipment.

Additional synthetic datasets and fictional documents should be added only
when a milestone defines their schema, validation boundary, and tests.
