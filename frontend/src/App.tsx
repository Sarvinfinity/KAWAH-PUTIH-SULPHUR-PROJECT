import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './components/Dashboard';

function App() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="app-container">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="main-content">
        <Dashboard activeTab={activeTab} />
      </main>
    </div>
  );
}

export default App;
