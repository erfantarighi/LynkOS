import { Navigate, Route, Routes } from "react-router-dom";
import { SWRConfig } from "swr";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Wifi from "./pages/Wifi";
import Pppoe from "./pages/Pppoe";
import RoutesPage from "./pages/Routes";
import VlansPage from "./pages/Vlans";
import DdnsPage from "./pages/Ddns";
import Wireguard from "./pages/Wireguard";
import Speedtest from "./pages/Speedtest";
import Security from "./pages/Security";
import Adblock from "./pages/Adblock";
import Clients from "./pages/Clients";
import Account from "./pages/Account";
import Login from "./pages/Login";
import AIPage from "./pages/AI";
import { fetcher, getToken } from "./api";

function RequireAuth({ children }: { children: React.ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <SWRConfig value={{ fetcher, refreshInterval: 5000, shouldRetryOnError: false }}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="wifi" element={<Wifi />} />
          <Route path="pppoe" element={<Pppoe />} />
          <Route path="vlans" element={<VlansPage />} />
          <Route path="routes" element={<RoutesPage />} />
          <Route path="ddns" element={<DdnsPage />} />
          <Route path="wireguard" element={<Wireguard />} />
          <Route path="speedtest" element={<Speedtest />} />
          <Route path="security" element={<Security />} />
          <Route path="adblock" element={<Adblock />} />
          <Route path="clients" element={<Clients />} />
          <Route path="ai" element={<AIPage />} />
          <Route path="account" element={<Account />} />
        </Route>
      </Routes>
    </SWRConfig>
  );
}
