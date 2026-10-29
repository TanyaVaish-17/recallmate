import { useState } from 'react';
import { api } from './api';
import { Btn, ErrorBox, inputCls, isoDate, pct } from './ui';
const BADGE = {
    completed: 'bg-emerald-100 text-emerald-700',
    skipped: 'bg-slate-200 text-slate-600',
    missed: 'bg-red-100 text-red-700',
    pending: 'bg-amber-100 text-amber-700',
};
export default function SessionCard({ s, onChanged, allowDelete = false }) {
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState('');
    const [moving, setMoving] = useState(false);
    const [date, setDate] = useState(s.scheduled_date);
    const closed = s.status === 'completed' || s.status === 'skipped';
    const run = async (fn) => {
        setBusy(true);
        setErr('');
        try {
            await fn();
            setMoving(false);
            onChanged();
        }
        catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed');
        }
        setBusy(false);
    };
    return (<div className="rounded-xl border border-slate-200 bg-white p-4" style={{ borderLeft: `5px solid ${s.subject_color}` }}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-900">{s.topic_name}</p>
          <p className="text-xs text-slate-500">{s.subject_name} · {s.duration_minutes} min · priority {Number(s.priority ?? 0).toFixed(2)}</p>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE[s.status] ?? BADGE.pending}`}>{s.status}</span>
      </div>
      <p className="mt-2 text-sm text-slate-600">{s.reason}</p>
      <p className="mt-1 text-xs text-slate-500">
        {typeof s.predicted_probability === 'number'
            ? `Model estimate of answering correctly: ${pct(s.predicted_probability)} (an estimate, not a measure of memory)`
            : 'No model estimate yet for this topic'}
      </p>
      {err && <div className="mt-2"><ErrorBox message={err}/></div>}
      {!closed && (<div className="mt-3 flex flex-wrap items-center gap-2">
          <Btn disabled={busy} onClick={() => run(() => api.completeSession(s.id))}>Complete</Btn>
          <Btn variant="ghost" disabled={busy} onClick={() => run(() => api.skipSession(s.id))}>Skip</Btn>
          {moving ? (<>
              <input type="date" className={`${inputCls} !w-auto`} min={isoDate(new Date())} value={date} onChange={e => setDate(e.target.value)}/>
              <Btn disabled={busy} onClick={() => run(() => api.rescheduleSession(s.id, date))}>Move</Btn>
              <Btn variant="ghost" onClick={() => setMoving(false)}>Cancel</Btn>
            </>) : (<Btn variant="ghost" disabled={busy} onClick={() => setMoving(true)}>Reschedule</Btn>)}
          {allowDelete && <Btn variant="danger" disabled={busy} onClick={() => run(() => api.deleteSession(s.id))}>Delete</Btn>}
        </div>)}
    </div>);
}
