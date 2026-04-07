import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import PortfolioPage from "@/pages/PortfolioPage";
import TestValidationPage from "@/pages/TestValidationPage";
import LeaderboardPage from "@/pages/LeaderboardPage";
import BotConfigPage from "@/pages/BotConfigPage";
import LiveDashboardPage from "@/pages/LiveDashboardPage";
import TradeHistoryPage from "@/pages/TradeHistoryPage";
import AlertSettingsPage from "@/pages/AlertSettingsPage";
import AnalyzeBotPage from "@/pages/AnalyzeBotPage";
import DiscoveryPage from "@/pages/DiscoveryPage";
import StrategyLibraryPage from "@/pages/StrategyLibraryPage";
import MarketDataPage from "@/pages/MarketDataPage";
import PipelinePage from "@/pages/PipelinePage";

function PortfolioPageWrapper() {
  const navigate = useNavigate();
  return <PortfolioPage onBack={() => navigate('/')} />;
}

function App() {
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  return (
    <div className="App min-h-screen overflow-y-auto">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/portfolio" element={<PortfolioPageWrapper />} />
          <Route path="/test/validation" element={<TestValidationPage />} />
          <Route path="/leaderboard" element={<LeaderboardPage />} />
          <Route path="/bot-config" element={<BotConfigPage />} />
          <Route path="/live" element={<LiveDashboardPage />} />
          <Route path="/trade-history" element={<TradeHistoryPage />} />
          <Route path="/settings/alerts" element={<AlertSettingsPage />} />
          <Route path="/analyze-bot" element={<AnalyzeBotPage />} />
          <Route path="/discovery" element={<DiscoveryPage />} />
          <Route path="/library" element={<StrategyLibraryPage />} />
          <Route path="/market-data" element={<MarketDataPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
