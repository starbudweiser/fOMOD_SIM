import { useState, useRef, useEffect } from 'react';
import { useI18n, Language } from '../locales';

interface LanguageSelectorProps {
  variant?: 'dropdown' | 'pills';
  className?: string;
}

export default function LanguageSelector({
  variant = 'dropdown',
  className = '',
}: LanguageSelectorProps) {
  const { language, setLanguage, availableLanguages } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentLang = availableLanguages.find((l) => l.code === language) || availableLanguages[0];

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  if (variant === 'pills') {
    return (
      <div className={`inline-flex items-center gap-1 p-1 bg-[#18181a] border border-[#303036] rounded-lg shadow-inner ${className}`}>
        {availableLanguages.map((lang) => {
          const isActive = lang.code === language;
          return (
            <button
              key={lang.code}
              type="button"
              onClick={() => setLanguage(lang.code)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                isActive
                  ? 'bg-[#0ea5e9] text-white shadow-sm font-semibold'
                  : 'text-[#a1a1aa] hover:text-white hover:bg-[#27272a]'
              }`}
              title={lang.nativeName}
            >
              <span className="text-xs leading-none">{lang.flag}</span>
              <span>{lang.nativeName}</span>
            </button>
          );
        })}
      </div>
    );
  }

  // Dropdown variant (aesthetic, sleek, fits headers or cards)
  return (
    <div ref={dropdownRef} className={`relative inline-block text-left ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="h-8 px-2.5 bg-[#202024] hover:bg-[#28282e] active:bg-[#1a1a1e] border border-[#383840] hover:border-[#0ea5e9] rounded-md flex items-center gap-2 text-xs font-medium text-[#f1f1f1] transition-all cursor-pointer shadow-sm group"
        title="Changer la langue / Change language"
      >
        <span className="text-base leading-none">{currentLang.flag}</span>
        <span className="font-semibold">{currentLang.nativeName}</span>
        <svg
          className={`w-3.5 h-3.5 text-[#888] group-hover:text-[#38bdf8] transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-44 bg-[#1e1e24] border border-[#3a3a44] rounded-lg shadow-2xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100 overflow-hidden">
          <div className="px-3 py-1.5 text-[10px] uppercase font-bold tracking-wider text-[#71717a] border-b border-[#2a2a32]">
            Langue / Language
          </div>
          {availableLanguages.map((lang) => {
            const isActive = lang.code === language;
            return (
              <button
                key={lang.code}
                type="button"
                onClick={() => {
                  setLanguage(lang.code);
                  setIsOpen(false);
                }}
                className={`w-full px-3 py-2 text-xs flex items-center justify-between transition-colors cursor-pointer text-left ${
                  isActive
                    ? 'bg-[#0ea5e9]/15 text-[#38bdf8] font-bold'
                    : 'text-[#d4d4d8] hover:bg-[#282832] hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-base leading-none">{lang.flag}</span>
                  <span>{lang.nativeName}</span>
                </div>
                {isActive && (
                  <span className="text-[#38bdf8] text-xs font-bold">✓</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
