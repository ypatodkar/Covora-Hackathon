import { NavLink } from "react-router-dom";

const SECTIONS = [
  { to: "/", label: "Overview" },
  { to: "/icp", label: "ICP Studio" },
  { to: "/prospects", label: "Prospects" },
  { to: "/campaigns", label: "Campaigns" },
  { to: "/inbox", label: "Inbox" },
  { to: "/workflow", label: "Agent Workflow" },
  { to: "/settings", label: "Settings" },
];

export function Sidebar() {
  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-6">
      <div className="mb-8 px-3 text-lg font-semibold tracking-tight">
        Covora
      </div>
      <ul className="space-y-1">
        {SECTIONS.map((s) => (
          <li key={s.to}>
            <NavLink
              to={s.to}
              end={s.to === "/"}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm ${
                  isActive
                    ? "bg-indigo-50 font-medium text-indigo-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`
              }
            >
              {s.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
