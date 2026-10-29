import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth';
import Layout from './Layout';
import { Spinner } from './ui';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Subjects from './pages/Subjects';
import Quiz from './pages/Quiz';
import Plan from './pages/Plan';
import Analytics from './pages/Analytics';
import Model from './pages/Model';
export default function App() {
    const { user, loading } = useAuth();
    if (loading)
        return <Spinner />;
    if (!user) {
        return (<Routes>
        <Route path="*" element={<Login />}/>
      </Routes>);
    }
    return (<Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />}/>
        <Route path="subjects" element={<Subjects />}/>
        <Route path="quiz" element={<Quiz />}/>
        <Route path="plan" element={<Plan />}/>
        <Route path="analytics" element={<Analytics />}/>
        <Route path="model" element={<Model />}/>
        <Route path="*" element={<Navigate to="/" replace/>}/>
      </Route>
    </Routes>);
}
