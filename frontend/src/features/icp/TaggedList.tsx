import type { Tagged } from "../../api/types";
import { inputClass, secondaryButton } from "../../components/ui";
import { OriginBadge, originRowClass } from "./OriginBadge";

interface Props<T> {
  label: string;
  items: Tagged<T>[];
  onChange: (items: Tagged<T>[]) => void;
  format: (value: T) => string;
  parse: (text: string) => T;
  empty: T;
}

/** An editable list of tagged values. Anything the user edits or adds becomes "stated". */
export function TaggedList<T>({ label, items, onChange, format, parse, empty }: Props<T>) {
  const setItem = (index: number, text: string) =>
    onChange(items.map((item, i) => (i === index ? { value: parse(text), origin: "stated" } : item)));
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));
  const add = () => onChange([...items, { value: empty, origin: "stated" }]);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-700">{label}</h3>
        <button type="button" className={secondaryButton} onClick={add}>
          Add
        </button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400">None yet</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className={`flex items-center gap-2 ${originRowClass(item.origin)}`}>
              <input
                aria-label={`${label} ${i + 1}`}
                className={inputClass}
                value={format(item.value)}
                onChange={(e) => setItem(i, e.target.value)}
              />
              <OriginBadge origin={item.origin} />
              <button
                type="button"
                className="text-xs text-slate-400 hover:text-red-600"
                aria-label={`Remove ${label} ${i + 1}`}
                onClick={() => remove(i)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export const asText = {
  format: (v: string) => v,
  parse: (t: string) => t,
  empty: "",
};
