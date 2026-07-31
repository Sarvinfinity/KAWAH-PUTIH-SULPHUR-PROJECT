import React from 'react';
import { Activity, BarChart2, ShieldAlert, LayoutDashboard, Settings } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'forecast', label: 'Forecast (24h)', icon: Activity },
    { id: 'thresholds', label: 'Threshold Analysis', icon: ShieldAlert },
    { id: 'classification', label: 'Risk Classification', icon: BarChart2 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      <div style={{ marginBottom: '40px' }}>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '4px', color: '#fff' }}>Kawah Putih</h2>
        <p style={{ fontSize: '0.8rem', color: 'var(--accent-secondary)' }}>Hazard Intelligence</p>
      </div>

      <nav style={{ flex: 1 }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={(e) => {
                e.preventDefault();
                setActiveTab(item.id);
              }}
            >
              <Icon size={18} />
              {item.label}
            </a>
          );
        })}
      </nav>

      <div style={{ marginTop: 'auto', padding: '16px', backgroundColor: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
        <div className="flex-between" style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>System Status</span>
          <span className="badge badge-normal">Online</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Last update: Just now</p>
      </div>
    </aside>
  );
};
