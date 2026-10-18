import type { ReactNode } from "react";
import type {
  Location,
  Range,
  SizeBand,
  StructuredICP,
  Tagged,
} from "../../api/types";
import { inputClass, secondaryButton } from "../../components/ui";
import { OriginBadge, originRowClass } from "./OriginBadge";
import { TaggedList, asText } from "./TaggedList";

const asLocation = {
  format: (v: Location) =>
    v.regions.length ? `${v.country}: ${v.regions.join(", ")}` : v.country,
  parse: (text: string): Location => {
    const [country, regions = ""] = text.split(":");
    return {
      country: country.trim(),
      regions: regions
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean),
    };
  },
  empty: { country: "", regions: [] } as Location,
};

const toNumber = (text: string): number | null =>
  text.trim() === "" ? null : Number(text);
const splitTitles = (text: string) =>
  text
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-4 border-t border-slate-100 pt-6 first:border-0 first:pt-0">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function RangeField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Tagged<Range> | null;
  onChange: (value: Tagged<Range> | null) => void;
}) {
  if (value === null) {
    return (
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-slate-700">{label}</h3>
          <p className="text-sm text-slate-400">None yet</p>
        </div>
        <button
          type="button"
          className={secondaryButton}
          onClick={() =>
            onChange({ value: { min: null, max: null }, origin: "stated" })
          }
        >
          Add
        </button>
      </div>
    );
  }
  const set = (patch: Partial<Range>) =>
    onChange({ value: { ...value.value, ...patch }, origin: "stated" });
  return (
    <div className={originRowClass(value.origin)}>
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-medium text-slate-700">{label}</h3>
        <OriginBadge origin={value.origin} />
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          aria-label={`${label} min`}
          className={`${inputClass} w-40`}
          value={value.value.min ?? ""}
          placeholder="Any"
          onChange={(e) => set({ min: toNumber(e.target.value) })}
        />
        <span className="text-slate-400">to</span>
        <input
          type="number"
          aria-label={`${label} max`}
          className={`${inputClass} w-40`}
          value={value.value.max ?? ""}
          placeholder="Any"
          onChange={(e) => set({ max: toNumber(e.target.value) })}
        />
        <button
          type="button"
          className="text-xs text-slate-400 hover:text-red-600"
          onClick={() => onChange(null)}
        >
          Clear
        </button>
      </div>
    </div>
  );
}

function SizeBands({
  bands,
  onChange,
}: {
  bands: SizeBand[];
  onChange: (bands: SizeBand[]) => void;
}) {
  const set = (index: number, patch: Partial<SizeBand>) =>
    onChange(
      bands.map((b, i) =>
        i === index ? { ...b, ...patch, origin: "stated" } : b,
      ),
    );
  const add = () =>
    onChange([
      ...bands,
      {
        employees: { min: null, max: null },
        primary_titles: [],
        secondary_titles: [],
        origin: "stated",
      },
    ]);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-700">
          Who to contact, by company size
        </h3>
        <button type="button" className={secondaryButton} onClick={add}>
          Add
        </button>
      </div>
      {bands.length === 0 ? (
        <p className="text-sm text-slate-400">None yet</p>
      ) : (
        <ul className="space-y-4">
          {bands.map((band, i) => (
            <li key={i} className={`space-y-2 ${originRowClass(band.origin)}`}>
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <span>Companies with</span>
                <input
                  type="number"
                  aria-label={`Band ${i + 1} employees min`}
                  className={`${inputClass} w-24`}
                  value={band.employees.min ?? ""}
                  onChange={(e) =>
                    set(i, {
                      employees: {
                        ...band.employees,
                        min: toNumber(e.target.value),
                      },
                    })
                  }
                />
                <span>to</span>
                <input
                  type="number"
                  aria-label={`Band ${i + 1} employees max`}
                  className={`${inputClass} w-24`}
                  value={band.employees.max ?? ""}
                  onChange={(e) =>
                    set(i, {
                      employees: {
                        ...band.employees,
                        max: toNumber(e.target.value),
                      },
                    })
                  }
                />
                <span>employees</span>
                <OriginBadge origin={band.origin} />
                <button
                  type="button"
                  className="ml-auto text-xs text-slate-400 hover:text-red-600"
                  onClick={() => onChange(bands.filter((_, j) => j !== i))}
                >
                  Remove
                </button>
              </div>
              <input
                aria-label={`Band ${i + 1} primary titles`}
                className={inputClass}
                value={band.primary_titles.join(", ")}
                placeholder="Primary titles, comma-separated"
                onChange={(e) =>
                  set(i, { primary_titles: splitTitles(e.target.value) })
                }
              />
              <input
                aria-label={`Band ${i + 1} secondary titles`}
                className={inputClass}
                value={band.secondary_titles.join(", ")}
                placeholder="Backup titles, comma-separated"
                onChange={(e) =>
                  set(i, { secondary_titles: splitTitles(e.target.value) })
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ReadOnlyList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: string[];
  emptyText: string;
}) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-slate-700">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400">{emptyText}</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function IcpEditor({
  value,
  onChange,
}: {
  value: StructuredICP;
  onChange: (value: StructuredICP) => void;
}) {
  const set = (patch: Partial<StructuredICP>) =>
    onChange({ ...value, ...patch });
  const setBuyer = (patch: Partial<StructuredICP["buyer_map"]>) =>
    onChange({ ...value, buyer_map: { ...value.buyer_map, ...patch } });

  return (
    <div className="space-y-6">
      <Section title="Summary">
        <textarea
          aria-label="Summary"
          className={inputClass}
          rows={2}
          value={value.summary}
          onChange={(e) => set({ summary: e.target.value })}
        />
      </Section>
      <Section title="Which companies">
        <TaggedList
          label="Industries"
          items={value.industries}
          onChange={(industries) => set({ industries })}
          {...asText}
        />
        <TaggedList
          label="Locations"
          items={value.locations}
          onChange={(locations) => set({ locations })}
          {...asLocation}
        />
        <RangeField
          label="Employees"
          value={value.employee_range}
          onChange={(employee_range) => set({ employee_range })}
        />
        <RangeField
          label="Revenue"
          value={value.revenue_range_usd}
          onChange={(revenue_range_usd) => set({ revenue_range_usd })}
        />
        <TaggedList
          label="Other criteria"
          items={value.other_criteria}
          onChange={(other_criteria) => set({ other_criteria })}
          {...asText}
        />
        <TaggedList
          label="Exclusions"
          items={value.exclusions}
          onChange={(exclusions) => set({ exclusions })}
          {...asText}
        />
      </Section>
      <Section title="Buyer map">
        <TaggedList
          label="Target functions"
          items={value.buyer_map.target_functions}
          onChange={(target_functions) => setBuyer({ target_functions })}
          {...asText}
        />
        <SizeBands
          bands={value.buyer_map.by_company_size}
          onChange={(by_company_size) => setBuyer({ by_company_size })}
        />
        <TaggedList
          label="Titles to skip"
          items={value.buyer_map.skip_titles}
          onChange={(skip_titles) => setBuyer({ skip_titles })}
          {...asText}
        />
      </Section>
      <Section title="How Covora read it">
        <ReadOnlyList
          title="Assumptions"
          items={value.assumptions}
          emptyText="No assumptions."
        />
        <ReadOnlyList
          title="Planned searches"
          items={value.search_queries}
          emptyText="None yet"
        />
      </Section>
    </div>
  );
}
