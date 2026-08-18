import React, { useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Trash2, Cpu, Wrench, BrainCircuit } from 'lucide-react';

interface SettingsProps {
  open: boolean;
  onClose: () => void;
  onClearHistory: () => void;
  settings: AppSettings;
  onSettingsChange: (s: AppSettings) => void;
}

export interface AppSettings {
  model: string;
  temperature: number;
  systemPrompt: string;
}

const DEFAULT_MODEL = import.meta.env.VITE_DEFAULT_MODEL || '';

const MODELS = [
  { id: '', label: 'Gemini 3.6 Flash (Default)', desc: 'Google Gemini 3.6 Flash — active default model' },
  { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash', desc: 'Google Gemini 3.6 Flash — fast & intelligent' },
  { id: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview', desc: 'Google Gemini 3 Flash Preview' },
  { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro', desc: 'Google Gemini 2.5 Pro — high reasoning' },
];

export function SettingsModal({ open, onClose, onClearHistory, settings, onSettingsChange }: SettingsProps) {
  const [localSettings, setLocalSettings] = useState<AppSettings>(settings);

  const handleSave = () => {
    onSettingsChange(localSettings);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-card border border-white/10 text-foreground max-w-2xl shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-2">
            <Cpu size={20} className="text-primary" /> Settings
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Configure the AI assistant's behavior.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="model" className="mt-2">
          <TabsList className="bg-secondary/50 border border-white/5 w-full">
            <TabsTrigger value="model" className="flex-1">Model</TabsTrigger>
            <TabsTrigger value="prompt" className="flex-1">System Prompt</TabsTrigger>
            <TabsTrigger value="danger" className="flex-1 text-destructive">Data</TabsTrigger>
          </TabsList>

          {/* Model Selection */}
          <TabsContent value="model" className="mt-4 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <BrainCircuit size={14} /> LLM Model
              </label>
              <div className="space-y-2">
                {MODELS.map(m => (
                  <div
                    key={m.id}
                    onClick={() => setLocalSettings(s => ({ ...s, model: m.id }))}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      localSettings.model === m.id
                        ? 'border-primary bg-primary/10'
                        : 'border-border hover:border-primary/40 bg-secondary/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{m.label}</span>
                      {localSettings.model === m.id && (
                        <Badge className="bg-primary text-primary-foreground text-xs">Active</Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{m.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            <Separator className="bg-border/40" />

            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Temperature: <span className="text-primary">{localSettings.temperature}</span>
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={localSettings.temperature}
                onChange={e => setLocalSettings(s => ({ ...s, temperature: parseFloat(e.target.value) }))}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0 — Precise</span>
                <span>1 — Balanced</span>
                <span>2 — Creative</span>
              </div>
            </div>
          </TabsContent>

          {/* System Prompt */}
          <TabsContent value="prompt" className="mt-4 space-y-3">
            <label className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <Wrench size={14} /> System Prompt
            </label>
            <textarea
              className="w-full h-48 bg-secondary/30 border border-border rounded-lg p-3 text-sm text-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="You are a helpful AI assistant..."
              value={localSettings.systemPrompt}
              onChange={e => setLocalSettings(s => ({ ...s, systemPrompt: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">
              This prompt is prepended to every conversation. Define the assistant's personality, role, and constraints here.
            </p>
          </TabsContent>

          {/* Danger Zone */}
          <TabsContent value="danger" className="mt-4 space-y-4">
            <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/5 space-y-3">
              <h3 className="font-semibold text-sm text-destructive">Danger Zone</h3>
              <p className="text-xs text-muted-foreground">
                Clearing the conversation will delete all messages in the current session from memory. This cannot be undone.
              </p>
              <Button
                variant="destructive"
                size="sm"
                className="gap-2"
                onClick={() => { onClearHistory(); onClose(); }}
              >
                <Trash2 size={14} /> Clear Conversation History
              </Button>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} className="bg-primary hover:bg-primary/90">Save Changes</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
