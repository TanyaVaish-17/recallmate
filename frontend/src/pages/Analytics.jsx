import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import { Card, Empty, ErrorBox, PageTitle, Spinner, addDays, isoDate, useLoad } from '../ui';
export default function Analytics() {
    const data = useLoad(async () => {
        const [quizzes, subjects, preds, plan] = await Promise.all([
            api.quizzes(100), api.subjects(), api.predictions(),
            api.plan(isoDate(addDays(new Date(), -13)), isoDate(new Date())),
        ]);
        const details = await Promise.all(subjects.map(s => api.subject(s.id)));
        const topicSubject = new Map();
        details.forEach(d => d.topics.forEach(t => topicSubject.set(t.id, { name: d.name, color: d.color })));
        const recent = await Promise.all(quizzes.slice(0, 25).map(q => api.quiz(q.id)));
        const per = new Map();
        for (const q of recent)
            for (const r of q.responses) {
                const s = topicSubject.get(r.topic_id);
                if (!s)
                    continue;
                const cur = per.get(s.name) ?? { correct: 0, total: 0, color: s.color };
                cur.total += 1;
                cur.correct += r.is_correct ? 1 : 0;
                per.set(s.name, cur);
            }
        return { quizzes, preds, plan, per };
    }, []);
    if (data.loading)
        return <Spinner />;
    if (data.error)
        return <ErrorBox message={data.error}/>;
    const { quizzes, preds, plan, per } = data.data;
    const scores = [...quizzes].reverse().map((q, i) => ({ n: i + 1, percent: q.percent }));
    const subjectBars = [...per.entries()].map(([name, v]) => ({ name, percent: Math.round((v.correct / v.total) * 100), color: v.color }));
    const topicBars = preds.topics.filter(t => t.probability !== null)
        .map(t => ({ name: t.topic_name, percent: Math.round((t.probability ?? 0) * 100), color: t.subject_color }))
        .sort((a, b) => a.percent - b.percent);
    const counts = ['completed', 'pending', 'missed', 'skipped'].map(st => ({ name: st, count: plan.filter(s => s.status === st).length }));
    return (<>
      <PageTitle title="Analytics" sub="Everything here is computed from your own recorded activity."/>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Quiz scores over time">
          {scores.length === 0 ? <Empty>No quiz attempts yet.</Empty> : (<div className="h-60"><ResponsiveContainer><LineChart data={scores}>
              <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="n" label={{ value: 'attempt', position: 'insideBottom', offset: -2 }}/><YAxis domain={[0, 100]}/><Tooltip />
              <Line type="monotone" dataKey="percent" stroke="#4f46e5" strokeWidth={2} dot/>
            </LineChart></ResponsiveContainer></div>)}
        </Card>
        <Card title="Subject-wise accuracy (last 25 quizzes)">
          {subjectBars.length === 0 ? <Empty>No answers recorded yet.</Empty> : (<div className="h-60"><ResponsiveContainer><BarChart data={subjectBars}>
              <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis domain={[0, 100]}/><Tooltip />
              <Bar dataKey="percent">{subjectBars.map(b => <Cell key={b.name} fill={b.color}/>)}</Bar>
            </BarChart></ResponsiveContainer></div>)}
        </Card>
        <Card title="Topics needing practice (model estimate, %)">
          {topicBars.length === 0 ? <Empty>No model estimates yet. Take quizzes first{preds.model.trained ? '.' : ' (and train the model).'}</Empty> : (<div className="h-60"><ResponsiveContainer><BarChart data={topicBars} layout="vertical">
              <CartesianGrid strokeDasharray="3 3"/><XAxis type="number" domain={[0, 100]}/><YAxis type="category" dataKey="name" width={110}/><Tooltip />
              <Bar dataKey="percent">{topicBars.map(b => <Cell key={b.name} fill={b.color}/>)}</Bar>
            </BarChart></ResponsiveContainer></div>)}
        </Card>
        <Card title="Revision sessions, last 14 days">
          {plan.length === 0 ? <Empty>No sessions in the last 14 days.</Empty> : (<div className="h-60"><ResponsiveContainer><BarChart data={counts}>
              <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip />
              <Bar dataKey="count" fill="#4f46e5"/>
            </BarChart></ResponsiveContainer></div>)}
        </Card>
      </div>
      <p className="mt-4 text-xs text-slate-500">Predicted-vs-actual charts are intentionally omitted until there are enough real observations to compare.</p>
    </>);
}
