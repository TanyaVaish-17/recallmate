import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Btn, Card, Empty, ErrorBox, PageTitle, Spinner, fmtDate, inputCls, useLoad } from '../ui';
export default function Quiz() {
    const topics = useLoad(async () => {
        const subs = await api.subjects();
        return Promise.all(subs.map(s => api.subject(s.id)));
    }, []);
    const history = useLoad(() => api.quizzes(10), []);
    const [picked, setPicked] = useState([]);
    const [count, setCount] = useState(5);
    const [quiz, setQuiz] = useState(null);
    const [answers, setAnswers] = useState({});
    const [result, setResult] = useState(null);
    const [err, setErr] = useState('');
    const [busy, setBusy] = useState(false);
    const toggle = (id) => setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]));
    const start = async () => {
        setBusy(true);
        setErr('');
        try {
            setQuiz(await api.startQuiz(picked, count));
            setAnswers({});
            setResult(null);
        }
        catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed');
        }
        setBusy(false);
    };
    const submit = async () => {
        if (!quiz)
            return;
        setBusy(true);
        setErr('');
        try {
            const r = await api.submitQuiz(quiz.id, quiz.questions.map(q => ({ question_id: q.id, option_id: answers[q.id] })));
            setResult(r);
            setQuiz(null);
            void history.reload();
        }
        catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed');
        }
        setBusy(false);
    };
    if (result) {
        return (<>
        <PageTitle title="Quiz result"/>
        <Card>
          <p className="text-3xl font-bold">{result.score}/{result.total} <span className="text-lg text-slate-500">({result.percent}%)</span></p>
          <div className="mt-4 space-y-3">
            {result.responses.map((r, i) => (<div key={r.question_id} className={`rounded-lg border p-3 text-sm ${r.is_correct ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
                <p className="font-medium">{i + 1}. {r.text}</p>
                <p className="mt-1">{r.is_correct ? 'Correct' : 'Incorrect'}{r.explanation ? ` — ${r.explanation}` : ''}</p>
              </div>))}
          </div>
          <div className="mt-4 flex gap-2">
            <Btn onClick={() => setResult(null)}>Another quiz</Btn>
            <Link to="/plan"><Btn variant="ghost">Update my plan</Btn></Link>
          </div>
        </Card>
      </>);
    }
    if (quiz) {
        const done = quiz.questions.every(q => answers[q.id] !== undefined);
        return (<>
        <PageTitle title="Quiz" sub={`${quiz.questions.length} questions`}/>
        <div className="space-y-4">
          {quiz.questions.map((q, i) => (<Card key={q.id}>
              <p className="mb-3 font-medium">{i + 1}. {q.text}</p>
              <div className="space-y-2">
                {q.options.map(o => (<label key={o.id} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${answers[q.id] === o.id ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                    <input type="radio" name={`q${q.id}`} checked={answers[q.id] === o.id} onChange={() => setAnswers(a => ({ ...a, [q.id]: o.id }))}/>
                    {o.text}
                  </label>))}
              </div>
            </Card>))}
        </div>
        {err && <div className="mt-3"><ErrorBox message={err}/></div>}
        <Btn className="mt-4" disabled={!done || busy} onClick={submit}>{busy ? 'Submitting…' : 'Submit answers'}</Btn>
      </>);
    }
    return (<>
      <PageTitle title="Take a quiz" sub="Choose one or more topics. Every answer is saved to your learning history."/>
      <Card>
        {topics.loading ? <Spinner /> : topics.error ? <ErrorBox message={topics.error}/> :
            (topics.data ?? []).every(s => s.topics.length === 0) ? (<Empty>Add subjects and topics (and questions) first in <Link className="text-indigo-600" to="/subjects">Subjects</Link>.</Empty>) : (<div className="space-y-4">
              {topics.data.filter(s => s.topics.length).map(s => (<div key={s.id}>
                  <p className="mb-1 text-sm font-semibold" style={{ color: s.color }}>{s.name}</p>
                  <div className="flex flex-wrap gap-2">
                    {s.topics.map(t => (<button key={t.id} type="button" onClick={() => toggle(t.id)} className={`rounded-full border px-3 py-1 text-sm ${picked.includes(t.id) ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-700'}`}>
                        {t.name}
                      </button>))}
                  </div>
                </div>))}
              <label className="block text-sm">Number of questions
                <input type="number" min={1} max={20} className={`${inputCls} mt-1 !w-24`} value={count} onChange={e => setCount(Number(e.target.value))}/>
              </label>
              {err && <ErrorBox message={err}/>}
              <Btn disabled={picked.length === 0 || busy} onClick={start}>{busy ? 'Starting…' : 'Start quiz'}</Btn>
            </div>)}
      </Card>

      <Card title="Recent attempts" className="mt-4">
        {history.loading ? <Spinner /> : (history.data ?? []).length === 0 ? <Empty>No attempts yet.</Empty> : (<ul className="space-y-2 text-sm">
            {history.data.map(q => (<li key={q.id} className="flex justify-between"><span>{fmtDate(q.completed_at)}</span><span className="font-medium">{q.score}/{q.total} ({q.percent}%)</span></li>))}
          </ul>)}
      </Card>
    </>);
}
