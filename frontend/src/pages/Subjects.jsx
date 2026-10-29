import { useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import { loadDemoData } from '../demo';
import { Btn, Card, Empty, ErrorBox, PageTitle, Spinner, fmtDate, inputCls, isoDate, useLoad } from '../ui';
function Preferences() {
    const { user, refresh } = useAuth();
    const [daily, setDaily] = useState(user?.daily_study_minutes ?? 120);
    const [session, setSession] = useState(user?.session_minutes ?? 30);
    const [msg, setMsg] = useState('');
    const [err, setErr] = useState('');
    const save = async (e) => {
        e.preventDefault();
        setErr('');
        setMsg('');
        try {
            await api.updateMe({ daily_study_minutes: daily, session_minutes: session });
            await refresh();
            setMsg('Saved.');
        }
        catch (x) {
            setErr(x instanceof Error ? x.message : 'Failed');
        }
    };
    return (<Card title="Study preferences">
      <form onSubmit={save} className="flex flex-wrap items-end gap-3">
        <label className="text-sm">Study minutes per day
          <input type="number" min={15} max={720} className={`${inputCls} mt-1 !w-32`} value={daily} onChange={e => setDaily(Number(e.target.value))}/>
        </label>
        <label className="text-sm">Preferred session (min)
          <input type="number" min={10} max={120} className={`${inputCls} mt-1 !w-32`} value={session} onChange={e => setSession(Number(e.target.value))}/>
        </label>
        <Btn type="submit">Save</Btn>
        {msg && <span className="text-sm text-emerald-700">{msg}</span>}
      </form>
      {err && <div className="mt-2"><ErrorBox message={err}/></div>}
    </Card>);
}
function QuestionForm({ topic, onDone }) {
    const [text, setText] = useState('');
    const [expl, setExpl] = useState('');
    const [opts, setOpts] = useState(['', '', '', '']);
    const [correct, setCorrect] = useState(0);
    const [err, setErr] = useState('');
    const [ok, setOk] = useState('');
    const save = async (e) => {
        e.preventDefault();
        setErr('');
        setOk('');
        try {
            await api.createQuestion(topic.id, {
                text, explanation: expl || undefined,
                options: opts.map((o, i) => ({ text: o, is_correct: i === correct })),
            });
            setText('');
            setExpl('');
            setOpts(['', '', '', '']);
            setCorrect(0);
            setOk('Question added.');
            onDone();
        }
        catch (x) {
            setErr(x instanceof Error ? x.message : 'Failed');
        }
    };
    return (<form onSubmit={save} className="mt-2 space-y-2 rounded-lg bg-slate-50 p-3">
      <input className={inputCls} placeholder="Question" value={text} onChange={e => setText(e.target.value)} required/>
      {opts.map((o, i) => (<div key={i} className="flex items-center gap-2">
          <input type="radio" name={`c${topic.id}`} checked={correct === i} onChange={() => setCorrect(i)} aria-label={`Option ${i + 1} is correct`}/>
          <input className={inputCls} placeholder={`Option ${i + 1}`} value={o} required onChange={e => setOpts(opts.map((x, j) => (j === i ? e.target.value : x)))}/>
        </div>))}
      <input className={inputCls} placeholder="Explanation (optional)" value={expl} onChange={e => setExpl(e.target.value)}/>
      <p className="text-xs text-slate-500">Select the radio button next to the correct option.</p>
      {err && <ErrorBox message={err}/>}
      {ok && <p className="text-sm text-emerald-700">{ok}</p>}
      <Btn type="submit">Add question</Btn>
    </form>);
}
function SubjectBlock({ s, onChanged }) {
    const [name, setName] = useState('');
    const [diff, setDiff] = useState(3);
    const [mins, setMins] = useState(30);
    const [openQ, setOpenQ] = useState(null);
    const [err, setErr] = useState('');
    const run = async (fn) => {
        setErr('');
        try {
            await fn();
            onChanged();
        }
        catch (x) {
            setErr(x instanceof Error ? x.message : 'Failed');
        }
    };
    const addTopic = (e) => {
        e.preventDefault();
        void run(async () => { await api.createTopic(s.id, { name, difficulty: diff, estimated_minutes: mins }); setName(''); });
    };
    return (<Card>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold"><span className="h-3 w-3 rounded-full" style={{ background: s.color }}/>{s.name}</h3>
        <Btn variant="danger" onClick={() => { if (confirm(`Delete ${s.name} and everything in it?`))
        void run(() => api.deleteSubject(s.id)); }}>Delete</Btn>
      </div>
      {s.topics.length === 0 && <p className="mb-2 text-sm text-slate-500">No topics yet.</p>}
      <ul className="space-y-2">
        {s.topics.map(t => (<li key={t.id} className="rounded-lg border border-slate-200 p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{t.name} <span className="font-normal text-slate-500">· difficulty {t.difficulty}/5 · {t.estimated_minutes} min</span></span>
              <span className="flex gap-2">
                <Btn variant="ghost" onClick={() => setOpenQ(openQ === t.id ? null : t.id)}>{openQ === t.id ? 'Close' : 'Add question'}</Btn>
                <Btn variant="danger" onClick={() => { if (confirm(`Delete topic ${t.name}?`))
            void run(() => api.deleteTopic(t.id)); }}>Delete</Btn>
              </span>
            </div>
            {openQ === t.id && <QuestionForm topic={t} onDone={() => undefined}/>}
          </li>))}
      </ul>
      <form onSubmit={addTopic} className="mt-3 flex flex-wrap items-end gap-2">
        <input className={`${inputCls} !w-56`} placeholder="New topic name" value={name} onChange={e => setName(e.target.value)} required/>
        <label className="text-xs text-slate-500">Difficulty
          <select className={`${inputCls} !w-20`} value={diff} onChange={e => setDiff(Number(e.target.value))}>{[1, 2, 3, 4, 5].map(n => <option key={n}>{n}</option>)}</select>
        </label>
        <label className="text-xs text-slate-500">Minutes
          <input type="number" min={5} max={240} className={`${inputCls} !w-20`} value={mins} onChange={e => setMins(Number(e.target.value))}/>
        </label>
        <Btn type="submit">Add topic</Btn>
      </form>
      {err && <div className="mt-2"><ErrorBox message={err}/></div>}
    </Card>);
}
export default function Subjects() {
    const subjects = useLoad(async () => {
        const list = await api.subjects();
        return Promise.all(list.map(s => api.subject(s.id)));
    }, []);
    const exams = useLoad(() => api.exams(), []);
    const [name, setName] = useState('');
    const [color, setColor] = useState('#6366f1');
    const [examSubject, setExamSubject] = useState('');
    const [examTitle, setExamTitle] = useState('Final exam');
    const [examDate, setExamDate] = useState('');
    const [err, setErr] = useState('');
    const [demoBusy, setDemoBusy] = useState(false);
    const guard = async (fn) => {
        setErr('');
        try {
            await fn();
        }
        catch (x) {
            setErr(x instanceof Error ? x.message : 'Failed');
        }
    };
    const addSubject = (e) => {
        e.preventDefault();
        void guard(async () => { await api.createSubject(name, color); setName(''); await subjects.reload(); });
    };
    const addExam = (e) => {
        e.preventDefault();
        void guard(async () => { await api.createExam(Number(examSubject), examTitle, examDate); await exams.reload(); });
    };
    const demo = async () => {
        setDemoBusy(true);
        await guard(loadDemoData);
        await subjects.reload();
        await exams.reload();
        setDemoBusy(false);
    };
    const subjectName = (id) => subjects.data?.find(s => s.id === id)?.name ?? '';
    return (<>
      <PageTitle title="Subjects, topics & exams" sub="Set up what you study, when your exams are, and how much time you have."/>
      <div className="space-y-4">
        <Preferences />

        {subjects.loading ? <Spinner /> : subjects.error ? <ErrorBox message={subjects.error}/> : (subjects.data ?? []).length === 0 && (<Card title="Quick start">
            <p className="mb-3 text-sm text-slate-600">Load the demo set: Deep Learning, Operating Systems and DBMS, with 6 topics, 18 quiz questions and exam dates.</p>
            <Btn disabled={demoBusy} onClick={demo}>{demoBusy ? 'Loading demo data…' : 'Load demo data'}</Btn>
          </Card>)}

        {(subjects.data ?? []).map(s => <SubjectBlock key={s.id} s={s} onChanged={() => void subjects.reload()}/>)}

        <Card title="Add subject">
          <form onSubmit={addSubject} className="flex flex-wrap items-end gap-2">
            <input className={`${inputCls} !w-64`} placeholder="Subject name" value={name} onChange={e => setName(e.target.value)} required/>
            <input type="color" aria-label="Subject colour" className="h-9 w-12 rounded border border-slate-300" value={color} onChange={e => setColor(e.target.value)}/>
            <Btn type="submit">Add subject</Btn>
          </form>
        </Card>

        <Card title="Exams">
          {(exams.data ?? []).length === 0 ? <Empty>No exams yet.</Empty> : (<ul className="mb-3 space-y-2 text-sm">
              {exams.data.map(e => (<li key={e.id} className="flex items-center justify-between">
                  <span>{e.title} <span className="text-slate-500">· {subjectName(e.subject_id)}</span></span>
                  <span className="flex items-center gap-3 text-slate-500">{fmtDate(e.exam_date)} · {e.days_remaining}d
                    <Btn variant="danger" onClick={() => void guard(async () => { await api.deleteExam(e.id); await exams.reload(); })}>Delete</Btn></span>
                </li>))}
            </ul>)}
          <form onSubmit={addExam} className="flex flex-wrap items-end gap-2">
            <select required className={`${inputCls} !w-48`} value={examSubject} onChange={e => setExamSubject(e.target.value)}>
              <option value="">Subject…</option>
              {(subjects.data ?? []).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input className={`${inputCls} !w-44`} value={examTitle} onChange={e => setExamTitle(e.target.value)} required/>
            <input type="date" min={isoDate(new Date())} className={`${inputCls} !w-44`} value={examDate} onChange={e => setExamDate(e.target.value)} required/>
            <Btn type="submit">Add exam</Btn>
          </form>
        </Card>
        {err && <ErrorBox message={err}/>}
      </div>
    </>);
}
