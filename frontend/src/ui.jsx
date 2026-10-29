import { useCallback, useEffect, useState } from 'react';
export function Card({ title, right, children, className = '' }) {
    return (<section className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {(title || right) && (<div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {right}
        </div>)}
      {children}
    </section>);
}
export function Btn({ variant = 'primary', className = '', ...p }) {
    const styles = {
        primary: 'bg-indigo-600 text-white hover:bg-indigo-700',
        ghost: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
        danger: 'border border-red-200 bg-white text-red-600 hover:bg-red-50',
    }[variant];
    return (<button {...p} className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}/>);
}
export const inputCls = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200';
export function Spinner({ label = 'Loading…' }) {
    return <p className="animate-pulse py-6 text-center text-sm text-slate-500">{label}</p>;
}
export function ErrorBox({ message }) {
    return <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>;
}
export function Empty({ children }) {
    return <p className="rounded-lg bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">{children}</p>;
}
export function PageTitle({ title, sub }) {
    return (<header className="mb-5">
      <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
      {sub && <p className="text-sm text-slate-500">{sub}</p>}
    </header>);
}
export function useLoad(fn, deps = []) {
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const run = useCallback(fn, deps);
    const reload = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            setData(await run());
        }
        catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load');
        }
        setLoading(false);
    }, [run]);
    useEffect(() => {
        void reload();
    }, [reload]);
    return { data, error, loading, reload };
}
export const isoDate = (d) => d.toLocaleDateString('en-CA');
export const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export const fmtDate = (iso) => new Date(iso + (iso.length === 10 ? 'T00:00:00' : '')).toLocaleDateString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
});
export const pct = (v) => `${Math.round(v * 100)}%`;
