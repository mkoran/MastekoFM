import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  type User,
} from 'firebase/auth'
import { firebaseAuth, googleProvider } from '../services/firebase'

interface AuthContextType {
  user: User | null
  loading: boolean
  token: string | null
  signInWithGoogle: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
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

  const signOut = async () => {
    await firebaseSignOut(firebaseAuth)
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, token, signInWithGoogle, signOut }}>
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
