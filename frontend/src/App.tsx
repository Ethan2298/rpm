import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { LayoutDashboard, Car, Users, MessageSquare, Smartphone } from 'lucide-react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import CarDetail from './pages/CarDetail';
import Leads from './pages/Leads';
import Conversations from './pages/Conversations';
import TextSimulator from './pages/TextSimulator';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/inventory', label: 'Inventory', icon: Car },
  { to: '/leads', label: 'Leads', icon: Users },
  { to: '/conversations', label: 'Chats', icon: MessageSquare },
  { to: '/simulator', label: 'Simulator', icon: Smartphone },
];

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <div className="flex h-screen bg-background">
          {/* Desktop Sidebar — hidden on mobile */}
          <aside className="hidden md:flex w-64 bg-card border-r border-border flex-col shrink-0">
            {/* Logo */}
            <div className="px-6 py-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                  <span className="text-primary-foreground font-black text-lg tracking-tighter">R</span>
                </div>
                <div>
                  <h1 className="text-foreground font-bold text-lg tracking-wide">RPM</h1>
                  <p className="text-muted-foreground text-[10px] uppercase tracking-widest leading-none">Collector Cars</p>
                </div>
              </div>
            </div>

            <Separator />

            {/* Navigation */}
            <nav className="flex-1 px-4 py-6 space-y-1.5">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
                        isActive
                          ? 'bg-primary/10 text-primary border border-primary/20'
                          : 'text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent'
                      )
                    }
                  >
                    <Icon className="w-5 h-5" />
                    {item.label}
                  </NavLink>
                );
              })}
            </nav>

            {/* Footer */}
            <Separator />
            <div className="px-6 py-5">
              <div className="flex items-center gap-2.5">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-muted-foreground text-xs">Marcus AI Online</span>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto px-4 py-4 pb-20 md:px-10 md:py-8 md:pb-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/inventory/:id" element={<CarDetail />} />
              <Route path="/leads" element={<Leads />} />
              <Route path="/conversations" element={<Conversations />} />
              <Route path="/simulator" element={<TextSimulator />} />
            </Routes>
          </main>

          {/* Mobile Bottom Tab Bar */}
          <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border safe-area-bottom">
            <div className="flex items-center justify-around h-16">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      cn(
                        'flex flex-col items-center justify-center gap-0.5 min-w-[48px] min-h-[44px] px-2 py-1 rounded-lg text-[10px] font-medium transition-colors',
                        isActive
                          ? 'text-primary'
                          : 'text-muted-foreground'
                      )
                    }
                  >
                    <Icon className="w-5 h-5" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </nav>
        </div>
      </BrowserRouter>
    </TooltipProvider>
  );
}
