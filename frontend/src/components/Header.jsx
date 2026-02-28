import React from 'react'
import { Globe, PanelLeftClose, PanelLeft, LayoutDashboard, Thermometer } from 'lucide-react'

export default function Header({ onToggleSidebar, onToggleDashboard, showDashboard }) {
  return (
    <header className="h-14 bg-card border-b border-border flex items-center justify-between px-4 shrink-0 z-20" role="banner">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-md hover:bg-secondary transition-colors"
          aria-label="Toggle details panel"
        >
          <PanelLeft className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2">
          <Globe className="w-6 h-6 text-primary" aria-hidden="true" />
          <h1 className="text-lg font-semibold tracking-tight">
            Climate Anomaly Engine
          </h1>
        </div>
      </div>

      <nav className="flex items-center gap-2" aria-label="Main navigation">
        <button
          onClick={onToggleDashboard}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            showDashboard
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-secondary text-muted-foreground hover:text-foreground'
          }`}
          aria-pressed={showDashboard}
          aria-label="Toggle global dashboard"
        >
          <LayoutDashboard className="w-4 h-4" aria-hidden="true" />
          <span className="hidden sm:inline">Dashboard</span>
        </button>

        <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground" aria-label="Dataset info">
          <Thermometer className="w-4 h-4" aria-hidden="true" />
          <span>100+ Years · 500 Stations</span>
        </div>
      </nav>
    </header>
  )
}
