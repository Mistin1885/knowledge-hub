import { Link, useNavigate } from 'react-router-dom';
import { Home, KeyRound, LogOut, Network, PanelLeft, Search, Settings } from 'lucide-react';
import type { User, Workspace } from '../../api/types';
import { authApi } from '../../api/endpoints';
import { initials } from '../../lib/utils';
import { colorForUser } from '../../lib/color';
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
    <header className="flex h-11 flex-none items-center justify-between border-b border-neutral-200 bg-white px-2">
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
        <NavLink to={`${base}/settings`} icon={<Settings size={15} />} label="Settings" />
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
                icon={<KeyRound size={14} />}
                label="API tokens"
                onClick={() => {
                  close();
                  navigate('/settings/tokens');
                }}
              />
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
