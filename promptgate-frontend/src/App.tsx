import { NavLink, Route, Routes } from "react-router-dom";
import { RunsDashboard } from "./pages/RunsDashboard";
import { PromptDetail } from "./pages/PromptDetail";
import { LocaleBreakdown } from "./pages/LocaleBreakdown";

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      style={({ isActive }) => ({
        padding: "0.25rem 0.75rem",
        borderRadius: "0.375rem",
        fontSize: "0.875rem",
        fontWeight: 500,
        textDecoration: "none",
        color: isActive ? "var(--color-text-success)" : "var(--color-text-secondary)",
        background: isActive ? "var(--color-background-success)" : "transparent",
      })}
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div style={{ maxWidth: "72rem", margin: "0 auto", padding: "1.5rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <div
          style={{
            borderLeft: "3px solid var(--color-border-info)",
            paddingLeft: "0.875rem",
            marginBottom: "1rem",
          }}
        >
          <h1 style={{ fontSize: "1.5rem", fontWeight: 500, margin: "0 0 0.25rem" }}>
            PromptGate
          </h1>
          <p style={{ fontSize: "0.875rem", margin: 0, color: "var(--color-text-secondary)" }}>
            Is this output{" "}
            <span style={{ color: "var(--color-text-success)", fontWeight: 500 }}>safe</span>
            {" "}and{" "}
            <span style={{ color: "var(--color-text-info)", fontWeight: 500 }}>correct</span>
            {" "}to ship?
          </p>
        </div>
        <nav style={{ display: "flex", gap: "0.5rem" }}>
          <NavItem to="/">Runs</NavItem>
          <NavItem to="/prompts">Prompt Trends</NavItem>
          <NavItem to="/locale">Locale Breakdown</NavItem>
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<RunsDashboard />} />
          <Route path="/prompts" element={<PromptDetail />} />
          <Route path="/locale" element={<LocaleBreakdown />} />
        </Routes>
      </main>
    </div>
  );
}
