import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { apiFetch, postJson } from "../../api/client";
import type { SalesRep } from "../../api/types";
import {
  inputClass,
  labelClass,
  primaryButton,
  secondaryButton,
} from "../../components/ui";

export function SalesTeamForm() {
  const queryClient = useQueryClient();
  const reps = useQuery({
    queryKey: ["sales-reps"],
    queryFn: () => apiFetch<SalesRep[]>("/sales-reps"),
  });
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [booking, setBooking] = useState("");
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["sales-reps"] });
  const add = useMutation({
    mutationFn: () =>
      postJson<SalesRep>("/sales-reps", {
        name,
        email,
        booking_url: booking || null,
        active: true,
      }),
    onSuccess: () => {
      setName("");
      setEmail("");
      setBooking("");
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/sales-reps/${id}`, { method: "DELETE" }),
    onSuccess: () => void refresh(),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };

  return (
    <div className="space-y-5">
      {reps.isError && (
        <p role="alert" className="text-sm text-red-600">
          {reps.error.message}
        </p>
      )}
      {reps.data && reps.data.length === 0 && (
        <p className="text-sm text-slate-500">No sales reps yet</p>
      )}
      {reps.data && reps.data.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
          {reps.data.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between gap-4 px-4 py-3 text-sm"
            >
              <div>
                <p className="font-medium text-slate-900">{r.name}</p>
                <p className="text-slate-500">
                  {r.email}
                  {r.booking_url ? ` · ${r.booking_url}` : ""}
                </p>
              </div>
              <button
                type="button"
                className={secondaryButton}
                onClick={() => remove.mutate(r.id)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        onSubmit={onSubmit}
        className="grid gap-4 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
      >
        <div>
          <label htmlFor="rep-name" className={labelClass}>
            Name
          </label>
          <input
            id="rep-name"
            required
            className={`${inputClass} mt-1`}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="rep-email" className={labelClass}>
            Email
          </label>
          <input
            id="rep-email"
            type="email"
            required
            className={`${inputClass} mt-1`}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="rep-booking" className={labelClass}>
            Booking link
          </label>
          <input
            id="rep-booking"
            className={`${inputClass} mt-1`}
            placeholder="https://cal.com/…"
            value={booking}
            onChange={(e) => setBooking(e.target.value)}
          />
        </div>
        <button
          type="submit"
          className={primaryButton}
          disabled={add.isPending}
        >
          Add rep
        </button>
      </form>
      {add.isError && (
        <p role="alert" className="text-sm text-red-600">
          {add.error.message}
        </p>
      )}
    </div>
  );
}
