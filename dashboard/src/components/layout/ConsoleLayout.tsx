import Sidebar from "./Sidebar.jsx";
import TopBar from "./TopBar.jsx";

export default function ConsoleLayout({ children }) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      {/* Fixed Sidebar */}
      <aside className="fixed left-0 top-0 z-50 h-screen w-60">
        <Sidebar />
      </aside>

      {/* Scrollable Main Content */}
      <div className="ml-60 flex h-screen flex-1 flex-col overflow-hidden">
        <TopBar />

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}