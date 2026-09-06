import { useState } from 'react';
// Import your API client if you have one, otherwise we just use fetch
// import apiClient from '../api/client';

export default function TaskAssignment() {
    const [taskId, setTaskId] = useState('');
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const fetchRecommendations = async (e) => {
        e.preventDefault();
        if (!taskId) return;

        setLoading(true);
        setError('');

        try {
            // Calling the FastAPI endpoint we set up in the backend
            const response = await fetch(`http://localhost:8000/api/task_assignment/top_employees/${taskId}?top_n=3`);

            if (!response.ok) {
                throw new Error('Task not found or failed to fetch candidates');
            }

            const data = await response.json();
            setCandidates(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="page-container" style={{ padding: '2rem' }}>
            <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '1rem', color: '#1f2937' }}>
                Task Assignment (ML Recommended)
            </h1>

            <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <form onSubmit={fetchRecommendations} style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
                    <input
                        type="text"
                        placeholder="Enter Task ID (e.g. TSK0001)"
                        value={taskId}
                        onChange={(e) => setTaskId(e.target.value)}
                        style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', flex: 1 }}
                    />
                    <button
                        type="submit"
                        disabled={loading}
                        style={{ padding: '0.5rem 1rem', background: '#2563eb', color: 'white', borderRadius: '4px', border: 'none', cursor: 'pointer' }}
                    >
                        {loading ? 'Searching...' : 'Find Best Employees'}
                    </button>
                </form>

                {error && <p style={{ color: 'red', marginBottom: '1rem' }}>{error}</p>}

                {candidates.length > 0 && (
                    <div>
                        <h2 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '1rem' }}>Top 3 Recommended Candidates</h2>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {candidates.map((candidate, index) => (
                                <div key={candidate.employee_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                                    <div>
                                        <h3 style={{ fontWeight: 'bold', color: '#111827' }}>#{index + 1} - Employee: {candidate.employee_id}</h3>
                                        <p style={{ fontSize: '14px', color: '#4b5563' }}>Success Probability: {candidate.success_probability}%</p>
                                        <p style={{ fontSize: '14px', color: '#4b5563' }}>Recommendation: {candidate.recommendation}</p>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <span style={{
                                            display: 'inline-block', padding: '4px 8px', borderRadius: '9999px', fontSize: '12px', fontWeight: 'bold',
                                            background: candidate.delay_risk_label === 'Low' ? '#dcfce7' : candidate.delay_risk_label === 'Moderate' ? '#fef08a' : '#fee2e2',
                                            color: candidate.delay_risk_label === 'Low' ? '#166534' : candidate.delay_risk_label === 'Moderate' ? '#854d0e' : '#991b1b'
                                        }}>
                                            {candidate.delay_risk_label} Delay Risk ({candidate.delay_risk_score})
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
