import { NavLink, Outlet } from 'react-router-dom';
import { BarChart3, BookOpen, Brain, CalendarCheck, ClipboardCheck, LayoutDashboard, LogOut } from 'lucide-react';
import { useAuth } from './auth';
const NAV = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/subjects', label: 'Subjects', icon: BookOpen },
    { to: '/quiz', label: 'Quiz', icon: ClipboardCheck },
    { to: '/plan', label: 'Plan', icon: CalendarCheck },
    { to: '/analytics', label: 'Analytics', icon: BarChart3 },
    { to: '/model', label: 'Model', icon: Brain },
];
export default function Layout() {
    const { user, logout } = useAuth();
    const link = ({ isActive }) => `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`;
    return (<div className="min-h-screen md:flex">
      <aside className="border-b border-slate-200 bg-white md:fixed md:inset-y-0 md:w-56 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-4 py-3 md:block">
          <p className="text-lg font-bold text-indigo-600">RecallMate</p>
          <p className="hidden text-xs text-slate-500 md:block">{user?.display_name}</p>
          <button onClick={logout} className="text-slate-500 md:hidden" aria-label="Log out"><LogOut size={18}/></button>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-2 md:flex-col md:overflow-visible">
          {NAV.map(n => (<NavLink key={n.to} to={n.to} end={n.to === '/'} className={link}>
              <n.icon size={16}/> {n.label}
            </NavLink>))}
        </nav>
        <button onClick={logout} className="absolute bottom-4 left-4 hidden items-center gap-2 text-sm text-slate-500 hover:text-slate-800 md:flex">
          <LogOut size={16}/> Log out
        </button>
      </aside>
      <main className="mx-auto w-full max-w-5xl px-4 py-6 md:ml-56 md:px-8">
        <Outlet />
      </main>
    </div>);
}
