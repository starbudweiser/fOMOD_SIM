import React, { createContext, useContext, useState, useEffect, useMemo, ReactNode } from 'react';
import { Language, LanguageInfo, Translations } from './types';
import { fr } from './fr';
import { en } from './en';
import { it } from './it';
import { es } from './es';

export * from './types';

export const AVAILABLE_LANGUAGES: LanguageInfo[] = [
  { code: 'fr', name: 'Français', nativeName: 'Français', flag: '🇫🇷' },
  { code: 'en', name: 'English', nativeName: 'English', flag: '🇬🇧' },
  { code: 'it', name: 'Italiano', nativeName: 'Italiano', flag: '🇮🇹' },
  { code: 'es', name: 'Español', nativeName: 'Español', flag: '🇪🇸' },
];

const TRANSLATIONS: Record<Language, Translations> = {
  fr,
  en,
  it,
  es,
};

const STORAGE_KEY = 'fomod_sim_language';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  strings: Translations;
  availableLanguages: LanguageInfo[];
  t: (keyPath: string, fallback?: string) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Language | null;
      if (saved && (saved === 'fr' || saved === 'en' || saved === 'it' || saved === 'es')) {
        return saved;
      }
    } catch {
      // Fallback
    }
    // Default language is French as requested: "Nous partons avec le français (par défaut pour l'instant)"
    return 'fr';
  });

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
      document.documentElement.lang = lang;
    } catch {
      // Ignore localStorage errors
    }
  };

  useEffect(() => {
    try {
      document.documentElement.lang = language;
    } catch {
      // Ignore
    }
  }, [language]);

  const strings = useMemo(() => {
    return TRANSLATIONS[language] || TRANSLATIONS.fr;
  }, [language]);

  const t = (keyPath: string, fallback?: string): string => {
    const parts = keyPath.split('.');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let curr: any = strings;
    for (const part of parts) {
      if (curr && typeof curr === 'object' && part in curr) {
        curr = curr[part];
      } else {
        return fallback || keyPath;
      }
    }
    return typeof curr === 'string' ? curr : fallback || keyPath;
  };

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      strings,
      availableLanguages: AVAILABLE_LANGUAGES,
      t,
    }),
    [language, strings]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useI18n must be used within a LanguageProvider');
  }
  return context;
}
