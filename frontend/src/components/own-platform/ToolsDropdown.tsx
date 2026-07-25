"use client";

import { Globe, BookOpen, Terminal, BarChart3 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";

const TOOLS = [
  { id: "web", label: "Web Search", desc: "Search the internet for real-time info", icon: <Globe size={16} />, color: "text-sky-400" },
  { id: "kb", label: "Knowledge Base", desc: "Query uploaded documents", icon: <BookOpen size={16} />, color: "text-blue-400" },
  { id: "code", label: "Code Exec", desc: "Run Python code snippets", icon: <Terminal size={16} />, color: "text-green-400" },
  { id: "data", label: "Data Analysis", desc: "Analyze datasets and metrics", icon: <BarChart3 size={16} />, color: "text-purple-400" },
];

interface ToolsDropdownProps {
  activeTools: Record<string, boolean>;
  onToggle: (id: string, now: boolean) => void;
}

export function ToolsDropdown({ activeTools, onToggle }: ToolsDropdownProps) {
  const hasActive = Object.values(activeTools).some(Boolean);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className={`h-9 px-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all ${hasActive ? 'text-primary border border-primary/20 bg-primary/5' : ''}`}
        >
          <div className="flex items-center gap-1.5">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
            </svg>
          </div>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        className="bg-popover w-[320px] rounded-xl border p-2 shadow-xl"
        align="end"
        side="top"
        sideOffset={8}
      >
        <DropdownMenuLabel className="px-2 pb-1 text-sm font-semibold text-foreground">
          Available Tools
        </DropdownMenuLabel>
        <p className="px-2 pb-2 text-caption text-muted-foreground border-b border-border mb-1">
          Toggle tools ON to activate them in chat
        </p>

        <DropdownMenuGroup>
          {TOOLS.map((tool) => (
            <DropdownMenuItem
              key={tool.id}
              onSelect={(e) => e.preventDefault()}
              className="group hover:bg-accent/50! flex cursor-pointer items-center gap-3 rounded-lg p-2.5"
            >
              <div className={`${tool.color} shrink-0`}>
                {tool.icon}
              </div>
              <div className="flex flex-1 flex-col min-w-0">
                <span className="text-small font-medium text-foreground">{tool.label}</span>
                <span className="text-caption text-muted-foreground truncate">{tool.desc}</span>
              </div>
              <Switch
                checked={!!activeTools[tool.id]}
                onCheckedChange={() => onToggle(tool.id)}
              />
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
