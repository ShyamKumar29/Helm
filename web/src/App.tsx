import { Route, Routes } from 'react-router-dom';
import { AboutPage } from './pages/AboutPage';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { LandingPage } from './pages/LandingPage';
import { ReplayPage } from './pages/ReplayPage';
import { SimDataProvider } from './state/SimDataProvider';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      {/* One provider instance for all three dashboard routes, mounted above the router so
          switching Live/History/About tabs never tears down the live state, the WS
          connection, or refetches from zero — see state/SimDataProvider.tsx. */}
      <Route
        path="/dashboard/*"
        element={
          <SimDataProvider>
            <Routes>
              <Route index element={<DashboardPage />} />
              <Route path="replay" element={<ReplayPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="about" element={<AboutPage />} />
            </Routes>
          </SimDataProvider>
        }
      />
    </Routes>
  );
}

export default App;
