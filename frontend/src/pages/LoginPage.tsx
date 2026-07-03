import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import AuthCard from '../components/auth/AuthCard';
import { Button, ErrorNote, Input, Label } from '../components/ui/primitives';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await authApi.login(email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Sign in">
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <div>
          <Label>Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            autoFocus
          />
        </div>
        <div>
          <Label>Password</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <Button type="submit" variant="primary" className="w-full" busy={busy}>
          Sign in
        </Button>
      </form>
      <p className="mt-4 text-center text-[13px] text-neutral-500">
        New here?{' '}
        <Link to="/register" className="text-indigo-600 hover:underline">
          Create an account
        </Link>
      </p>
    </AuthCard>
  );
}
