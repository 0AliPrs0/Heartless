import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api', 
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  console.log("Attaching token to request:", token); 

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const register = (username, email, password) => {
  return apiClient.post('/auth/register', { username, email, password });
};

export const login = (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    return apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
};

export const getAvailableGames = () => {
    return apiClient.get('/games');
};

export const createGame = () => {
    return apiClient.post('/games/');
};

export const joinGame = (gameId) => {
    return apiClient.post(`/games/${gameId}/join`);
};

export default apiClient;