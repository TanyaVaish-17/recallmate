const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'recallmate_token';
export function getToken() {
    try {
        return localStorage.getItem(TOKEN_KEY);
    }
    catch {
        return null;
    }
}
export function setToken(t) {
    try {
        localStorage.setItem(TOKEN_KEY, t);
    }
    catch { /* ignore */ }
}
export function clearToken() {
    try {
        localStorage.removeItem(TOKEN_KEY);
    }
    catch { /* ignore */ }
}
export class ApiError extends Error {
    status;
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}
function errorMessage(data) {
    const detail = data?.detail;
    if (typeof detail === 'string')
        return detail;
    if (Array.isArray(detail)) {
        return detail
            .map((d) => {
            const field = Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1]) : '';
            return field ? `${field}: ${d.msg}` : String(d.msg);
        })
            .join('; ');
    }
    return 'Something went wrong';
}
async function req(method, path, body) {
    const headers = {};
    if (body !== undefined)
        headers['Content-Type'] = 'application/json';
    const token = getToken();
    if (token)
        headers.Authorization = `Bearer ${token}`;
    let res;
    try {
        res = await fetch(`${BASE}/api${path}`, {
            method,
            headers,
            body: body !== undefined ? JSON.stringify(body) : undefined,
        });
    }
    catch {
        throw new ApiError('Cannot reach the server. Is the backend running?', 0);
    }
    if (res.status === 204)
        return undefined;
    const data = await res.json().catch(() => null);
    if (!res.ok) {
        if (res.status === 401 && path !== '/auth/login') {
            clearToken();
            window.dispatchEvent(new Event('recallmate-logout'));
        }
        throw new ApiError(errorMessage(data), res.status);
    }
    return data;
}
/* ---------- endpoints ---------- */
export const api = {
    login: (email, password) => req('POST', '/auth/login', { email, password }),
    register: (email, password, display_name) => req('POST', '/auth/register', { email, password, display_name }),
    me: () => req('GET', '/auth/me'),
    updateMe: (b) => req('PATCH', '/auth/me', b),
    subjects: () => req('GET', '/subjects?limit=100'),
    subject: (id) => req('GET', `/subjects/${id}`),
    createSubject: (name, color) => req('POST', '/subjects', { name, color }),
    deleteSubject: (id) => req('DELETE', `/subjects/${id}`),
    createTopic: (sid, b) => req('POST', `/subjects/${sid}/topics`, b),
    deleteTopic: (id) => req('DELETE', `/topics/${id}`),
    createQuestion: (topicId, b) => req('POST', `/topics/${topicId}/questions`, b),
    exams: () => req('GET', '/exams?limit=100'),
    createExam: (subject_id, title, exam_date) => req('POST', '/exams', { subject_id, title, exam_date }),
    deleteExam: (id) => req('DELETE', `/exams/${id}`),
    startQuiz: (topic_ids, num_questions) => req('POST', '/quizzes/start', { topic_ids, num_questions }),
    submitQuiz: (id, answers) => req('POST', `/quizzes/${id}/submit`, { answers }),
    quizzes: (limit = 50) => req('GET', `/quizzes?limit=${limit}`),
    quiz: (id) => req('GET', `/quizzes/${id}`),
    generatePlan: (horizon_days) => req('POST', '/plan/generate', { horizon_days }),
    plan: (start, end) => req('GET', `/plan?start=${start}&end=${end}`),
    planToday: () => req('GET', '/plan/today'),
    addSession: (topic_id, scheduled_date, duration_minutes) => req('POST', '/plan/sessions', { topic_id, scheduled_date, duration_minutes }),
    completeSession: (id) => req('POST', `/plan/sessions/${id}/complete`),
    skipSession: (id) => req('POST', `/plan/sessions/${id}/skip`),
    rescheduleSession: (id, scheduled_date) => req('POST', `/plan/sessions/${id}/reschedule`, { scheduled_date }),
    deleteSession: (id) => req('DELETE', `/plan/sessions/${id}`),
    predictions: () => req('GET', '/predictions/topics'),
    modelResults: () => req('GET', '/model/results'),
};
