# AOI Wafer Inspector Alarm Guide

This fictional guide exists only for the Industrial AI Agent synthetic demo.
It is not operating guidance for real equipment.

## OPTICAL-SIGNAL-LOW

When `OPTICAL-SIGNAL-LOW` is recorded, keep the inspection lot paused. Confirm
that the optical lens cover is seated and free from visible synthetic debris.
Check that the illumination connector is seated in the fictional service panel.

Record the alarm code, equipment ID, lot ID, and observation time before making
any change. Do not infer that low yield caused the alarm. The production summary
and this alarm procedure are separate evidence sources.

### Recovery boundary

After the fictional lens cover and illumination connector checks, use the demo
reset control once. If the alarm remains recorded, leave the lot paused and
escalate the synthetic event to the demo maintenance role. This guide does not
authorize bypassing an interlock or changing an inspection threshold.

## SCRATCH-COUNT-HIGH

When a high scratch count is recorded, confirm the lot identifier and inspect
the synthetic handling record. Keep defect classification separate from cause:
a scratch category does not prove that handling created the observation.

## Normal shutdown

Finish the active synthetic record, place the demo equipment state in idle, and
then use the application shutdown action. Record incomplete demo work before
closing the session.
