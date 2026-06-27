import { Link } from "react-router-dom";

type Props = {
  title: string;
  children: React.ReactNode;
  backTo?: string;
};

export function PageLayout({ title, children, backTo }: Props) {
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white px-4 py-4 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-4">
          {backTo && (
            <Link to={backTo} className="text-blue-700 font-semibold">
              ← Back
            </Link>
          )}
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
