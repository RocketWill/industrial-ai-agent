# AOI Preventive Maintenance Guide

This Synthetic Demo document is independently written fictional material for
the Industrial AI Agent portfolio project. It describes a maintenance record
for a fictional AOI demonstration station. It is not an instruction manual for
servicing physical equipment and must not be used to operate, open, adjust, or
repair a real machine.

## Maintenance boundary

The demo maintenance workflow records planned checks as synthetic events. It
does not measure wear, certify a component, or determine a root cause. The
operator can record what the application displays, while a qualified owner of
any real system would need a separate procedure, authorization, and risk
review.

The useful result is a traceable record, not a confident guess. If a check is
not represented in the application, leave it unrecorded rather than inventing
an outcome.

## Scheduled demo review

### Illumination panel observation

Open the fictional maintenance task in the demo application and review the
illumination-panel observation supplied by the scenario. Record whether the
application reports the panel as clear, flagged, or unavailable. These labels
describe synthetic application state only. They do not represent a measured
light level or a physical cleanliness assessment.

### Carrier path observation

Review the synthetic carrier-path note and compare its equipment and task
identifiers with the maintenance record. Keep the original note alongside any
operator comment. Do not rewrite an unavailable observation as a pass. And do
not treat a repeated application flag as proof that one component caused a
production or inspection result.

## Record a maintenance event

For each completed demo check, record the task identifier, UTC observation
time, displayed state, and a short note. Four fields are enough for this
scenario to remain reproducible. A note such as “not available in demo data”
is more useful than a guessed condition because it preserves the evidence
boundary.

If the application returns an invalid task or timestamp, stop the maintenance
event and retain the error state. The workflow should not silently move an
event to another date, equipment identifier, or task merely to make the record
look complete.

## Hold and escalation boundary

A flagged or unavailable demo observation should remain visible for review.
The scenario may label the event as needing follow-up, but it does not authorize
opening a housing, changing an optical setting, bypassing a safeguard, or
returning a physical machine to service. No real equipment action is implied.

When an alarm appears with a maintenance event, record the two event types
separately. The shared timestamp can be cited as an observation; it cannot be
used as evidence of cause without an independent investigation.

## Return the demo to an available state

After the synthetic fields are checked, close the maintenance task in the demo
application. Mark the task complete only when its displayed state, identifier,
and observation time are present. Otherwise keep it open with the explicit
limitation that the synthetic evidence is incomplete.

## Evidence limits

This guide is a fictional retrieval artifact. It includes no maintenance
interval for real equipment, no component specification, no service password,
and no validated safety instruction. Its purpose is to test how an agent
retrieves maintenance-related evidence while keeping recorded observations
separate from calculations, interpretations, and unsupported operational
claims.
