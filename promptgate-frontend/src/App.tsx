import { RunsTable } from "./components/RunsTable";
import { ScoreTrendChart } from "./components/ScoreTrendChart";

function App() {
  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900">PromptGate</h1>
        <p className="text-gray-500 text-sm">
          Is this output safe and correct to ship?
        </p>
      </header>

      <section className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Judge score trend</h2>
        <ScoreTrendChart />
      </section>

      <section className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Recent runs</h2>
        <RunsTable />
      </section>
    </div>
  );
}

export default App;
