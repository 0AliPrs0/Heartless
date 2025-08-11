import React, { createContext, useState, useContext, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { login as apiLogin } from '../services/api';

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [currentUser, setCurrentUser] = useState(null);
    const socket = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        const storedUser = localStorage.getItem('user');
        const token = localStorage.getItem('access_token');
        if (storedUser && token) {
            setCurrentUser(JSON.parse(storedUser));
        }
    }, []);

    const login = async (username, password) => {
        const response = await apiLogin(username, password);
        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);
        
        const userResponse = await apiClient.get('/auth/users/me');
        
        localStorage.setItem('user', JSON.stringify(userResponse.data));
        setCurrentUser(userResponse.data);
        
        navigate('/lobby');
    };

    const register = async (username, password) => {
        await apiClient.post('/auth/register', { username, password });
        await login(username, password);
    };
    
    const logout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        setCurrentUser(null);
        disconnectSocket();
        navigate('/');
    };

    const connectSocket = useCallback((gameId) => {
        if (socket.current && socket.current.readyState === WebSocket.OPEN) {
            return;
        }
        if (socket.current) { // Close any lingering connection
            socket.current.close();
        }
        const token = localStorage.getItem("access_token");
        if (!token) return;

        socket.current = new WebSocket(`ws://localhost:8000/games/${gameId}/ws?token=${token}`);
        
        socket.current.onopen = () => console.log(`Socket connected for game ${gameId}`);
        socket.current.onclose = () => console.log(`Socket disconnected for game ${gameId}`);
        socket.current.onerror = (error) => console.error("Socket Error: ", error);
    }, []);

    const disconnectSocket = () => {
        if (socket.current && socket.current.readyState === WebSocket.OPEN) {
            socket.current.close();
            socket.current = null;
        }
    };

    const value = { 
        currentUser, 
        socket,
        login, 
        register,
        logout,
        connectSocket,
        disconnectSocket
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
