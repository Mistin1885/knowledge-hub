import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import AuthCard from '../components/auth/AuthCard';
import { Button, ErrorNote, Input, Label } from '../components/ui/primitives';

export default function RegisterPage() {
  const [name, setName] = useState('');
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
      await authApi.register(email, name, password);
      // Registration does not set the session cookie; log in right after.
      await authApi.login(email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Registration failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Create your account">
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <div>
          <Label>Name</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            required
            autoFocus
          />
        </div>
        <div>
          <Label>Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </div>
        <div>
          <Label>Password</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <Button type="submit" variant="primary" className="w-full" busy={busy}>
          Create account
        </Button>
      </form>
      <p className="mt-4 text-center text-[13px] text-neutral-500">
        Already have an account?{' '}
        <Link to="/login" className="text-indigo-600 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
