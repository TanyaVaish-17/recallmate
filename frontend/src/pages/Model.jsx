import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import { Card, ErrorBox, PageTitle, Spinner, useLoad } from '../ui';
const f = (v) => v.toFixed(3);
export default function Model() {
    const m = useLoad(() => api.modelResults(), []);
    if (m.loading)
        return <Spinner />;
    if (m.error)
        return <ErrorBox message={m.error}/>;
    const { status, explainer, results } = m.data;
    const rows = results ? [
        ['Transformer (test)', results.transformer_test],
        ['Transformer, ids hidden (test)', results.transformer_test_id_free],
        ['Logistic regression (test)', results.baseline_logistic],
        ['Previous-answer rate (test)', results.baseline_previous_answer],
        ['Global rate (test)', results.baseline_global_rate],
    ] : [];
    return (<>
      <PageTitle title="The model behind RecallMate" sub="A compact causal Transformer encoder for knowledge tracing."/>

      <div className={`mb-4 rounded-lg px-3 py-2 text-sm ${status.trained ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'}`}>
        {status.trained
            ? `Model loaded: ${status.model_version} (${status.n_parameters?.toLocaleString()} parameters).`
            : `Model not trained. ${status.message}`}
      </div>
      {results?.dataset.is_synthetic && (<div className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <b>Synthetic data.</b> These results come from simulated students. They are a development check, not results on real students.
        </div>)}

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Why a Transformer?"><p className="text-sm text-slate-700">{explainer.why_transformer}</p></Card>
        <Card title="Architecture"><p className="text-sm text-slate-700">{explainer.architecture}</p></Card>
        <Card title="Input features">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{explainer.input_features.map(x => <li key={x}>{x}</li>)}</ul>
        </Card>
        <Card title="Target construction (no future leakage)"><p className="text-sm text-slate-700">{explainer.target_construction}</p></Card>
      </div>

      {results ? (<div className="mt-4 space-y-4">
          <Card title="Test-set results (threshold 0.5)">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead><tr className="border-b border-slate-200 text-slate-500">
                  {['Model', 'AUC', 'Accuracy', 'Precision', 'Recall', 'F1', 'Log loss'].map(h => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}
                </tr></thead>
                <tbody>{rows.map(([name, r]) => (<tr key={name} className="border-b border-slate-100">
                    <td className="py-2 pr-4 font-medium">{name}</td><td className="pr-4">{f(r.auc)}</td><td className="pr-4">{f(r.accuracy)}</td>
                    <td className="pr-4">{f(r.precision)}</td><td className="pr-4">{f(r.recall)}</td><td className="pr-4">{f(r.f1)}</td><td>{f(r.log_loss)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-slate-500">"Ids hidden" replaces every question/topic id with unknown, which is how RecallMate uses the model on its own question bank.</p>
          </Card>

          <Card title="Training curves">
            <div className="h-64"><ResponsiveContainer><LineChart data={results.training.history}>
              <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="epoch"/><YAxis /><Tooltip /><Legend />
              <Line type="monotone" dataKey="train_loss" stroke="#4f46e5" dot={false}/>
              <Line type="monotone" dataKey="val_loss" stroke="#f59e0b" dot={false}/>
              <Line type="monotone" dataKey="val_auc" stroke="#10b981" dot={false}/>
            </LineChart></ResponsiveContainer></div>
            <p className="mt-2 text-xs text-slate-500">
              {results.training.epochs_run} epochs run, best epoch {results.training.best_epoch}, validation AUC {f(results.training.best_val_auc)}; model selected on validation, test evaluated once afterwards.
            </p>
          </Card>

          <Card title="Dataset">
            <ul className="space-y-1 text-sm text-slate-700">
              <li>Source: <b>{results.dataset.source}</b>{results.dataset.is_synthetic ? ' (synthetic)' : ''}</li>
              {Object.entries(results.dataset.splits).map(([k, v]) => (<li key={k}>{k}: {v.students} students, {v.interactions.toLocaleString()} interactions, positive rate {f(v.positive_rate)}</li>))}
              <li>Split by student; vocabularies and normalisation fitted on the training split only.</li>
            </ul>
          </Card>
        </div>) : (<Card title="Experiment results" className="mt-4">
          <p className="text-sm text-slate-600">No results file found. Run <code>python -m ml.training.train</code> to produce one.</p>
        </Card>)}

      <Card title="Limitations" className="mt-4">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{explainer.limitations.map(x => <li key={x}>{x}</li>)}</ul>
      </Card>
    </>);
}
