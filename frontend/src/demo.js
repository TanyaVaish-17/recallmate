import { api } from './api';
const DEMO = [
    {
        name: 'Deep Learning', color: '#6366f1', examInDays: 9,
        topics: [
            { name: 'Transformers', difficulty: 4, minutes: 40, questions: [
                    ['What lets a Transformer weigh earlier tokens when processing a later one?', 'Self-attention computes weights between all positions.', ['Self-attention', 'Max pooling', 'Dropout', 'Batch size'], 0],
                    ['Why is a causal mask used in a decoder-style model?', 'It stops position t from attending to later positions.', ['To speed up training', 'To prevent attending to future positions', 'To reduce parameters', 'To normalise inputs'], 1],
                    ['What does positional encoding provide?', 'Attention is order-agnostic, so order must be injected.', ['Word meaning', 'Order information', 'Regularisation', 'Learning rate'], 1],
                ] },
            { name: 'Backpropagation', difficulty: 3, minutes: 30, questions: [
                    ['Backpropagation computes gradients using which rule?', 'The chain rule propagates derivatives layer by layer.', ['Chain rule', 'Bayes rule', 'Pigeonhole principle', 'Central limit theorem'], 0],
                    ['A vanishing gradient mostly harms which layers?', 'Gradients shrink as they travel backward.', ['Output layer', 'Earlier layers', 'The loss function', 'The optimizer'], 1],
                    ['Which activation helps reduce vanishing gradients?', 'ReLU has gradient 1 for positive inputs.', ['Sigmoid', 'Tanh', 'ReLU', 'Softmax'], 2],
                ] },
        ],
    },
    {
        name: 'Operating Systems', color: '#10b981', examInDays: 13,
        topics: [
            { name: 'Deadlocks', difficulty: 4, minutes: 35, questions: [
                    ['Which is NOT a necessary condition for deadlock?', 'The four conditions are mutual exclusion, hold and wait, no preemption, circular wait.', ['Mutual exclusion', 'Circular wait', 'Preemption', 'Hold and wait'], 2],
                    ['The Banker\'s algorithm is used for:', 'It checks whether granting a request keeps the system in a safe state.', ['Deadlock avoidance', 'Memory paging', 'Disk scheduling', 'Process creation'], 0],
                    ['Breaking circular wait is commonly done by:', 'Impose an ordering on resources.', ['Ordering resources', 'Adding RAM', 'Killing the shell', 'Using more threads'], 0],
                ] },
            { name: 'CPU Scheduling', difficulty: 3, minutes: 30, questions: [
                    ['Which scheduling algorithm can cause starvation of long jobs?', 'Shortest Job First keeps favouring short jobs.', ['Round Robin', 'Shortest Job First', 'FCFS', 'None of these'], 1],
                    ['In Round Robin, the time quantum is too large. It behaves like:', 'A huge quantum means each process runs to completion.', ['FCFS', 'SJF', 'Priority scheduling', 'Multilevel queue'], 0],
                    ['Turnaround time equals:', 'Completion time minus arrival time.', ['Completion − arrival', 'Waiting + arrival', 'Burst − waiting', 'Arrival − burst'], 0],
                ] },
        ],
    },
    {
        name: 'DBMS', color: '#f59e0b', examInDays: 17,
        topics: [
            { name: 'Normalization', difficulty: 3, minutes: 30, questions: [
                    ['A relation is in 2NF if it is in 1NF and has no:', 'Partial dependency on a part of a composite key.', ['Partial dependency', 'Transitive dependency', 'Multivalued attribute', 'Foreign key'], 0],
                    ['BCNF requires that for every functional dependency X → Y:', 'X must be a superkey.', ['Y is a prime attribute', 'X is a superkey', 'X is a foreign key', 'Y is unique'], 1],
                    ['The main goal of normalization is to:', 'Reduce redundancy and update anomalies.', ['Reduce redundancy', 'Increase redundancy', 'Speed up all queries', 'Remove indexes'], 0],
                ] },
            { name: 'Transactions', difficulty: 4, minutes: 35, questions: [
                    ['In ACID, the letter I stands for:', 'Isolation: concurrent transactions do not interfere.', ['Integrity', 'Isolation', 'Indexing', 'Inheritance'], 1],
                    ['Which anomaly is a dirty read?', 'Reading data written by an uncommitted transaction.', ['Reading uncommitted data', 'Losing an update', 'Phantom rows', 'Deadlock'], 0],
                    ['Two-phase locking guarantees:', '2PL ensures conflict-serializable schedules.', ['Serializability', 'No deadlocks', 'Faster commits', 'No rollbacks'], 0],
                ] },
        ],
    },
];
/** Creates 3 subjects, 6 topics, 18 questions and 3 exams for the college demo. */
export async function loadDemoData() {
    const today = new Date();
    for (const s of DEMO) {
        const subject = await api.createSubject(s.name, s.color);
        for (const t of s.topics) {
            const topic = await api.createTopic(subject.id, { name: t.name, difficulty: t.difficulty, estimated_minutes: t.minutes });
            for (const [text, explanation, options, correct] of t.questions) {
                await api.createQuestion(topic.id, {
                    text, explanation,
                    options: options.map((o, i) => ({ text: o, is_correct: i === correct })),
                });
            }
        }
        const d = new Date(today);
        d.setDate(d.getDate() + s.examInDays);
        await api.createExam(subject.id, `${s.name} exam`, d.toLocaleDateString('en-CA'));
    }
}
