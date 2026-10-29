import { Link } from 'react-router-dom';
import { api } from '../api';
import SessionCard from '../SessionCard';
import { Card, Empty, ErrorBox, PageTitle, Spinner, addDays, fmtDate, isoDate, pct, useLoad } from '../ui';
import { useAuth } from '../auth';
function weekStart(d) {
    const x = new Date(d);
    x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); // Monday
    return x;
}
export default function Dashboard() {
    const { user } = useAuth();
    const today = useLoad(() => api.planToday(), []);
    const exams = useLoad(() => api.exams(), []);
    const quizzes = useLoad(() => api.quizzes(5), []);
    const preds = useLoad(() => api.predictions(), []);
    const week = useLoad(() => {
        const s = weekStart(new Date());
        return api.plan(isoDate(s), isoDate(addDays(s, 6)));
    }, []);
    const refreshAll = () => { void today.reload(); void week.reload(); void preds.reload(); };
    const upcoming = (exams.data ?? []).filter(e => e.days_remaining >= 0).slice(0, 4);
    const weekTotal = week.data?.length ?? 0;
    const weekDone = week.data?.filter(s => s.status === 'completed').length ?? 0;
    const weak = (preds.data?.topics ?? [])
        .filter(t => t.probability !== null)
        .sort((a, b) => (a.probability ?? 1) - (b.probability ?? 1))
        .slice(0, 4);
    return (<>
      <PageTitle title={`Hi, ${user?.display_name ?? ''}`} sub="Here is what to revise today."/>

      {preds.data && !preds.data.model.trained && (<p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Model not trained: {preds.data.model.message} Plans will not use Transformer predictions until a checkpoint exists.
        </p>)}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Today's revision plan" right={<Link to="/plan" className="text-sm text-indigo-600">Full plan</Link>}>
            {today.loading ? <Spinner /> : today.error ? <ErrorBox message={today.error}/> : (<div className="space-y-3">
                {today.data.overdue.length > 0 && (<>
                    <p className="text-sm font-medium text-red-600">Overdue</p>
                    {today.data.overdue.map(s => <SessionCard key={s.id} s={s} onChanged={refreshAll}/>)}
                    <p className="pt-1 text-sm font-medium text-slate-700">Today</p>
                  </>)}
                {today.data.today.length === 0
                ? <Empty>Nothing scheduled today. Go to <Link className="text-indigo-600" to="/plan">Plan</Link> and generate one.</Empty>
                : today.data.today.map(s => <SessionCard key={s.id} s={s} onChanged={refreshAll}/>)}
              </div>)}
          </Card>

          <Card title="Topics needing practice (model estimate)">
            {preds.loading ? <Spinner /> : weak.length === 0
            ? <Empty>No estimates yet. Take a quiz to give the model some history.</Empty>
            : (<ul className="space-y-2">
                  {weak.map(t => (<li key={t.topic_id} className="flex items-center justify-between text-sm">
                      <span><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: t.subject_color }}/>{t.topic_name} <span className="text-slate-400">· {t.subject_name}</span></span>
                      <span className="font-medium">{pct(t.probability ?? 0)}</span>
                    </li>))}
                </ul>)}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="This week">
            {week.loading ? <Spinner /> : weekTotal === 0 ? <Empty>No sessions this week.</Empty> : (<>
                <p className="text-3xl font-bold text-slate-900">{weekDone}<span className="text-lg text-slate-400"> / {weekTotal}</span></p>
                <p className="mb-2 text-sm text-slate-500">sessions completed</p>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-indigo-600" style={{ width: `${(weekDone / weekTotal) * 100}%` }}/>
                </div>
              </>)}
          </Card>

          <Card title="Upcoming exams">
            {exams.loading ? <Spinner /> : upcoming.length === 0 ? <Empty>No upcoming exams. Add one in Subjects.</Empty> : (<ul className="space-y-2 text-sm">
                {upcoming.map(e => (<li key={e.id} className="flex justify-between"><span>{e.title}</span>
                    <span className="text-slate-500">{fmtDate(e.exam_date)} · {e.days_remaining}d</span></li>))}
              </ul>)}
          </Card>

          <Card title="Recent quizzes" right={<Link to="/quiz" className="text-sm text-indigo-600">Take one</Link>}>
            {quizzes.loading ? <Spinner /> : (quizzes.data ?? []).length === 0 ? <Empty>No quizzes yet.</Empty> : (<ul className="space-y-2 text-sm">
                {quizzes.data.map(q => (<li key={q.id} className="flex justify-between"><span>{fmtDate(q.completed_at)}</span>
                    <span className="font-medium">{q.score}/{q.total} ({q.percent}%)</span></li>))}
              </ul>)}
          </Card>
        </div>
      </div>
    </>);
}
