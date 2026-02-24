import React from 'react'
import { Globe, PanelLeftClose, PanelLeft, LayoutDashboard, Thermometer } from 'lucide-react'

export default function Header({ onToggleSidebar, onToggleDashboard, showDashboard }) {
  return (
    <header className="h-14 bg-card border-b border-border flex items-center justify-between px-4 shrink-0 z-20">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-md hover:bg-secondary transition-colors"
          title="Toggle sidebar"
        >
          <PanelLeft className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2">
          <Globe className="w-6 h-6 text-primary" />
          <h1 className="text-lg font-semibold tracking-tight">
            Climate Anomaly Engine
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleDashboard}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            showDashboard
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-secondary text-muted-foreground hover:text-foreground'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          Dashboard
        </button>

        <div className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground">
          <Thermometer className="w-4 h-4" />
          <span>100+ Years · 500 Stations</span>
        </div>
      </div>
    </header>
  )
}
