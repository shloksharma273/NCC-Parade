import { Link } from "react-router-dom";

type Props = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  backTo?: string;
  strip?: string;
};

export function PageLayout({ title, subtitle, children, backTo, strip }: Props) {
  return (
    <div className="min-h-screen bg-[var(--color-surface-light)]">
      <header className="command-header px-4 py-5 shadow-md">
        <div className="mx-auto flex max-w-5xl items-center gap-4">
          {backTo && (
            <Link to={backTo} className="font-semibold text-[var(--color-sand)] hover:text-white">
              ← Back
            </Link>
          )}
          <div>
            {strip && <div className="rank-strip inline-block mb-1">{strip}</div>}
            <h1 className="font-command text-3xl font-bold text-white">{title}</h1>
            {subtitle && <p className="text-sm text-[var(--color-sand)]">{subtitle}</p>}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
