import { useMemo, useState } from "react";
import { Dashboard } from "./pages/Dashboard";
import { Journal } from "./pages/Journal";
import { Portfolio } from "./pages/Portfolio";
import { Recommendations } from "./pages/Recommendations";
import { Watchlist } from "./pages/Watchlist";

type Page = "dashboard" | "watchlist" | "recommendations" | "portfolio" | "journal";

const pages: Array<{ id: Page; label: string }> = [
  { id: "dashboard", label: "Dashboard" },
  { id: "watchlist", label: "Watchlist" },
  { id: "recommendations", label: "Recommendations" },
  { id: "portfolio", label: "Portfolio" },
  { id: "journal", label: "Journal" }
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");

  const content = useMemo(() => {
    if (page === "watchlist") return <Watchlist />;
    if (page === "recommendations") return <Recommendations />;
    if (page === "portfolio") return <Portfolio />;
    if (page === "journal") return <Journal />;
    return <Dashboard onNavigate={setPage} />;
  }, [page]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">TradePilot</p>
          <h1>Research queue</h1>
        </div>
        <nav aria-label="Main navigation">
          {pages.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "nav-active" : ""}
              onClick={() => setPage(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main>{content}</main>
    </div>
  );
}
