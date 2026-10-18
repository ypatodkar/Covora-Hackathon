import type { IcpVersionOut } from "../../api/types";

export function VersionHistory({
  versions,
  activeId,
  onSelect,
}: {
  versions: IcpVersionOut[];
  activeId: string | null;
  onSelect: (version: IcpVersionOut) => void;
}) {
  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-slate-700">
        Saved versions
      </h2>
      {versions.length === 0 ? (
        <p className="text-sm text-slate-400">No saved versions yet.</p>
      ) : (
        <ul className="space-y-1">
          {versions.map((v) => (
            <li key={v.id}>
              <button
                type="button"
                onClick={() => onSelect(v)}
                className={`w-full rounded-md px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                  v.id === activeId
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600"
                }`}
              >
                <span className="font-medium">v{v.version}</span>
                <span className="text-slate-400">
                  {" "}
                  · {new Date(v.created_at).toLocaleDateString()} ·{" "}
                </span>
                <span>{v.structured.summary}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
