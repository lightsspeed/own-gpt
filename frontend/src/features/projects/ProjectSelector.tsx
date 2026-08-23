import { useState, useRef, useEffect, useCallback } from 'react'
import { Folder, FolderGit2, Check, ChevronDown, Loader, AlertTriangle, Plus, X, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Project } from './services/projectsApi'

interface ProjectSelectorProps {
  projects: Project[]
  selectedProjectId: string | null
  loading?: boolean
  error?: string | null
  onSelect: (projectId: string | null) => void
  onCreate: (name: string) => Promise<Project>
  onRetry?: () => void
}

export function ProjectSelector({
  projects,
  selectedProjectId,
  loading = false,
  error = null,
  onSelect,
  onCreate,
  onRetry,
}: ProjectSelectorProps) {
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [nameInputOpen, setNameInputOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selected = projects.find(p => p.id === selectedProjectId) ?? null

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [open])

  const handleCreate = useCallback(async () => {
    const name = newName.trim()
    if (!name || creating) return
    setCreating(true)
    setCreateError(null)
    try {
      const project = await onCreate(name)
      setNewName('')
      setNameInputOpen(false)
      setOpen(false)
      onSelect(project.id)
    } catch (e: any) {
      setCreateError(e?.message || 'Failed to create project')
    } finally {
      setCreating(false)
    }
  }, [newName, creating, onCreate, onSelect])

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        onClick={() => setOpen(v => !v)}
        className={cn(
          'w-full flex items-center justify-between gap-2.5 px-3 py-2 rounded-xl border text-small transition-all shadow-xs',
          open
            ? 'border-primary/40 bg-primary/10 text-foreground ring-1 ring-primary/20'
            : 'border-border/60 bg-background/40 text-foreground/80 hover:text-foreground hover:bg-background/60 hover:border-border',
        )}
        title="Select active workspace project"
      >
        <span className="flex items-center gap-2.5 min-w-0">
          <div className="w-5 h-5 rounded-md bg-primary/15 border border-primary/25 flex items-center justify-center text-primary shrink-0">
            <FolderGit2 size={12} />
          </div>
          <span className="truncate font-medium text-xs max-w-[170px]">{selected ? selected.name : 'General (All Content)'}</span>
        </span>
        <ChevronDown size={14} className={cn('shrink-0 text-muted-foreground/60 transition-transform duration-200', open && 'rotate-180 text-primary')} />
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-2 z-50 rounded-xl border border-border/60 bg-popover shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-1">
          <div className="px-3 pt-2.5 pb-1.5 text-caption text-muted-foreground/60">Project</div>

          {loading && (
            <div className="flex items-center gap-2 px-3 py-2 text-small text-muted-foreground">
              <Loader size={13} className="animate-spin" /> Loading projects…
            </div>
          )}

          {!loading && error && (
            <div className="flex items-center gap-2 px-3 py-2 text-small text-danger">
              <AlertTriangle size={13} />
              <span className="flex-1 min-w-0 truncate">{error}</span>
              {onRetry && (
                <button onClick={onRetry} className="text-caption text-foreground underline shrink-0">Retry</button>
              )}
            </div>
          )}

          {!loading && !error && (
            <>
              <button
                onClick={() => { onSelect(null); setOpen(false) }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-small text-left transition-colors hover:bg-hover',
                  !selectedProjectId ? 'text-foreground' : 'text-muted-foreground',
                )}
              >
                <Folder size={14} className="text-muted-foreground/40" />
                <span className="flex-1">General (all content)</span>
                {!selectedProjectId && <Check size={14} className="text-primary" />}
              </button>

              {projects.map(p => (
                <button
                  key={p.id}
                  onClick={() => { onSelect(p.id); setOpen(false) }}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 text-small text-left transition-colors hover:bg-hover',
                    selectedProjectId === p.id ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  <Folder size={14} className="text-primary/70" />
                  <span className="flex-1 truncate">{p.name}</span>
                  {selectedProjectId === p.id && <Check size={14} className="text-primary" />}
                </button>
              ))}

              {projects.length === 0 && (
                <div className="px-3 py-2 text-caption text-muted-foreground/60">
                  No projects yet — create one to scope chats, documents and memory.
                </div>
              )}
            </>
          )}

          <div className="border-t border-border/60 p-2 space-y-1.5">
            {creating ? (
              <div className="flex items-center gap-2 px-2 py-1.5 text-small text-muted-foreground">
                <Loader size={13} className="animate-spin" /> Creating project…
              </div>
            ) : nameInputOpen ? (
              <form
                onSubmit={e => { e.preventDefault(); void handleCreate() }}
                className="flex items-center gap-1.5"
              >
                <input
                  autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  placeholder="Project name"
                  className="flex-1 min-w-0 rounded-lg bg-background/40 border border-border/60 px-2 py-1.5 text-small text-foreground placeholder:text-muted-foreground/30 outline-none focus:border-primary/40"
                />
                <button
                  type="submit"
                  disabled={!newName.trim()}
                  className="px-2 py-1.5 rounded-lg bg-primary text-primary-foreground text-caption font-medium disabled:opacity-40 shrink-0"
                >
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => { setNameInputOpen(false); setNewName(''); setCreateError(null) }}
                  className="p-1.5 rounded-lg text-muted-foreground/50 hover:text-foreground hover:bg-hover shrink-0"
                  title="Cancel"
                >
                  <X size={12} />
                </button>
              </form>
            ) : (
              <button
                onClick={() => { setCreateError(null); setNewName(''); setNameInputOpen(true) }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-small text-sky-400 hover:bg-sky-400/10 transition-all"
              >
                <Plus size={13} /> New Project
              </button>
            )}
            {createError && (
              <div className="flex items-center gap-1.5 px-2 text-caption text-danger">
                <AlertTriangle size={11} className="shrink-0" />
                <span className="truncate">{createError}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}