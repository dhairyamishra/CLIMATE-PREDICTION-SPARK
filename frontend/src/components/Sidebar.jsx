import React, { useEffect, useState } from 'react'
import { X } from 'lucide-react'

export default function Sidebar({ children, onClose, isOpen = true }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    requestAnimationFrame(() => setMounted(true))
    return () => setMounted(false)
  }, [])

  return (
    <>
      {/* Mobile overlay */}
      <div
        className={`fixed inset-0 bg-black/50 z-30 lg:hidden transition-opacity duration-200 ${
          mounted ? 'opacity-100' : 'opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className={`
          fixed inset-y-14 left-0 z-30
          lg:relative lg:inset-auto lg:z-auto
          w-[85vw] sm:w-[400px]
          bg-card border-r border-border flex flex-col shrink-0 overflow-hidden
          transition-transform duration-200 ease-out
          ${mounted ? 'translate-x-0' : '-translate-x-full'}
        `}
        role="complementary"
        aria-label="Station details panel"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-sm font-medium text-muted-foreground">Details</span>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-secondary transition-colors"
            aria-label="Close panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto overscroll-contain">
          {children}
        </div>
      </aside>
    </>
  )
}
