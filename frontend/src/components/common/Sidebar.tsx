import React from 'react';
import { NavLink } from 'react-router-dom';
// import { useRole } from '../../hooks/useRole';

interface MenuItem {
  path?: string;
  icon?: string;
  label?: string;
  type?: 'item' | 'divider';
}

interface SidebarProps {
  menuItems: MenuItem[];
  className?: string;
  isCollapsed?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  menuItems,
  className = '',
  isCollapsed = false
}) => {
  // const { currentRole } = useRole(); // For future role-based features

  return (
    <nav className={`bg-gray-50 border-r border-gray-200 ${className} overflow-hidden`}>
      <div className="p-4">
        <ul className="space-y-1">
          {menuItems.map((item, index) => {
            if (item.type === 'divider') {
              return (
                <li key={index} className="my-3">
                  <hr className="border-gray-300" />
                </li>
              );
            }

            if (!item.path || !item.icon || !item.label) {
              return null;
            }

            return (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${isActive
                      ? 'bg-blue-100 text-blue-700 border-r-2 border-blue-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`
                  }
                  title={item.label}
                >
                  <span className="mr-3 text-lg flex-shrink-0">{item.icon}</span>
                  <span className={`${isCollapsed ? 'opacity-0 w-0' : 'opacity-100'} transition-all duration-300 overflow-hidden whitespace-nowrap`}>
                    {item.label}
                  </span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
};
