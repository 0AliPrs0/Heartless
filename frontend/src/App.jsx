import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import AuthPage from './pages/AuthPage';
import LobbyPage from './pages/LobbyPage';
import GamePage from './pages/GamePage';
import WaitingRoomPage from './pages/WaitingRoomPage';
import './App.css';

const PrivateRoute = ({ children }) => {
  const { currentUser } = useAuth();
  return currentUser ? children : <Navigate to="/" />;
};

function App() {
  return (
    <Routes>
      <Route path="/" element={<AuthPage />} />
      <Route path="/lobby" element={<PrivateRoute><LobbyPage /></PrivateRoute>} />
      <Route path="/waiting/:gameId" element={<PrivateRoute><WaitingRoomPage /></PrivateRoute>} />
      <Route path="/game/:gameId" element={<PrivateRoute><GamePage /></PrivateRoute>} />
    </Routes>
  );
}

export default App;