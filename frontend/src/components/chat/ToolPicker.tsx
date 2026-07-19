import React, { useState, useRef, useEffect } from 'react';
import {
  Paperclip, Globe, BookOpen, Microscope, Image,
  Zap, FileText, Blocks, ChevronRight, Search
} from 'lucide-react';
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

export interface ToolAction {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  iconBg: string;
  badge?: 'Connect' | 'Beta';
  onClick: () => void;
}

interface ToolPickerProps {
  open: boolean;
  onClose: () => void;
  onFileUploadClick: () => void;
  onToolSelect: (toolId: string) => void;
  activeTools: string[];
}

const TOOL_SECTIONS = [
  {
    title: null,
    tools: [
      {
        id: 'upload',
        label: 'Add photos & files',
        description: 'Upload from computer',
        icon: <Paperclip size={16} />,
        iconBg: 'bg-zinc-600',
      },
    ],
  },
  {
    title: null,
    tools: [
      {
        id: 'search_web',
        label: 'Web search',
        description: 'Find real-time news and info',
        icon: <Globe size={16} />,
        iconBg: 'bg-blue-600',
      },
      {
        id: 'search_knowledge_base',
        label: 'Knowledge Base',
        description: 'Query your uploaded documents',
        icon: <BookOpen size={16} />,
        iconBg: 'bg-purple-600',
      },
      {
        id: 'deep_research',
        label: 'Deep research',
        description: 'Get a detailed multi-step report',
        icon: <Microscope size={16} />,
        iconBg: 'bg-teal-600',
        badge: 'Beta' as const,
      },
      {
        id: 'create_image',
        label: 'Create image',
        description: 'Visualize anything with DALL-E',
        icon: <Image size={16} />,
        iconBg: 'bg-green-700',
      },
      {
        id: 'sm_integration',
        label: 'Social Media',
        description: 'Post, read or analyze social content',
        icon: <Zap size={16} />,
        iconBg: 'bg-yellow-600',
      },
    ],
  },
  {
    title: 'Integrations',
    tools: [
      {
        id: 'atlassian',
        label: 'Atlassian (Jira/Confluence)',
        description: 'Manage tasks and docs',
        icon: <Blocks size={16} />,
        iconBg: 'bg-blue-700',
        badge: 'Connect' as const,
      },
      {
        id: 'notion',
        label: 'Notion',
        description: 'Search and reference your pages',
        icon: <FileText size={16} />,
        iconBg: 'bg-zinc-700',
        badge: 'Connect' as const,
      },
    ],
  },
];

export function ToolPicker({ open, onClose, onFileUploadClick, onToolSelect, activeTools }: ToolPickerProps) {
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) setSearch('');
  }, [open]);

  if (!open) return null;

  const filteredSections = TOOL_SECTIONS.map(section => ({
    ...section,
    tools: section.tools.filter(
      t =>
        t.label.toLowerCase().includes(search.toLowerCase()) ||
        t.description.toLowerCase().includes(search.toLowerCase())
    ),
  })).filter(s => s.tools.length > 0);

  const handleTool = (id: string) => {
    if (id === 'upload') {
      onFileUploadClick();
    } else {
      onToolSelect(id);
    }
    onClose();
  };

  return (
    <div
      ref={ref}
      className="absolute bottom-full mb-2 left-0 w-80 rounded-2xl border border-white/10 bg-zinc-900/95 backdrop-blur-xl shadow-2xl z-50 overflow-hidden animate-in slide-in-from-bottom-2 fade-in duration-200"
    >
      {/* Search */}
      <div className="p-2 border-b border-white/5">
        <div className="flex items-center gap-2 bg-zinc-800/70 rounded-xl px-3 py-2">
          <Search size={13} className="text-muted-foreground flex-shrink-0" />
          <input
            autoFocus
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search plugins, files, folders & skills"
            className="bg-transparent text-xs w-full outline-none text-foreground placeholder:text-muted-foreground"
          />
        </div>
      </div>

      {/* Tool list */}
      <div className="py-1 max-h-80 overflow-y-auto">
        {filteredSections.map((section, si) => (
          <div key={si}>
            {section.title && (
              <p className="text-xs text-muted-foreground px-3 pt-3 pb-1 uppercase tracking-wider font-semibold">
                {section.title}
              </p>
            )}
            {section.tools.map(tool => {
              const isActive = activeTools.includes(tool.id);
              return (
                <button
                  key={tool.id}
                  onClick={() => handleTool(tool.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 transition-colors text-left group ${isActive ? 'bg-primary/10' : ''}`}
                >
                  {/* Icon */}
                  <div className={`w-8 h-8 rounded-lg ${tool.iconBg} flex items-center justify-center flex-shrink-0 text-white`}>
                    {tool.icon}
                  </div>
                  {/* Text */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{tool.label}</span>
                      {tool.badge && (
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium
                          ${tool.badge === 'Connect'
                            ? 'text-muted-foreground border border-border'
                            : 'bg-primary/20 text-primary border border-primary/30'}`}>
                          {tool.badge}
                        </span>
                      )}
                      {isActive && (
                        <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-1.5 py-0.5 rounded">Active</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{tool.description}</p>
                  </div>
                  <ChevronRight size={14} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
