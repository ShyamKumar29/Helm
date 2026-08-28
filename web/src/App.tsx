import { Route, Routes } from 'react-router-dom';
import { AboutPage } from './pages/AboutPage';
import { DashboardPage } from './pages/DashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { LandingPage } from './pages/LandingPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/dashboard/history" element={<HistoryPage />} />
      <Route path="/dashboard/about" element={<AboutPage />} />
    </Routes>
  );
}

export default App;
