import React from 'react'

export function Skeleton({ className = '', ...props }) {
  return (
    <div
      className={`animate-pulse rounded bg-secondary/60 ${className}`}
      {...props}
    />
  )
}

export function MapLoadingSkeleton() {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-muted-foreground">Loading map data...</p>
      </div>
    </div>
  )
}

export function StationPanelSkeleton() {
  return (
    <div className="p-4 space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-3 w-32" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-lg" />
        ))}
      </div>
      <div className="flex gap-1">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-8 flex-1 rounded" />
        ))}
      </div>
      <Skeleton className="h-48 rounded-lg" />
      <Skeleton className="h-32 rounded-lg" />
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="p-4 space-y-4">
      <Skeleton className="h-6 w-40" />
      <div className="grid grid-cols-2 gap-2">
        {[...Array(6)].map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-44 rounded-lg" />
      <Skeleton className="h-48 rounded-lg" />
    </div>
  )
}
