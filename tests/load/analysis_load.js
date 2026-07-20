import http from 'k6/http';
import { check, sleep } from 'k6';
import encoding from 'k6/encoding';

export const options = {
  stages: [
    { duration: '30s', target: 3 },   // ramp up to 3 users
    { duration: '1m',  target: 3 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'], // 95% of requests under 5s
    http_req_failed: ['rate<0.1'],      // less than 10% failures
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:8000';

// Inline CSV content (small Iris sample)
const CSV_CONTENT = 'sepal_length,sepal_width,petal_length,petal_width,species\n5.1,3.5,1.4,0.2,setosa\n4.9,3,1.4,0.2,setosa\n6.2,3.4,5.4,2.3,virginica\n';

export function setup() {
  const email = `loadtest_${Date.now()}@test.com`;
  const password = 'loadtest123';

  // Register – accept 201 (created) or 400 (already exists, but we use unique email so shouldn't happen)
  const regRes = http.post(`${BASE_URL}/auth/register`, JSON.stringify({
    email: email,
    password: password,
  }), { headers: { 'Content-Type': 'application/json' } });

  // Log the response for debugging (remove in final version)
  console.log(`Registration status: ${regRes.status}, body: ${regRes.body}`);

  check(regRes, { 'registration successful': (r) => r.status === 201 || r.status === 400 });

  // Login
  const loginRes = http.post(`${BASE_URL}/auth/token`, JSON.stringify({
    email: email,
    password: password,
  }), { headers: { 'Content-Type': 'application/json' } });

  console.log(`Login status: ${loginRes.status}, body: ${loginRes.body}`);

  check(loginRes, { 'login successful': (r) => r.status === 200 });

  // Parse token only if login succeeded
  let token = null;
  if (loginRes.status === 200) {
    try {
      token = JSON.parse(loginRes.body).access_token;
    } catch (e) {
      console.error(`JSON parse error: ${e}, body: ${loginRes.body}`);
    }
  }
  return { token, email };
}

export default function (data) {
  const token = data.token;

  // Create a multipart form request with inline CSV
  const formData = {
    file: http.file(CSV_CONTENT, 'load_test.csv', 'text/csv'),
    question: 'What is the average sepal length?',
  };

  const analyzeRes = http.post(`${BASE_URL}/v1/analyze`, formData, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  check(analyzeRes, { 'analysis submitted': (r) => r.status === 201 });

  // Optionally poll for completion (comment out if too slow)
  // if (analyzeRes.status === 201) {
  //   const jobId = JSON.parse(analyzeRes.body).id;
  //   let status = '';
  //   for (let i = 0; i < 10; i++) {
  //     const pollRes = http.get(`${BASE_URL}/v1/analyze/${jobId}/status`, {
  //       headers: { 'Authorization': `Bearer ${token}` },
  //     });
  //     status = JSON.parse(pollRes.body).status;
  //     if (status === 'completed' || status === 'failed') break;
  //     sleep(2);
  //   }
  // }

  sleep(1);
}
