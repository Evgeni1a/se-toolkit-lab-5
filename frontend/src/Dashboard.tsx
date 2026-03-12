import React, { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  PointElement
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import { ScoreBucket, TimelinePoint, PassRate } from './types';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  PointElement
);

const API_BASE_URL = import.meta.env.VITE_API_TARGET || 'http://localhost:42002';

const Dashboard: React.FC = () => {
  const [selectedLab, setSelectedLab] = useState<string>('lab-04');
  const [scores, setScores] = useState<ScoreBucket[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [passRates, setPassRates] = useState<PassRate[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const labs = ['lab-01', 'lab-02', 'lab-03', 'lab-04', 'lab-05'];

  const getAuthToken = (): string | null => {
    return localStorage.getItem('api_key');
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    const token = getAuthToken();
    if (!token) {
      setError('API key not found. Please connect first.');
      setLoading(false);
      return;
    }

    const headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };

    try {
      // Fetch scores
      const scoresRes = await fetch(`${API_BASE_URL}/analytics/scores?lab=${selectedLab}`, { headers });
      if (!scoresRes.ok) throw new Error('Failed to fetch scores');
      const scoresData = await scoresRes.json();
      setScores(scoresData);

      // Fetch timeline
      const timelineRes = await fetch(`${API_BASE_URL}/analytics/timeline?lab=${selectedLab}`, { headers });
      if (!timelineRes.ok) throw new Error('Failed to fetch timeline');
      const timelineData = await timelineRes.json();
      setTimeline(timelineData);

      // Fetch pass rates
      const passRatesRes = await fetch(`${API_BASE_URL}/analytics/pass-rates?lab=${selectedLab}`, { headers });
      if (!passRatesRes.ok) throw new Error('Failed to fetch pass rates');
      const passRatesData = await passRatesRes.json();
      setPassRates(passRatesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedLab]);

  // Prepare chart data
  const scoresChartData = {
    labels: scores.map(item => item.bucket),
    datasets: [
      {
        label: 'Number of Students',
        data: scores.map(item => item.count),
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1,
      },
    ],
  };

  const timelineChartData = {
    labels: timeline.map(item => item.date),
    datasets: [
      {
        label: 'Submissions',
        data: timeline.map(item => item.submissions),
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
        tension: 0.1,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Score Distribution',
      },
    },
  };

  const timelineOptions = {
    ...chartOptions,
    plugins: {
      ...chartOptions.plugins,
      title: {
        display: true,
        text: 'Submissions Over Time',
      },
    },
  };

  if (loading) return <div>Loading dashboard...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="dashboard">
      <h2>Analytics Dashboard</h2>
      
      <div className="lab-selector">
        <label htmlFor="lab-select">Select Lab: </label>
        <select
          id="lab-select"
          value={selectedLab}
          onChange={(e) => setSelectedLab(e.target.value)}
        >
          {labs.map(lab => (
            <option key={lab} value={lab}>{lab}</option>
          ))}
        </select>
        <button onClick={fetchData}>Refresh</button>
      </div>

      <div className="charts-container">
        <div className="chart">
          <h3>Score Distribution</h3>
          {scores.length > 0 ? (
            <Bar data={scoresChartData} options={chartOptions} />
          ) : (
            <p>No score data available</p>
          )}
        </div>

        <div className="chart">
          <h3>Submissions Timeline</h3>
          {timeline.length > 0 ? (
            <Line data={timelineChartData} options={timelineOptions} />
          ) : (
            <p>No timeline data available</p>
          )}
        </div>

        <div className="table">
          <h3>Pass Rates by Task</h3>
          {passRates.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Average Score</th>
                  <th>Attempts</th>
                </tr>
              </thead>
              <tbody>
                {passRates.map((item, index) => (
                  <tr key={index}>
                    <td>{item.task}</td>
                    <td>{item.avg_score.toFixed(1)}</td>
                    <td>{item.attempts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No pass rate data available</p>
          )}
        </div>
      </div>

      <style>{`
        .dashboard {
          padding: 20px;
        }
        .lab-selector {
          margin: 20px 0;
        }
        .lab-selector select {
          margin: 0 10px;
          padding: 5px;
        }
        .lab-selector button {
          padding: 5px 15px;
          background-color: #4CAF50;
          color: white;
          border: none;
          border-radius: 3px;
          cursor: pointer;
        }
        .lab-selector button:hover {
          background-color: #45a049;
        }
        .charts-container {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: 30px;
        }
        .chart {
          background: white;
          padding: 20px;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .table {
          background: white;
          padding: 20px;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        th, td {
          padding: 10px;
          text-align: left;
          border-bottom: 1px solid #ddd;
        }
        th {
          background-color: #f2f2f2;
        }
        .error {
          color: red;
          padding: 20px;
        }
      `}</style>
    </div>
  );
};

export default Dashboard;