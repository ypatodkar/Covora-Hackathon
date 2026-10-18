import type { ReactNode } from "react";
import type { LlmCallOut } from "../../api/types";
import { formatCost, formatDuration, formatTokens } from "./format";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 py-1.5 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words text-slate-900">{children}</dd>
    </div>
  );
}

export function LlmCallCard({ call }: { call: LlmCallOut }) {
  const sameModel = call.requested_model === call.actual_model;
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold">Model call</h3>
      <dl className="divide-y divide-slate-100">
        <Row label="Task">{call.task}</Row>
        <Row label="Routing mode">{call.routing_mode}</Row>
        {sameModel ? (
          <Row label="Model">
            <span className="font-mono">{call.actual_model}</span>
            <span className="ml-2 text-xs text-slate-400">as requested</span>
          </Row>
        ) : (
          <>
            <Row label="Requested model">
              <span className="font-mono">{call.requested_model}</span>
            </Row>
            <Row label="Actual model">
              <span className="font-mono">{call.actual_model}</span>
            </Row>
          </>
        )}
        <Row label="Routing reason">{call.routing_reason}</Row>
        <Row label="Fallback">
          {call.fallback_used
            ? `Yes — ${call.fallback_reason ?? "unknown reason"}`
            : "No"}
        </Row>
        <Row label="Tokens in / out">
          {formatTokens(call.prompt_tokens)} /{" "}
          {formatTokens(call.completion_tokens)}
        </Row>
        <Row label="Latency">{formatDuration(call.latency_ms)}</Row>
        <Row label="Est. cost">{formatCost(call.est_cost_usd)}</Row>
        <Row label="Retries">{call.retries}</Row>
        <Row label="Valid output">{call.output_valid ? "Yes" : "No"}</Row>
      </dl>
    </div>
  );
}
