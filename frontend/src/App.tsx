import { useState, useEffect } from 'react';
import axios from 'axios';
import AgentConsole from './AgentConsole';

const API_URL = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/ws';

const App = () => {
  const [activeTab, setActiveTab] = useState('list');
  const [experiences, setExperiences] = useState([]);
  const [projects, setProjects] = useState([]);
  const [settings, setSettings] = useState({ llm_retry_max: 3, llm_wait_time: 5, llm_model: "anthropic/claude-3-haiku" });
  const [jdText, setJdText] = useState('');
  const [startAlign, setStartAlign] = useState(false);

  useEffect(() => {
    if (activeTab === 'list') {
      axios.get(`${API_URL}/experiences`).then(res => setExperiences(res.data));
      axios.get(`${API_URL}/projects`).then(res => setProjects(res.data));
    } else if (activeTab === 'settings') {
      axios.get(`${API_URL}/settings`).then(res => setSettings(res.data));
    }
  }, [activeTab]);

  const saveSettings = () => {
    axios.post(`${API_URL}/settings`, settings).then(() => {
      alert('Settings saved');
    });
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8 font-sans">
      <div className="max-w-6xl mx-auto bg-white rounded-xl shadow-lg overflow-hidden">
        <header className="bg-slate-900 text-white p-6">
          <h1 className="text-2xl font-bold">Resume Lifecycle Repository</h1>
          <p className="text-slate-400 text-sm mt-1">Local-first career data management</p>
        </header>

        <nav className="flex border-b bg-slate-50">
          {['list', 'add-experience', 'add-project', 'align-jd', 'settings'].map(tab => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setStartAlign(false); }}
              className={`px-6 py-3 font-medium text-sm transition-colors ${
                activeTab === tab
                  ? 'border-b-2 border-blue-600 text-blue-600 bg-white'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              {tab.replace('-', ' ').toUpperCase()}
            </button>
          ))}
        </nav>

        <main className="p-6 min-h-[600px]">
          {activeTab === 'list' && (
            <div className="space-y-8">
              <div>
                <h2 className="text-xl font-bold mb-4 border-b pb-2">Experiences</h2>
                {experiences.length === 0 ? <p className="text-gray-500 italic">No experiences found.</p> : null}
                <div className="grid gap-4">
                  {experiences.map((exp: any) => (
                    <div key={exp.id} className="border p-4 rounded-lg shadow-sm">
                      <h3 className="font-bold text-lg">{exp.role} <span className="text-gray-500 font-normal">at {exp.company}</span></h3>
                      <p className="text-sm text-gray-500 mb-2">{exp.start_date || 'N/A'} — {exp.end_date || 'Present'}</p>
                      <ul className="list-disc pl-5 space-y-1 text-sm">
                        {exp.bullets.filter((b:any) => b.is_active).map((b:any) => (
                          <li key={b.id}>
                            {b.text}
                            {b.has_metric && <span className="ml-2 inline-flex items-center rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">Metric</span>}
                            {b.source === 'gap_enriched' && <span className="ml-2 inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-600/20">Enriched</span>}
                          </li>
                        ))}
                      </ul>
                      {exp.skills.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {exp.skills.map((s: string, i: number) => (
                            <span key={i} className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded border">{s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h2 className="text-xl font-bold mb-4 border-b pb-2">Projects</h2>
                {projects.length === 0 ? <p className="text-gray-500 italic">No projects found.</p> : null}
                <div className="grid gap-4">
                  {projects.map((proj: any) => (
                    <div key={proj.id} className="border p-4 rounded-lg shadow-sm">
                      <h3 className="font-bold text-lg">{proj.name} <span className="text-sm font-normal px-2 py-1 bg-gray-100 rounded ml-2">{proj.status}</span></h3>
                      <p className="text-sm text-gray-700 my-2">{proj.description}</p>
                      <ul className="list-disc pl-5 space-y-1 text-sm">
                        {proj.bullets.filter((b:any) => b.is_active).map((b:any) => (
                          <li key={b.id}>{b.text}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'add-experience' && (
            <AgentConsole wsUrl={`${WS_URL}/add-experience`} />
          )}

          {activeTab === 'add-project' && (
            <AgentConsole wsUrl={`${WS_URL}/add-project`} />
          )}

          {activeTab === 'align-jd' && (
            <div>
              {!startAlign ? (
                <div className="max-w-2xl mx-auto space-y-4">
                  <h2 className="text-xl font-bold">Align with Job Description</h2>
                  <p className="text-gray-600 text-sm">Paste the job description below to extract requirements and bridge gaps with your current profile.</p>
                  <textarea
                    value={jdText}
                    onChange={e => setJdText(e.target.value)}
                    rows={10}
                    className="w-full border p-3 rounded shadow-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="Paste job description here..."
                  />
                  <button
                    disabled={!jdText.trim()}
                    onClick={() => setStartAlign(true)}
                    className="w-full bg-blue-600 text-white py-3 rounded font-semibold hover:bg-blue-700 disabled:bg-gray-300 transition-colors"
                  >
                    Start Alignment Agent
                  </button>
                </div>
              ) : (
                <AgentConsole wsUrl={`${WS_URL}/align-jd`} initData={{ jd_text: jdText }} />
              )}
            </div>
          )}

          {activeTab === 'settings' && (
            <div className="max-w-md space-y-6">
              <h2 className="text-xl font-bold border-b pb-2">Agent Settings</h2>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Retry Max Attempts</label>
                <input
                  type="number"
                  value={settings.llm_retry_max}
                  onChange={e => setSettings({...settings, llm_retry_max: parseInt(e.target.value)})}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Wait Time (seconds)</label>
                <input
                  type="number"
                  value={settings.llm_wait_time}
                  onChange={e => setSettings({...settings, llm_wait_time: parseInt(e.target.value)})}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Model</label>
                <input
                  type="text"
                  value={settings.llm_model}
                  onChange={e => setSettings({...settings, llm_model: e.target.value})}
                  className="w-full border p-2 rounded"
                />
              </div>

              <button
                onClick={saveSettings}
                className="bg-slate-900 text-white px-6 py-2 rounded hover:bg-slate-800"
              >
                Save Settings
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
