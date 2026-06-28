export const colors = {
  armyGreen: "#3f4f24",
  deepOlive: "#263315",
  khaki: "#c2b280",
  sand: "#efe6c8",
  commandRed: "#8b1e1e",
  warning: "#d99a00",
  success: "#1f6b3a",
  fail: "#b3261e",
  surfaceLight: "#f7f1dc",
  surfaceDark: "#1e2614",
} as const;

export const resultStyles: Record<string, { bg: string; text: string; border: string }> = {
  pass: { bg: "bg-[#1f6b3a]", text: "text-white", border: "border-[#1f6b3a]" },
  needs_correction: { bg: "bg-[#d99a00]", text: "text-[#171717]", border: "border-[#d99a00]" },
  fail: { bg: "bg-[#8b1e1e]", text: "text-white", border: "border-[#8b1e1e]" },
};

export const checkStatusIcon: Record<string, string> = {
  pass: "✓",
  warning: "⚠",
  fail: "✕",
};
