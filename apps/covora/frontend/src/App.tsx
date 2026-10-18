import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AgentWorkflow } from "./pages/AgentWorkflow";
import { CampaignDetail } from "./pages/CampaignDetail";
import { Campaigns } from "./pages/Campaigns";
import { IcpStudio } from "./pages/IcpStudio";
import { Inbox } from "./pages/Inbox";
import { Overview } from "./pages/Overview";
import { Prospects } from "./pages/Prospects";
import { RunDetail } from "./pages/RunDetail";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="icp" element={<IcpStudio />} />
        <Route path="prospects" element={<Prospects />} />
        <Route path="campaigns" element={<Campaigns />} />
        <Route path="campaigns/:campaignId" element={<CampaignDetail />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="workflow" element={<AgentWorkflow />} />
        <Route path="workflow/runs/:runId" element={<RunDetail />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
