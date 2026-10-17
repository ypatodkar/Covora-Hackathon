import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch, postJson } from "../api/client";
import type { IcpVersionOut, ParseResponse, StructuredICP } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { cardClass, inputClass, labelClass, primaryButton, secondaryButton } from "../components/ui";
import { IcpEditor } from "../features/icp/IcpEditor";
import { VersionHistory } from "../features/icp/VersionHistory";

export function IcpStudio() {
  const queryClient = useQueryClient();
  const [promptText, setPromptText] = useState("");
  const [draft, setDraft] = useState<StructuredICP | null>(null);
  const [edited, setEdited] = useState<StructuredICP | null>(null);
  const [parentId, setParentId] = useState<string | null>(null);
  const [savedVersion, setSavedVersion] = useState<number | null>(null);

  const versions = useQuery({ queryKey: ["icps"], queryFn: () => apiFetch<IcpVersionOut[]>("/icps") });

  const parse = useMutation({
    mutationFn: (text: string) => postJson<ParseResponse>("/icp/parse", { prompt_text: text }),
    onSuccess: (result) => {
      setDraft(result.draft);
      setEdited(result.draft);
      setSavedVersion(null);
    },
  });

  const save = useMutation({
    mutationFn: () =>
      postJson<IcpVersionOut>("/icps", { prompt_text: promptText, structured: edited, draft, parent_id: parentId }),
    onSuccess: (version) => {
      setSavedVersion(version.version);
      setParentId(version.id);
      setDraft(version.structured);
      setEdited(version.structured);
      void queryClient.invalidateQueries({ queryKey: ["icps"] });
    },
  });

  const loadVersion = (version: IcpVersionOut) => {
    setPromptText(version.prompt_text);
    setDraft(version.structured);
    setEdited(version.structured);
    setParentId(version.id);
    setSavedVersion(null);
    parse.reset();
  };

  return (
    <>
      <PageHeader
        title="ICP Studio"
        subtitle="Describe who you want to reach. Covora turns it into a profile its agents can search with."
      />
      <div className="grid gap-8 lg:grid-cols-[1fr_16rem]">
        <div className="space-y-6">
          <section className={cardClass}>
            <label htmlFor="vibe-prompt" className={labelClass}>
              Describe your ideal customers
            </label>
            <textarea
              id="vibe-prompt"
              className={`${inputClass} mt-2`}
              rows={4}
              value={promptText}
              placeholder="Find manufacturing companies in the US with 5–25 employees…"
              onChange={(e) => setPromptText(e.target.value)}
            />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                className={primaryButton}
                disabled={parse.isPending || promptText.trim() === ""}
                onClick={() => parse.mutate(promptText)}
              >
                {parse.isPending ? "Interpreting…" : "Interpret"}
              </button>
            </div>
            {parse.isError && (
              <div role="alert" className="mt-4 flex items-center justify-between rounded-md bg-red-50 px-4 py-3">
                <span className="text-sm text-red-700">{parse.error.message}</span>
                <button type="button" className={secondaryButton} onClick={() => parse.mutate(promptText)}>
                  Try again
                </button>
              </div>
            )}
          </section>

          {edited && (
            <section className={cardClass}>
              <IcpEditor value={edited} onChange={setEdited} />
              <div className="mt-8 flex items-center justify-end gap-3 border-t border-slate-100 pt-6">
                {savedVersion !== null && <span className="text-sm text-emerald-700">Saved as v{savedVersion}</span>}
                {save.isError && (
                  <span role="alert" className="text-sm text-red-600">
                    {save.error.message}
                  </span>
                )}
                <button
                  type="button"
                  className={primaryButton}
                  disabled={save.isPending || promptText.trim() === ""}
                  onClick={() => save.mutate()}
                >
                  Save version
                </button>
              </div>
            </section>
          )}
        </div>
        <aside>
          <VersionHistory versions={versions.data ?? []} activeId={parentId} onSelect={loadVersion} />
        </aside>
      </div>
    </>
  );
}
