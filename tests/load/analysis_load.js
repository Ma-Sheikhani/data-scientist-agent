import http from 'k6/http';
import { check, sleep } from 'k6';

// Read file at init stage (global scope)
const csvData = open('/data/test.csv', 'b');

export const options = {
  stages: [
    { duration: '30s', target: 5 },
    { duration: '1m', target: 5 },
    { duration: '10s', target: 0 },
  ],
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  // 1. Login
  const loginRes = http.post(`${BASE_URL}/auth/token`, JSON.stringify({
    email: 'load@test.com',
    password: 'loadtest',
  }), { headers: { 'Content-Type': 'application/json' } });

  check(loginRes, { 'login successful': (r) => r.status === 200 });

  if (loginRes.status !== 200) return;

  const token = JSON.parse(loginRes.body).access_token;

  // 2. Submit analysis with the pre‑read CSV file
  const formData = {
    file: http.file(csvData, 'test.csv', 'text/csv'),
    question: 'correlation',
  };

  const analyzeRes = http.post(`${BASE_URL}/v1/analyze`, formData, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  check(analyzeRes, { 'analysis submitted': (r) => r.status === 201 });

  sleep(1);
}
