import type { SpanOut } from "../../api/types";
import { formatDuration } from "./format";

const KIND_STYLES: Record<string, string> = {
  agent: "bg-indigo-50 text-indigo-700",
  llm: "bg-violet-50 text-violet-700",
  memory: "bg-teal-50 text-teal-700",
  tool: "bg-orange-50 text-orange-700",
};

interface Node {
  span: SpanOut;
  children: Node[];
}

function buildTree(spans: SpanOut[]): Node[] {
  const nodes = new Map(
    spans.map((s) => [s.id, { span: s, children: [] as Node[] }]),
  );
  const roots: Node[] = [];
  for (const node of nodes.values()) {
    const parent = node.span.parent_span_id
      ? nodes.get(node.span.parent_span_id)
      : undefined;
    (parent ? parent.children : roots).push(node);
  }
  return roots;
}

function Row({
  node,
  depth,
  selectedId,
  onSelect,
}: {
  node: Node;
  depth: number;
  selectedId: string | null;
  onSelect: (span: SpanOut) => void;
}) {
  const { span } = node;
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(span)}
        style={{ paddingLeft: `${depth * 1.25 + 0.75}rem` }}
        className={`flex w-full items-center gap-3 rounded-md py-2 pr-3 text-left text-sm hover:bg-slate-50 ${
          span.id === selectedId ? "bg-indigo-50" : ""
        }`}
      >
        <span className="font-mono text-slate-800">{span.name}</span>
        <span
          className={`rounded px-1.5 py-0.5 text-xs ${KIND_STYLES[span.kind] ?? "bg-slate-100 text-slate-600"}`}
        >
          {span.kind}
        </span>
        {span.status === "running" && (
          <span className="text-xs text-sky-700">running…</span>
        )}
        <span className="ml-auto text-xs text-slate-400">
          {formatDuration(span.duration_ms)}
        </span>
      </button>
      {span.status === "error" && span.error && (
        <p
          className="mb-1 text-xs text-red-600"
          style={{ paddingLeft: `${depth * 1.25 + 0.75}rem` }}
        >
          <span className="mr-1 rounded bg-red-100 px-1.5 py-0.5 font-medium">
            error
          </span>
          {span.error}
        </p>
      )}
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <Row
              key={child.span.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export function SpanTree({
  spans,
  selectedId,
  onSelect,
}: {
  spans: SpanOut[];
  selectedId: string | null;
  onSelect: (span: SpanOut) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {buildTree(spans).map((node) => (
        <Row
          key={node.span.id}
          node={node}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </ul>
  );
}
