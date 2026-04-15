import { initializeApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'AIzaSyA9sHXGaAHU-rRxJ02KX5rHfE5u3Duti-8',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'masteko-fm.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'masteko-fm',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'masteko-fm.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '560873149926',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:560873149926:web:c5acae4646548d2a7db227',
}

export const firebaseApp = initializeApp(firebaseConfig)
export const firebaseAuth = getAuth(firebaseApp)
export const googleProvider = new GoogleAuthProvider()
