import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import {
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
  signInWithGoogle: () => Promise<void>
  signInDev: (email: string) => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

const DEV_USER_KEY = 'masteko_dev_user'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | DevUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    // Check for dev user in localStorage first
    const stored = localStorage.getItem(DEV_USER_KEY)
    if (stored) {
      const devUser: DevUser = JSON.parse(stored)
      setUser(devUser)
      setToken(`dev-${devUser.email}`)
      setLoading(false)
      return
    }

    // Firebase auth listener
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (firebaseUser) => {
      setUser(firebaseUser)
      if (firebaseUser) {
        const idToken = await firebaseUser.getIdToken()
        setToken(idToken)
      } else {
        setToken(null)
      }
      setLoading(false)
    })
    return unsubscribe
  }, [])

  const signInWithGoogle = async () => {
    await signInWithPopup(firebaseAuth, googleProvider)
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
    try {
      await firebaseSignOut(firebaseAuth)
    } catch {
      // May fail if no Firebase user
    }
    setUser(null)
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, token, signInWithGoogle, signInDev, signOut }}>
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
