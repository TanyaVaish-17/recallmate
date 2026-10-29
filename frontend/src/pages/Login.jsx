import { useState } from 'react';
import { useAuth } from '../auth';
import { Btn, ErrorBox, inputCls } from '../ui';
export default function Login() {
    const { login, register } = useAuth();
    const [mode, setMode] = useState('login');
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            if (mode === 'login')
                await login(email, password);
            else
                await register(email, password, name);
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed');
        }
        setBusy(false);
    };
    return (<div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-indigo-600">RecallMate</h1>
          <p className="text-sm text-slate-500">AI-powered adaptive revision scheduler</p>
        </div>
        {mode === 'register' && (<label className="block text-sm">Display name
            <input className={inputCls} value={name} onChange={e => setName(e.target.value)} required/>
          </label>)}
        <label className="block text-sm">Email
          <input type="email" className={inputCls} value={email} onChange={e => setEmail(e.target.value)} required/>
        </label>
        <label className="block text-sm">Password {mode === 'register' && <span className="text-slate-400">(min 8 characters)</span>}
          <input type="password" minLength={mode === 'register' ? 8 : undefined} className={inputCls} value={password} onChange={e => setPassword(e.target.value)} required/>
        </label>
        {error && <ErrorBox message={error}/>}
        <Btn type="submit" disabled={busy} className="w-full !py-2">
          {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </Btn>
        <button type="button" className="w-full text-center text-sm text-indigo-600" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>
          {mode === 'login' ? 'New here? Create an account' : 'Have an account? Log in'}
        </button>
      </form>
    </div>);
}
