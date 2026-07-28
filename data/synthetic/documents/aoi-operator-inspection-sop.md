# AOI Operator Inspection SOP

This Synthetic Demo document is independently written fictional material for
the Industrial AI Agent portfolio project. It describes a software scenario
around a fictional AOI inspection station. It is not operating guidance for a
physical machine, a production line, or any real equipment.

## Purpose and boundary

This procedure gives the demo operator a consistent order for creating and
reviewing one synthetic inspection record. The record is an input to a test
scenario, not proof that an inspection occurred. The project uses it to keep
recorded fields, deterministic calculations, and later model interpretation
separate.

This is a boundary. A recorded observation is not a diagnosis. The procedure
does not establish a defect cause, equipment condition, product quality, or
permission to change a real process.

## Prepare a demo inspection

### Confirm the inspection context

Before starting the scenario, select the fictional equipment identifier,
synthetic lot identifier, and UTC time range shown by the demo application. The
operator should check that the identifiers belong to the same test scenario.
If a required value is missing or unclear, leave the record unstarted and
report the missing context in the scenario notes.

### Confirm the demo record

Create one empty inspection record with a stable scenario identifier. For this
demo, the record contains four required values: inspected wafer count, passed
wafer count, failed wafer count, and observation time. Counts are data fields,
not estimates. Do not fill an unknown value with a plausible number just to
continue the example.

## Run the inspection scenario

Start the fictional inspection action from the demo application. Keep the
selected context unchanged while the scenario is running. When the action
returns, copy the recorded counts into the inspection record and verify that
the passed and failed counts do not exceed the inspected count.

If the application reports an incomplete or malformed result, preserve the
returned status in the notes and stop the scenario. Do not repair a missing
count by inference. But a failed demo step should still leave a trace of what
was observed, because the failure itself is useful test evidence.

## Review an observation

Review the record against the selected context before asking the agent to
summarize it. Compare identifiers and timestamps first, then check the count
relationship. A matching record supports a deterministic summary of the
recorded values; it does not support a claim about why those values occurred.

When an alarm or maintenance note appears in the same scenario, keep it as a
separate evidence item. Co-occurrence can be reported, but it does not prove a
causal connection. (That distinction is intentional.)

## Close the synthetic record

Save the completed demo record only after the required fields and boundaries
have been checked. If the record remains incomplete, label it as incomplete
and keep the missing field visible. The agent may explain that evidence is
insufficient, but it must not present an absent value as an equipment status or
production result.

## Evidence limits

This SOP is a fictional test artifact. It contains no live telemetry, real
equipment interface, production data, or validated operating limits. Its terms
are chosen to exercise document retrieval and evidence handling in a synthetic
application. Any question about a physical inspection system requires a
separate, authorized source and qualified human review.
