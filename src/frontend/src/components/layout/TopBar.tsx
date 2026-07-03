import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Home, KeyRound, LogOut, Moon, Network, PanelLeft, Search, Settings } from 'lucide-react';
import type { User, Workspace } from '../../api/types';
import { authApi } from '../../api/endpoints';
import { cn, initials } from '../../lib/utils';
import { colorForUser } from '../../lib/color';
import { getTheme, setTheme } from '../../lib/theme';
import { Dropdown, MenuItem } from '../ui/Dropdown';
import MentionsBell from './MentionsBell';

function NavLink({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <Link
      to={to}
      title={label}
      className="flex h-7 items-center gap-1.5 rounded-md px-2 text-[13px] text-neutral-600 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-900"
    >
      {icon}
      <span className="hidden lg:inline">{label}</span>
    </Link>
  );
}

function DarkModeToggle() {
  const [dark, setDark] = useState(() => getTheme() === 'dark');
  const toggle = () => {
    const next = !dark;
    setDark(next);
    setTheme(next ? 'dark' : 'light');
  };
  return (
    <button
      role="switch"
      aria-checked={dark}
      onClick={(e) => {
        e.stopPropagation();
        toggle();
      }}
      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] text-neutral-700 transition-colors duration-150 hover:bg-neutral-100"
    >
      <Moon size={14} />
      <span className="flex-1">Dark mode</span>
      <span
        className={cn(
          'relative h-4 w-7 flex-none rounded-full transition-colors duration-150',
          dark ? 'bg-primary' : 'bg-neutral-300',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-all duration-150',
            dark ? 'left-3.5' : 'left-0.5',
          )}
        />
      </span>
    </button>
  );
}

export default function TopBar({
  workspace,
  user,
  onToggleSidebar,
}: {
  workspace: Workspace;
  user: User;
  onToggleSidebar: () => void;
}) {
  const navigate = useNavigate();
  const base = `/w/${workspace.slug}`;

  const logout = async () => {
    try {
      await authApi.logout();
    } finally {
      window.location.assign('/login');
    }
  };

  return (
    <header className="flex h-11 flex-none items-center justify-between border-b border-neutral-200 bg-surface px-2">
      <div className="flex items-center gap-1">
        <button
          onClick={onToggleSidebar}
          title="Toggle sidebar"
          className="rounded-md p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100"
        >
          <PanelLeft size={16} />
        </button>
        <NavLink to={base} icon={<Home size={15} />} label="Home" />
        <NavLink to={`${base}/graph`} icon={<Network size={15} />} label="Graph" />
        <NavLink to={`${base}/search`} icon={<Search size={15} />} label="Search" />
      </div>
      <div className="flex items-center gap-1">
        <MentionsBell workspaceSlug={workspace.slug} />
        <Dropdown
          align="right"
          button={
            <button
              title={user.name}
              className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold text-white"
              style={{ backgroundColor: colorForUser(user.id) }}
            >
              {initials(user.name)}
            </button>
          }
        >
          {(close) => (
            <>
              <div className="border-b border-neutral-100 px-3 py-2">
                <p className="truncate text-[13px] font-medium text-neutral-900">{user.name}</p>
                <p className="truncate text-xs text-neutral-500">{user.email}</p>
              </div>
              <MenuItem
                icon={<Settings size={14} />}
                label="Settings"
                onClick={() => {
                  close();
                  navigate(`${base}/settings`);
                }}
              />
              <MenuItem
                icon={<KeyRound size={14} />}
                label="API tokens"
                onClick={() => {
                  close();
                  navigate('/settings/tokens');
                }}
              />
              <DarkModeToggle />
              <div className="my-1 border-t border-neutral-100" />
              <MenuItem
                icon={<LogOut size={14} />}
                label="Log out"
                onClick={() => {
                  close();
                  void logout();
                }}
              />
            </>
          )}
        </Dropdown>
      </div>
    </header>
  );
}
