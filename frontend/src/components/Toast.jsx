import React, { useState, useEffect, useCallback, createContext, useContext } from 'react'
import { X, AlertTriangle, CheckCircle2, Info, AlertCircle } from 'lucide-react'

const ToastContext = createContext(null)

const ICONS = {
  success: CheckCircle2,
  error: AlertTriangle,
  warning: AlertCircle,
  info: Info,
}

const COLORS = {
  success: 'border-green-500/40 bg-green-500/10 text-green-400',
  error: 'border-destructive/40 bg-destructive/10 text-red-400',
  warning: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400',
  info: 'border-primary/40 bg-primary/10 text-blue-400',
}

function ToastItem({ id, type = 'info', title, message, onDismiss }) {
  const Icon = ICONS[type] || ICONS.info
  const color = COLORS[type] || COLORS.info

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(id), 5000)
    return () => clearTimeout(timer)
  }, [id, onDismiss])

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-xl backdrop-blur-sm animate-slide-in ${color}`}
      role="alert"
    >
      <Icon className="w-5 h-5 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        {title && <p className="text-sm font-medium">{title}</p>}
        {message && <p className="text-xs opacity-80 mt-0.5">{message}</p>}
      </div>
      <button
        onClick={() => onDismiss(id)}
        className="p-0.5 rounded hover:bg-white/10 transition-colors shrink-0"
        aria-label="Dismiss notification"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((toast) => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev.slice(-4), { ...toast, id }])
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80 pointer-events-none">
        {toasts.map(toast => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem {...toast} onDismiss={dismissToast} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const addToast = useContext(ToastContext)
  if (!addToast) throw new Error('useToast must be used within ToastProvider')
  return addToast
}
