# WKMS 멀티 디바이스 UI/UX 표준 설계서

## 📱 1. 개요

### 1.1 목적
웅진 WKMS 시스템을 PC, 태블릿, 스마트폰 등 모든 디바이스에서 최적의 사용자 경험을 제공하는 반응형 웹 애플리케이션으로 구현하기 위한 UI/UX 표준을 정의합니다.

### 1.2 디자인 철학
- **Mobile First**: 모바일 우선 설계로 점진적 향상
- **Progressive Enhancement**: 기능의 점진적 확장
- **Accessibility First**: 접근성을 최우선으로 고려
- **Performance Optimized**: 모든 디바이스에서 빠른 성능

### 1.3 지원 디바이스 범위
- **스마트폰**: 360px ~ 767px (Portrait/Landscape)
- **태블릿**: 768px ~ 1023px (Portrait/Landscape)  
- **데스크톱**: 1024px ~ 1440px
- **대형 모니터**: 1441px 이상

## 📐 2. 반응형 디자인 시스템

### 2.1 Breakpoint 정의
```scss
// Breakpoints
$breakpoints: (
  'mobile-s': 320px,   // 소형 스마트폰
  'mobile-m': 375px,   // 중형 스마트폰 (iPhone 12/13)
  'mobile-l': 425px,   // 대형 스마트폰 (iPhone 12 Pro Max)
  'tablet-p': 768px,   // 태블릿 세로
  'tablet-l': 1024px,  // 태블릿 가로 / 소형 노트북
  'laptop': 1440px,    // 일반 노트북
  'desktop': 1920px,   // 데스크톱
  'desktop-l': 2560px  // 대형 모니터
);

// Responsive mixins
@mixin mobile-s { @media (max-width: 320px) { @content; } }
@mixin mobile-m { @media (max-width: 375px) { @content; } }
@mixin mobile-l { @media (max-width: 425px) { @content; } }
@mixin tablet-p { @media (max-width: 768px) { @content; } }
@mixin tablet-l { @media (max-width: 1024px) { @content; } }
@mixin laptop { @media (max-width: 1440px) { @content; } }
@mixin desktop { @media (min-width: 1441px) { @content; } }
```

### 2.2 Grid System
```scss
// CSS Grid Layout System
.container {
  display: grid;
  gap: var(--spacing-md);
  padding: var(--spacing-sm);
  
  // Mobile First Grid
  grid-template-columns: 1fr;
  
  // Tablet
  @include tablet-p {
    grid-template-columns: repeat(2, 1fr);
    padding: var(--spacing-md);
  }
  
  // Desktop
  @include laptop {
    grid-template-columns: repeat(12, 1fr);
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--spacing-lg);
  }
}
```

### 2.3 Design Tokens
```scss
// Spacing System (8px base)
:root {
  --spacing-xs: 0.25rem;   // 4px
  --spacing-sm: 0.5rem;    // 8px
  --spacing-md: 1rem;      // 16px
  --spacing-lg: 1.5rem;    // 24px
  --spacing-xl: 2rem;      // 32px
  --spacing-2xl: 3rem;     // 48px
  --spacing-3xl: 4rem;     // 64px
  
  // Typography Scale
  --font-size-xs: 0.75rem;   // 12px
  --font-size-sm: 0.875rem;  // 14px
  --font-size-base: 1rem;    // 16px
  --font-size-lg: 1.125rem;  // 18px
  --font-size-xl: 1.25rem;   // 20px
  --font-size-2xl: 1.5rem;   // 24px
  --font-size-3xl: 1.875rem; // 30px
  --font-size-4xl: 2.25rem;  // 36px
  
  // Border Radius
  --radius-sm: 0.25rem;   // 4px
  --radius-md: 0.5rem;    // 8px
  --radius-lg: 0.75rem;   // 12px
  --radius-xl: 1rem;      // 16px
  
  // Shadows
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);
}
```

## 🎨 3. 디바이스별 UI 패턴

### 3.1 네비게이션 시스템

#### 3.1.1 모바일 (햄버거 메뉴)
```tsx
// Mobile Navigation
const MobileNavigation = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  
  return (
    <header className="mobile-header">
      <div className="header-top">
        <button 
          className="hamburger-menu"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          aria-label="메뉴 열기"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
        
        <h1 className="logo">WKMS</h1>
        
        <button className="user-avatar" aria-label="사용자 메뉴">
          <img src={user.avatar} alt={user.name} />
        </button>
      </div>
      
      <AnimatePresence>
        {isMenuOpen && (
          <motion.nav 
            className="mobile-nav-menu"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'tween', duration: 0.3 }}
          >
            <ul className="nav-items">
              {menuItems.map(item => (
                <li key={item.path}>
                  <Link 
                    to={item.path} 
                    className="nav-link"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span className="nav-label">{item.label}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
};
```

#### 3.1.2 태블릿 (탭 네비게이션)
```tsx
// Tablet Navigation
const TabletNavigation = () => {
  return (
    <header className="tablet-header">
      <div className="header-main">
        <h1 className="logo">웅진 WKMS</h1>
        
        <nav className="tab-navigation">
          {mainTabs.map(tab => (
            <Link 
              key={tab.path}
              to={tab.path}
              className={`tab-link ${isActive(tab.path) ? 'active' : ''}`}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-label">{tab.label}</span>
            </Link>
          ))}
        </nav>
        
        <UserProfile />
      </div>
      
      {/* 하위 네비게이션 */}
      <nav className="sub-navigation">
        {currentSubTabs.map(subTab => (
          <Link key={subTab.path} to={subTab.path} className="sub-tab">
            {subTab.label}
          </Link>
        ))}
      </nav>
    </header>
  );
};
```

#### 3.1.3 데스크톱 (사이드바 + 상단바)
```tsx
// Desktop Navigation
const DesktopNavigation = () => {
  return (
    <div className="desktop-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <img src="/logo.svg" alt="WKMS" className="logo" />
          <h2>웅진 WKMS</h2>
        </div>
        
        <nav className="sidebar-nav">
          {navigationGroups.map(group => (
            <div key={group.name} className="nav-group">
              <h3 className="nav-group-title">{group.name}</h3>
              <ul className="nav-group-items">
                {group.items.map(item => (
                  <li key={item.path}>
                    <Link 
                      to={item.path}
                      className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                    >
                      <span className="nav-icon">{item.icon}</span>
                      <span className="nav-label">{item.label}</span>
                      {item.badge && (
                        <span className="nav-badge">{item.badge}</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
      
      <div className="main-content">
        <header className="top-bar">
          <div className="breadcrumb">
            <Breadcrumb />
          </div>
          
          <div className="top-bar-actions">
            <SearchBar />
            <NotificationCenter />
            <UserDropdown />
          </div>
        </header>
        
        <main className="content-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
```

### 3.2 검색 인터페이스

#### 3.2.1 모바일 검색
```tsx
// Mobile Search Interface
const MobileSearchInterface = () => {
  const [isSearchActive, setIsSearchActive] = useState(false);
  
  return (
    <div className="mobile-search">
      {!isSearchActive ? (
        // 축약된 검색바
        <button 
          className="search-trigger"
          onClick={() => setIsSearchActive(true)}
        >
          <SearchIcon />
          <span>지식 검색...</span>
        </button>
      ) : (
        // 전체 화면 검색
        <div className="search-overlay">
          <div className="search-header">
            <button 
              className="back-button"
              onClick={() => setIsSearchActive(false)}
            >
              <ArrowLeftIcon />
            </button>
            
            <SearchInput 
              placeholder="궁금한 것을 물어보세요"
              autoFocus
            />
          </div>
          
          <div className="search-content">
            <RecentSearches />
            <PopularQueries />
            <SearchResults />
          </div>
        </div>
      )}
    </div>
  );
};
```

#### 3.2.2 태블릿/데스크톱 검색
```tsx
// Desktop Search Interface
const DesktopSearchInterface = () => {
  return (
    <div className="desktop-search">
      <div className="search-container">
        <div className="search-input-wrapper">
          <SearchInput 
            placeholder="문서, 질문, 키워드로 검색"
            className="main-search"
          />
          <div className="search-filters">
            <FilterButton type="document" label="문서" />
            <FilterButton type="category" label="카테고리" />
            <FilterButton type="author" label="작성자" />
            <FilterButton type="date" label="날짜" />
          </div>
        </div>
        
        <div className="search-results-layout">
          <aside className="search-sidebar">
            <SearchFilters />
            <SavedSearches />
          </aside>
          
          <main className="search-results">
            <SearchResultsList />
          </main>
        </div>
      </div>
    </div>
  );
};
```

### 3.3 문서 업로드 인터페이스

#### 3.3.1 모바일 업로드
```tsx
// Mobile Upload Interface
const MobileUploadInterface = () => {
  return (
    <div className="mobile-upload">
      {/* 단계별 업로드 프로세스 */}
      <div className="upload-steps">
        <Step1_FileSelection />
        <Step2_Metadata />
        <Step3_Permissions />
        <Step4_Confirmation />
      </div>
      
      {/* 드래그 앤 드롭 대신 카메라/갤러리 선택 */}
      <div className="file-input-options">
        <button className="camera-input">
          <CameraIcon />
          <span>사진 촬영</span>
        </button>
        
        <button className="gallery-input">
          <GalleryIcon />
          <span>갤러리 선택</span>
        </button>
        
        <button className="file-input">
          <FileIcon />
          <span>파일 선택</span>
        </button>
      </div>
    </div>
  );
};
```

#### 3.3.2 데스크톱 업로드
```tsx
// Desktop Upload Interface
const DesktopUploadInterface = () => {
  return (
    <div className="desktop-upload">
      <div className="upload-layout">
        {/* 좌측: 드래그 앤 드롭 영역 */}
        <div className="upload-dropzone">
          <DragDropArea />
          <UploadProgress />
        </div>
        
        {/* 우측: 메타데이터 및 권한 설정 */}
        <div className="upload-settings">
          <MetadataForm />
          <PermissionSettings />
          <PreviewArea />
        </div>
      </div>
    </div>
  );
};
```

## 🎯 4. 상호작용 패턴

### 4.1 터치 친화적 인터페이스
```scss
// Touch-friendly sizing
.touch-target {
  min-height: 44px;  // iOS 권장 최소 터치 영역
  min-width: 44px;
  
  @include tablet-p {
    min-height: 48px;  // Android 권장 크기
    min-width: 48px;
  }
}

// Touch gestures support
.swipeable {
  touch-action: pan-x;
  
  &.vertical {
    touch-action: pan-y;
  }
}

// Hover states only for devices that support hover
@media (hover: hover) {
  .button:hover {
    background-color: var(--color-primary-hover);
  }
}
```

### 4.2 제스처 지원
```tsx
// Swipe gestures for mobile
const SwipeableCard = ({ children, onSwipeLeft, onSwipeRight }) => {
  const handlers = useSwipeable({
    onSwipedLeft: onSwipeLeft,
    onSwipedRight: onSwipeRight,
    swipeDuration: 500,
    preventScrollOnSwipe: true,
    trackMouse: true
  });
  
  return (
    <div {...handlers} className="swipeable-card">
      {children}
    </div>
  );
};

// Pull-to-refresh
const PullToRefresh = ({ onRefresh, children }) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const handlePullToRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setIsRefreshing(false);
  };
  
  return (
    <div className="pull-to-refresh">
      <motion.div
        className="refresh-indicator"
        initial={{ y: -50, opacity: 0 }}
        animate={{ 
          y: isRefreshing ? 0 : -50,
          opacity: isRefreshing ? 1 : 0
        }}
      >
        <RefreshIcon className={isRefreshing ? 'spinning' : ''} />
      </motion.div>
      
      {children}
    </div>
  );
};
```

### 4.3 키보드 네비게이션
```tsx
// Keyboard navigation support
const KeyboardNavigableList = ({ items, onSelect }) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  
  useEffect(() => {
    const handleKeyDown = (e) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev => 
            prev < items.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => prev > 0 ? prev - 1 : prev);
          break;
        case 'Enter':
          e.preventDefault();
          onSelect(items[selectedIndex]);
          break;
        case 'Escape':
          e.preventDefault();
          setSelectedIndex(0);
          break;
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [items, selectedIndex, onSelect]);
  
  return (
    <ul className="keyboard-navigable-list" role="listbox">
      {items.map((item, index) => (
        <li 
          key={item.id}
          className={`list-item ${index === selectedIndex ? 'selected' : ''}`}
          role="option"
          aria-selected={index === selectedIndex}
        >
          {item.content}
        </li>
      ))}
    </ul>
  );
};
```

## 📱 5. 디바이스별 컴포넌트 최적화

### 5.1 카드 컴포넌트
```tsx
// Responsive Card Component
interface CardProps {
  children: React.ReactNode;
  variant?: 'default' | 'compact' | 'detailed';
  interactive?: boolean;
}

const Card: React.FC<CardProps> = ({ 
  children, 
  variant = 'default', 
  interactive = false 
}) => {
  const cardClasses = classNames(
    'card',
    `card--${variant}`,
    {
      'card--interactive': interactive
    }
  );
  
  return (
    <div className={cardClasses}>
      {children}
    </div>
  );
};

// CSS for responsive cards
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  box-shadow: var(--shadow-sm);
  
  // Mobile: Stack vertically, full width
  @include mobile-l {
    margin-bottom: var(--spacing-sm);
    
    &--compact {
      padding: var(--spacing-sm);
      
      .card__title {
        font-size: var(--font-size-sm);
      }
    }
  }
  
  // Tablet: 2 columns
  @include tablet-p {
    &--detailed {
      display: grid;
      grid-template-columns: 1fr 2fr;
      gap: var(--spacing-md);
    }
  }
  
  // Desktop: Enhanced interactions
  @include laptop {
    transition: all 0.2s ease;
    
    &--interactive:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-lg);
    }
  }
}
```

### 5.2 테이블 컴포넌트
```tsx
// Responsive Table Component
const ResponsiveTable = ({ data, columns }) => {
  const [isMobile] = useMediaQuery('(max-width: 768px)');
  
  if (isMobile) {
    // Mobile: Card layout
    return (
      <div className="mobile-table">
        {data.map((row, index) => (
          <div key={index} className="mobile-table-card">
            {columns.map(column => (
              <div key={column.key} className="mobile-table-row">
                <span className="mobile-table-label">
                  {column.label}:
                </span>
                <span className="mobile-table-value">
                  {row[column.key]}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }
  
  // Desktop: Traditional table
  return (
    <div className="table-container">
      <table className="responsive-table">
        <thead>
          <tr>
            {columns.map(column => (
              <th key={column.key} className={column.className}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr key={index}>
              {columns.map(column => (
                <td key={column.key} className={column.className}>
                  {row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

### 5.3 모달/다이얼로그
```tsx
// Responsive Modal Component
const ResponsiveModal = ({ isOpen, onClose, children, title }) => {
  const [isMobile] = useMediaQuery('(max-width: 768px)');
  
  if (isMobile) {
    // Mobile: Full screen bottom sheet
    return (
      <AnimatePresence>
        {isOpen && (
          <motion.div className="mobile-modal-overlay">
            <motion.div 
              className="mobile-modal"
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'tween', duration: 0.3 }}
            >
              <div className="mobile-modal-header">
                <h2>{title}</h2>
                <button onClick={onClose} className="close-button">
                  <CloseIcon />
                </button>
              </div>
              
              <div className="mobile-modal-content">
                {children}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    );
  }
  
  // Desktop: Centered modal
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div 
          className="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div 
            className="modal"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            onClick={e => e.stopPropagation()}
          >
            <div className="modal-header">
              <h2>{title}</h2>
              <button onClick={onClose} className="close-button">
                <CloseIcon />
              </button>
            </div>
            
            <div className="modal-content">
              {children}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
```

## 🎨 6. 다크 모드 지원

### 6.1 컬러 시스템
```scss
// Light theme (default)
:root {
  --color-background: #ffffff;
  --color-surface: #f8fafc;
  --color-primary: #3b82f6;
  --color-primary-hover: #2563eb;
  --color-text-primary: #1f2937;
  --color-text-secondary: #6b7280;
  --color-border: #e5e7eb;
  --color-shadow: rgba(0, 0, 0, 0.1);
}

// Dark theme
[data-theme='dark'] {
  --color-background: #111827;
  --color-surface: #1f2937;
  --color-primary: #60a5fa;
  --color-primary-hover: #3b82f6;
  --color-text-primary: #f9fafb;
  --color-text-secondary: #d1d5db;
  --color-border: #374151;
  --color-shadow: rgba(0, 0, 0, 0.3);
}

// System preference detection
@media (prefers-color-scheme: dark) {
  :root {
    --color-background: #111827;
    --color-surface: #1f2937;
    --color-primary: #60a5fa;
    --color-primary-hover: #3b82f6;
    --color-text-primary: #f9fafb;
    --color-text-secondary: #d1d5db;
    --color-border: #374151;
    --color-shadow: rgba(0, 0, 0, 0.3);
  }
}
```

### 6.2 테마 토글 컴포넌트
```tsx
// Theme Toggle Component
const ThemeToggle = () => {
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  
  useEffect(() => {
    const root = document.documentElement;
    
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark' : 'light';
      root.setAttribute('data-theme', systemTheme);
    } else {
      root.setAttribute('data-theme', theme);
    }
  }, [theme]);
  
  return (
    <div className="theme-toggle">
      <button
        onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
        className="theme-toggle-button"
        aria-label="테마 변경"
      >
        {theme === 'light' ? <MoonIcon /> : <SunIcon />}
      </button>
    </div>
  );
};
```

## 🌐 7. 접근성 (Accessibility) 표준

### 7.1 WCAG 2.1 AA 준수
```tsx
// Accessible components
const AccessibleButton = ({ 
  children, 
  onClick, 
  disabled = false,
  ariaLabel,
  ...props 
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className="accessible-button"
      role="button"
      tabIndex={disabled ? -1 : 0}
      {...props}
    >
      {children}
    </button>
  );
};

// Screen reader support
const SkipLink = () => (
  <a 
    href="#main-content" 
    className="skip-link"
    onFocus={(e) => e.target.classList.add('visible')}
    onBlur={(e) => e.target.classList.remove('visible')}
  >
    본문 바로가기
  </a>
);

// Focus management
const FocusTrap = ({ children, isActive }) => {
  const trapRef = useRef(null);
  
  useEffect(() => {
    if (isActive && trapRef.current) {
      const focusableElements = trapRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      
      firstElement?.focus();
      
      const handleTabKey = (e) => {
        if (e.key === 'Tab') {
          if (e.shiftKey) {
            if (document.activeElement === firstElement) {
              lastElement?.focus();
              e.preventDefault();
            }
          } else {
            if (document.activeElement === lastElement) {
              firstElement?.focus();
              e.preventDefault();
            }
          }
        }
      };
      
      document.addEventListener('keydown', handleTabKey);
      return () => document.removeEventListener('keydown', handleTabKey);
    }
  }, [isActive]);
  
  return <div ref={trapRef}>{children}</div>;
};
```

### 7.2 고대비 모드 지원
```scss
// High contrast mode support
@media (prefers-contrast: high) {
  :root {
    --color-primary: #0000ff;
    --color-background: #ffffff;
    --color-text-primary: #000000;
    --color-border: #000000;
  }
  
  .button {
    border: 2px solid var(--color-text-primary);
  }
  
  .card {
    border: 1px solid var(--color-border);
  }
}

// Reduced motion support
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## 🚀 8. 성능 최적화

### 8.1 이미지 최적화
```tsx
// Responsive images with lazy loading
const ResponsiveImage = ({ 
  src, 
  alt, 
  sizes = "(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw" 
}) => {
  return (
    <picture>
      <source 
        media="(max-width: 768px)" 
        srcSet={`${src}?w=768&f=webp 768w, ${src}?w=384&f=webp 384w`}
        type="image/webp"
      />
      <source 
        media="(max-width: 1200px)" 
        srcSet={`${src}?w=1200&f=webp 1200w, ${src}?w=600&f=webp 600w`}
        type="image/webp"
      />
      <img 
        src={src}
        alt={alt}
        sizes={sizes}
        loading="lazy"
        decoding="async"
        className="responsive-image"
      />
    </picture>
  );
};
```

### 8.2 Virtual Scrolling
```tsx
// Virtual scrolling for large lists
const VirtualizedList = ({ items, itemHeight = 60 }) => {
  const [scrollTop, setScrollTop] = useState(0);
  const containerHeight = 400;
  const visibleCount = Math.ceil(containerHeight / itemHeight);
  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(startIndex + visibleCount, items.length);
  const visibleItems = items.slice(startIndex, endIndex);
  
  return (
    <div 
      className="virtual-list-container"
      style={{ height: containerHeight, overflow: 'auto' }}
      onScroll={(e) => setScrollTop(e.target.scrollTop)}
    >
      <div style={{ height: items.length * itemHeight, position: 'relative' }}>
        {visibleItems.map((item, index) => (
          <div
            key={startIndex + index}
            style={{
              position: 'absolute',
              top: (startIndex + index) * itemHeight,
              height: itemHeight,
              width: '100%'
            }}
          >
            <ListItem item={item} />
          </div>
        ))}
      </div>
    </div>
  );
};
```

## 📊 9. 구현 우선순위 및 로드맵

### 9.1 Phase 1: 기본 반응형 구조 (2주)
1. **Breakpoint 시스템 구축**
   - SCSS 믹스인 및 변수 정의
   - Grid 시스템 구현
   - Design Token 시스템

2. **기본 레이아웃 컴포넌트**
   - 반응형 헤더/네비게이션
   - 사이드바/모바일 메뉴
   - 메인 콘텐츠 영역

3. **공통 컴포넌트**
   - 버튼, 입력 필드, 카드
   - 모달/다이얼로그
   - 로딩 스피너

### 9.2 Phase 2: 핵심 인터랙션 (2주)
1. **검색 인터페이스**
   - 디바이스별 검색 UI
   - 자동완성 및 필터링
   - 검색 결과 표시

2. **업로드 인터페이스**
   - 드래그 앤 드롭 (데스크톱)
   - 모바일 파일 선택
   - 진행률 표시

3. **제스처 지원**
   - 스와이프 네비게이션
   - Pull-to-refresh
   - 터치 피드백

### 9.3 Phase 3: 고급 기능 (2주)
1. **다크 모드**
   - 테마 시스템 구축
   - 자동/수동 테마 전환
   - 시스템 설정 연동

2. **접근성 강화**
   - 키보드 네비게이션
   - 스크린 리더 지원
   - 고대비 모드

3. **성능 최적화**
   - Virtual scrolling
   - 이미지 최적화
   - 코드 스플리팅

### 9.4 Phase 4: 고급 UX (2주)
1. **애니메이션 시스템**
   - Micro-interactions
   - 페이지 전환 효과
   - 로딩 애니메이션

2. **PWA 기능**
   - 오프라인 지원
   - 푸시 알림
   - 홈 화면 추가

3. **사용자 개인화**
   - 레이아웃 커스터마이징
   - 즐겨찾기 기능
   - 사용 패턴 학습

### 9.5 Phase 5: 테스트 및 최적화 (1주)
1. **디바이스 테스트**
   - 실제 기기 테스트
   - 브라우저 호환성
   - 성능 벤치마킹

2. **사용성 테스트**
   - A/B 테스트
   - 사용자 피드백 수집
   - UX 개선

## 🛠️ 10. 개발 도구 및 라이브러리

### 10.1 필수 라이브러리
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.8.0",
    "framer-motion": "^10.0.0",
    "react-query": "^4.0.0",
    "@radix-ui/react-accordion": "^1.1.0",
    "@radix-ui/react-dialog": "^1.0.0",
    "react-use-gesture": "^9.1.3",
    "react-intersection-observer": "^9.4.0",
    "react-virtual": "^2.10.4"
  },
  "devDependencies": {
    "@storybook/react": "^6.5.0",
    "jest": "^29.0.0",
    "@testing-library/react": "^13.0.0",
    "@testing-library/jest-dom": "^5.16.0",
    "cypress": "^12.0.0",
    "sass": "^1.58.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

### 10.2 빌드 도구 설정
```javascript
// vite.config.js
export default {
  plugins: [
    react(),
    // PWA 플러그인
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}']
      }
    })
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'router': ['react-router-dom'],
          'ui': ['framer-motion', '@radix-ui/react-dialog']
        }
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: '@import "src/styles/variables.scss";'
      }
    }
  }
};
```

이 표준을 따라 구현하면 모든 디바이스에서 일관되고 최적화된 사용자 경험을 제공하는 현대적인 웹 애플리케이션을 구축할 수 있습니다.
