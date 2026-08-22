"use client";

import { Plus } from "lucide-react";

interface Button9Props {
  onClick?: () => void;
  children?: React.ReactNode;
}

const Button9 = ({ onClick, children }: Button9Props) => {
  return (
    <button
      onClick={onClick}
      className="w-full inline-flex items-center justify-center gap-2.5 px-4 py-3 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/25 hover:from-primary/25 hover:to-primary/10 transition-all active:scale-[0.98] text-primary font-semibold text-small"
    >
      <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center">
        <Plus size={16} className="text-primary" />
      </div>
      <span>{children || "New Chat"}</span>
    </button>
  );
};

export default Button9;
