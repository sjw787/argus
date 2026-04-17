import { LogIn } from 'lucide-react'
import type { AuthConfig } from '../../api/client'

interface Props {
  config: AuthConfig
}

export function CognitoLoginDialog({ config }: Props) {
  const { cognitoUserPoolId, cognitoClientId, cognitoDomain } = config

  const region = cognitoUserPoolId?.split('_')[0] ?? 'us-east-1'
  const redirectUri = encodeURIComponent(`${window.location.origin}/auth/callback`)
  const loginUrl =
    `https://${cognitoDomain}.auth.${region}.amazoncognito.com/login` +
    `?client_id=${cognitoClientId}&response_type=token&redirect_uri=${redirectUri}`

  return (
    <div className="fixed inset-0 flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="rounded-lg p-8 flex flex-col items-center gap-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>AthenaBeaver</h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Sign in to continue</p>
        <a
          href={loginUrl}
          className="flex items-center gap-2 px-4 py-2 rounded text-sm font-medium"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          <LogIn size={16} />
          Sign in with Cognito
        </a>
      </div>
    </div>
  )
}
