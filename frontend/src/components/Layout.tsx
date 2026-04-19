import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearToken } from "../api";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/wifi", label: "WiFi / Hotspot" },
  { to: "/pppoe", label: "PPPoE / WAN" },
  { to: "/vlans", label: "VLANs" },
  { to: "/routes", label: "Routes" },
  { to: "/ddns", label: "Dynamic DNS" },
  { to: "/wireguard", label: "WireGuard" },
  { to: "/speedtest", label: "Speedtest" },
  { to: "/security", label: "Security" },
  { to: "/adblock", label: "Adblock" },
  { to: "/clients", label: "Clients" },
  { to: "/ai", label: "AI" },
];

export default function Layout() {
  const navigate = useNavigate();
  const logout = () => {
    clearToken();
    navigate("/login");
  };
  return (
    <div className="flex h-full">
      <aside className="w-60 bg-slate-900 text-slate-100 flex flex-col">
        <div className="px-4 py-5 text-lg font-semibold border-b border-slate-800">LynkOS</div>
        <nav className="flex-1 p-2 space-y-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm ${
                  isActive ? "bg-slate-700 text-white" : "text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <NavLink
          to="/account"
          className={({ isActive }) =>
            `mx-2 px-3 py-2 rounded text-sm text-left ${
              isActive ? "bg-slate-700 text-white" : "text-slate-300 hover:bg-slate-800"
            }`
          }
        >
          Change password
        </NavLink>
        <button
          onClick={logout}
          className="m-2 px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-800 text-left"
        >
          Log out
        </button>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
