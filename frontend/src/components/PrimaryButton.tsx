type Props = {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "danger" | "secondary" | "command";
  className?: string;
  type?: "button" | "submit";
};

const VARIANTS = {
  primary: "bg-[var(--color-army-green)] hover:bg-[var(--color-deep-olive)] text-white disabled:opacity-50",
  command: "bg-[var(--color-deep-olive)] hover:bg-black text-[var(--color-sand)] border-2 border-[var(--color-khaki)] disabled:opacity-50",
  danger: "bg-[var(--color-command-red)] hover:bg-[#6d1616] text-white disabled:opacity-50",
  secondary: "bg-[var(--color-sand)] hover:bg-[var(--color-khaki)] text-[var(--color-deep-olive)] disabled:opacity-50",
};

export function PrimaryButton({
  children,
  onClick,
  disabled,
  variant = "primary",
  className = "",
  type = "button",
}: Props) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`min-h-[4rem] w-full rounded-xl px-6 py-4 text-lg font-bold transition disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
