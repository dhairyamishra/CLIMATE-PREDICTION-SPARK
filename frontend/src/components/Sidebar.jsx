import React from 'react'
import { X } from 'lucide-react'

export default function Sidebar({ children, onClose }) {
  return (
    <aside className="w-[400px] bg-card border-r border-border flex flex-col shrink-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-medium text-muted-foreground">Details</span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-secondary transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </aside>
  )
}
