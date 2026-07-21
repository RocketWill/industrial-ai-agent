import { Alert, Button, Form, Input, Select, Skeleton, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import type { WorkspaceContextState } from "../hooks/useWorkspaceContext";

const timeRanges = ["Last 1 hour", "Last 4 hours", "Last 8 hours", "Last 24 hours"];

type ContextDraft = {
  device: string;
  lot: string;
  timeRange: string;
};

type Props = {
  state: WorkspaceContextState;
  disabled: boolean;
  resetToken?: number;
  onDirtyChange?: (dirty: boolean) => void;
};

export default function AnalysisContext({ state, disabled, resetToken = 0, onDirtyChange }: Props) {
  const [draft, setDraft] = useState<ContextDraft>({ device: "", lot: "", timeRange: "" });
  const [lotError, setLotError] = useState<string | null>(null);
  const source = state.context;
  const saved = useMemo(() => ({
    device: source?.device ?? "",
    lot: source?.lot ?? "",
    timeRange: source?.time_range ?? "",
  }), [source]);
  const dirty = draft.device !== saved.device || draft.lot !== saved.lot || draft.timeRange !== saved.timeRange;

  useEffect(() => {
    setDraft(saved);
    setLotError(null);
  }, [saved, resetToken]);

  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  const save = async () => {
    if (draft.lot.trim().length > 200) {
      setLotError("Lot must be 200 characters or fewer.");
      return;
    }
    setLotError(null);
    await state.save({
      device: draft.device.trim() || null,
      lot: draft.lot.trim() || null,
      time_range: draft.timeRange || null,
    });
  };

  return (
    <aside className="context-inspector" aria-label="Analysis context">
      <header className="inspector-header">
        <div>
          <Typography.Text className="section-label">Analysis context</Typography.Text>
          <Typography.Title level={3}>Query scope</Typography.Title>
        </div>
        <Tag color="cyan">Synthetic Demo</Tag>
      </header>
      {state.isLoading ? (
        <Skeleton active paragraph={{ rows: 7 }} />
      ) : (
        <Form layout="vertical" className="context-form" disabled={disabled}>
          <Form.Item label="Device">
            <Select
              aria-label="Device"
              allowClear
              loading={state.devicesLoading}
              status={state.devicesError ? "error" : undefined}
              placeholder="Not selected"
              value={draft.device || undefined}
              onChange={(value) => setDraft((current) => ({ ...current, device: value ?? "" }))}
              options={state.devices.map((item) => ({ value: item.id, label: `${item.name} - ${item.category}` }))}
            />
          </Form.Item>
          <Form.Item label="Lot" validateStatus={lotError ? "error" : undefined} help={lotError}>
            <Input
              value={draft.lot}
              onChange={(event) => setDraft((current) => ({ ...current, lot: event.target.value }))}
              placeholder="Optional lot identifier"
            />
          </Form.Item>
          <Form.Item label="Time range">
            <Select
              aria-label="Time range"
              allowClear
              placeholder="Not selected"
              value={draft.timeRange || undefined}
              onChange={(value) => setDraft((current) => ({ ...current, timeRange: value ?? "" }))}
              options={timeRanges.map((value) => ({ value, label: value }))}
            />
          </Form.Item>
          <div className="context-metadata" aria-label="Context metadata">
            <div><Typography.Text type="secondary">Environment</Typography.Text><Typography.Text>{source?.environment ?? "Not available"}</Typography.Text></div>
            <div><Typography.Text type="secondary">Data source</Typography.Text><Typography.Text>Synthetic Demo</Typography.Text></div>
          </div>
          {(state.devicesError || state.error) && <Alert type="error" showIcon title={state.devicesError ?? state.error} />}
          <div className="context-actions">
            <Button disabled={!dirty || state.isSaving} onClick={() => setDraft(saved)}>Reset</Button>
            <Button color="primary" variant="solid" loading={state.isSaving} disabled={!dirty} onClick={() => void save()}>Save context</Button>
          </div>
        </Form>
      )}
    </aside>
  );
}
