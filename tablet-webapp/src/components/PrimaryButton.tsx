type Props = {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "danger" | "secondary";
  className?: string;
  type?: "button" | "submit";
};

const VARIANTS = {
  primary: "bg-blue-700 hover:bg-blue-800 text-white disabled:bg-blue-300",
  danger: "bg-red-600 hover:bg-red-700 text-white disabled:bg-red-300",
  secondary: "bg-slate-200 hover:bg-slate-300 text-slate-900 disabled:bg-slate-100",
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
      className={`min-h-14 w-full rounded-xl px-6 py-4 text-lg font-semibold transition disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
