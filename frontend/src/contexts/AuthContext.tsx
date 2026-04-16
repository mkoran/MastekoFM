import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  type User,
} from 'firebase/auth'
import { firebaseAuth, googleProvider } from '../services/firebase'

interface DevUser {
  email: string
  displayName: string
  uid: string
}

interface AuthContextType {
  user: User | DevUser | null
  loading: boolean
  token: string | null
  googleAccessToken: string | null
  signInWithGoogle: () => Promise<void>
  signInDev: (email: string) => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

const DEV_USER_KEY = 'masteko_dev_user'
const GOOGLE_TOKEN_KEY = 'masteko_google_access_token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | DevUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState<string | null>(null)
  const [googleAccessToken, setGoogleAccessToken] = useState<string | null>(
    localStorage.getItem(GOOGLE_TOKEN_KEY)
  )

  useEffect(() => {
    const stored = localStorage.getItem(DEV_USER_KEY)
    if (stored) {
      const devUser: DevUser = JSON.parse(stored)
      setUser(devUser)
      setToken(`dev-${devUser.email}`)
      setLoading(false)
      return
    }

    const unsubscribe = onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
      setUser(firebaseUser)
      if (firebaseUser) {
        const idToken = await firebaseUser.getIdToken()
        setToken(idToken)
      } else {
        setToken(null)
        setGoogleAccessToken(null)
        localStorage.removeItem(GOOGLE_TOKEN_KEY)
      }
      setLoading(false)
    })
    return unsubscribe
  }, [])

  const signInWithGoogle = async () => {
    // Request Drive file scope so we can upload output files to user's Drive
    googleProvider.addScope('https://www.googleapis.com/auth/drive.file')
    const result = await signInWithPopup(firebaseAuth, googleProvider)

    // Extract the Google OAuth access token
    const credential = GoogleAuthProvider.credentialFromResult(result)
    if (credential?.accessToken) {
      setGoogleAccessToken(credential.accessToken)
      localStorage.setItem(GOOGLE_TOKEN_KEY, credential.accessToken)
    }
  }

  const signInDev = (email: string) => {
    const devUser: DevUser = {
      email,
      displayName: email.split('@')[0] ?? email,
      uid: `dev-${email}`,
    }
    localStorage.setItem(DEV_USER_KEY, JSON.stringify(devUser))
    setUser(devUser)
    setToken(`dev-${email}`)
  }

  const signOut = async () => {
    localStorage.removeItem(DEV_USER_KEY)
    localStorage.removeItem(GOOGLE_TOKEN_KEY)
    setGoogleAccessToken(null)
    try {
      await firebaseSignOut(firebaseAuth)
    } catch {
      // May fail if no Firebase user
    }
    setUser(null)
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, token, googleAccessToken, signInWithGoogle, signInDev, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
