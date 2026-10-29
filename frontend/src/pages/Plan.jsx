import { useState } from 'react';
import { api } from '../api';
import SessionCard from '../SessionCard';
import { Btn, Card, Empty, ErrorBox, PageTitle, Spinner, addDays, fmtDate, inputCls, isoDate, useLoad } from '../ui';
export default function Plan() {
    const [horizon, setHorizon] = useState(7);
    const [generating, setGenerating] = useState(false);
    const [msg, setMsg] = useState('');
    const [err, setErr] = useState('');
    const start = isoDate(new Date());
    const end = isoDate(addDays(new Date(), 13));
    const plan = useLoad(() => api.plan(start, end), [start, end]);
    const topics = useLoad(async () => {
        const subs = await api.subjects();
        const details = await Promise.all(subs.map(s => api.subject(s.id)));
        return details.flatMap(d => d.topics.map(t => ({ ...t, subject: d.name })));
    }, []);
    const [topicId, setTopicId] = useState('');
    const [date, setDate] = useState(start);
    const [mins, setMins] = useState(30);
    const generate = async () => {
        setGenerating(true);
        setErr('');
        setMsg('');
        try {
            const r = await api.generatePlan(horizon);
            setMsg(`Plan generated with ${r.length} sessions.`);
        }
        catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed');
        }
        setGenerating(false);
    };
    const add = async (e) => {
        e.preventDefault();
        setErr('');
        try {
            await api.addSession(Number(topicId), date, mins);
            await plan.reload();
        }
        catch (x) {
            setErr(x instanceof Error ? x.message : 'Failed');
        }
    };
    const byDate = new Map();
    for (const s of plan.data ?? [])
        byDate.set(s.scheduled_date, [...(byDate.get(s.scheduled_date) ?? []), s]);
    return (<>
      <PageTitle title="Revision plan" sub="Priorities combine the model's estimate with exam dates, recency and missed sessions."/>
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">Plan for
            <select className={`${inputCls} mt-1`} value={horizon} onChange={e => setHorizon(Number(e.target.value))}>
              {[3, 7, 14].map(n => <option key={n} value={n}>{n} days</option>)}
            </select>
          </label>
          <Btn disabled={generating} onClick={generate}>{generating ? 'Generating…' : 'Generate / update plan'}</Btn>
        </div>
        {msg && <p className="mt-3 text-sm text-emerald-700">{msg}</p>}
        {err && <div className="mt-3"><ErrorBox message={err}/></div>}
      </Card>

      {plan.loading ? <Spinner /> : plan.error ? <ErrorBox message={plan.error}/> : byDate.size === 0 ? (<Empty>No sessions yet. Click "Generate / update plan".</Empty>) : (<div className="space-y-5">
          {[...byDate.entries()].map(([d, list]) => (<div key={d}>
              <h2 className="mb-2 text-sm font-semibold text-slate-700">{fmtDate(d)} · {(list ?? []).reduce((a, s) => a + s.duration_minutes, 0)} min</h2>
              <div className="space-y-3">
                {(list ?? []).map(s => <SessionCard key={s.id} s={s} allowDelete onChanged={() => void plan.reload()}/>)}
              </div>
            </div>))}
        </div>)}

      <Card title="Add a session manually" className="mt-6">
        <form onSubmit={add} className="flex flex-wrap items-end gap-3">
          <label className="min-w-48 flex-1 text-sm">Topic
            <select required className={`${inputCls} mt-1`} value={topicId} onChange={e => setTopicId(e.target.value)}>
              <option value="">Choose…</option>
              {(topics.data ?? []).map(t => <option key={t.id} value={t.id}>{t.subject} – {t.name}</option>)}
            </select>
          </label>
          <label className="text-sm">Date
            <input type="date" min={start} className={`${inputCls} mt-1`} value={date} onChange={e => setDate(e.target.value)} required/>
          </label>
          <label className="text-sm">Minutes
            <input type="number" min={10} max={240} className={`${inputCls} mt-1 !w-24`} value={mins} onChange={e => setMins(Number(e.target.value))}/>
          </label>
          <Btn type="submit">Add</Btn>
        </form>
      </Card>
    </>);
}
