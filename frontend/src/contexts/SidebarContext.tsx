import React, { createContext, ReactNode, useContext, useState } from 'react';

interface SidebarContextType {
    isOpen: boolean;
    toggle: () => void;
    open: () => void;
    close: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

interface SidebarProviderProps {
    children: ReactNode;
}

export const SidebarProvider: React.FC<SidebarProviderProps> = ({ children }) => {
    const [isOpen, setIsOpen] = useState(true); // 기본적으로 열린 상태

    const toggle = () => setIsOpen(prev => !prev);
    const open = () => setIsOpen(true);
    const close = () => setIsOpen(false);

    return (
        <SidebarContext.Provider value={{ isOpen, toggle, open, close }}>
            {children}
        </SidebarContext.Provider>
    );
};

export const useSidebar = () => {
    const context = useContext(SidebarContext);
    if (context === undefined) {
        throw new Error('useSidebar must be used within a SidebarProvider');
    }
    return context;
};
