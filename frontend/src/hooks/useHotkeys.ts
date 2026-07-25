import { useEffect } from 'react'

interface HotkeyDef {
  key: string
  handler: () => void
  deps?: unknown[]
}

export function useHotkeys(hotkeys: HotkeyDef[]) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      for (const h of hotkeys) {
        if (e.key === h.key && !e.metaKey && !e.ctrlKey && !e.altKey) {
          e.preventDefault()
          h.handler()
          return
        }
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotkeys])
}
