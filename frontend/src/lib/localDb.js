import { apiRequest } from '../utils/api';

const USER_ID = 'demo_user';

export async function loadSessionsFromDB() {
  return apiRequest(`/sessions?user_id=${encodeURIComponent(USER_ID)}`);
}

export async function saveSessionToDB(session) {
  return apiRequest('/sessions', {
    method: 'POST',
    body: JSON.stringify({
      user_id: USER_ID,
      session,
    }),
  });
}

export async function deleteSessionFromDB(sessionId) {
  return apiRequest(`/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(USER_ID)}`, {
    method: 'DELETE',
  });
}

export async function loadProfileFromDB() {
  return apiRequest(`/profile?user_id=${encodeURIComponent(USER_ID)}`);
}

export async function saveProfileToDB(profile) {
  return apiRequest('/profile', {
    method: 'POST',
    body: JSON.stringify({
      user_id: USER_ID,
      profile,
    }),
  });
}
