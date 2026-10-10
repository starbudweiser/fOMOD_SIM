import React, { useState, useEffect } from 'react';
import { useI18n } from '../locales';

interface FolderSelectModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentPath: string;
  onSelectDirectoryHandle: (handle: FileSystemDirectoryHandle) => void;
  onSetCustomPath: (path: string) => void;
}

export default function FolderSelectModal({
  isOpen,
  onClose,
  currentPath,
  onSelectDirectoryHandle,
  onSetCustomPath,
}: FolderSelectModalProps) {
  const { strings } = useI18n();
  const m = strings.modals.folderSelect;
  const c = strings.common;

  const [manualPath, setManualPath] = useState(currentPath);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setManualPath(currentPath);
      setErrorMsg(null);
    }
  }, [isOpen, currentPath]);

  if (!isOpen) return null;

  const isInIframe = typeof window !== 'undefined' && window.self !== window.top;
  const hasDirectoryPicker = typeof window !== 'undefined' && 'showDirectoryPicker' in window;

  const handlePickLocalFolder = async () => {
    setErrorMsg(null);
    if (!hasDirectoryPicker) {
      setErrorMsg(
        'Votre navigateur ne supporte pas l’accès direct au système de fichiers (File System Access).'
      );
      return;
    }

    try {
      // @ts-expect-error File System Access API
      const handle: FileSystemDirectoryHandle = await window.showDirectoryPicker({
        mode: 'readwrite',
      });
      onSelectDirectoryHandle(handle);
      onClose();
    } catch (err: unknown) {
      const name = (err as { name?: string }).name;
      if (name === 'AbortError') {
        return;
      }
      setErrorMsg(`Erreur : ${(err as Error).message || String(err)}`);
    }
  };

  const handleOpenNewTab = () => {
    window.open(window.location.href, '_blank');
    onClose();
  };

  const handleSaveManual = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualPath.trim()) {
      onSetCustomPath(manualPath.trim());
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-[#1e1e1e] border border-[#333333] shadow-2xl rounded p-6 flex flex-col space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-[#333333]">
          <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
            <span>📁</span> {m.title}
          </h2>
          <button
            onClick={onClose}
            className="text-[#999] hover:text-white text-xl leading-none px-2 cursor-pointer transition-colors"
            title={c.close}
          >
            &times;
          </button>
        </div>

        {/* Note importante */}
        <div className="p-2.5 bg-[#172554]/50 border border-[#1d4ed8] rounded text-xs text-[#93c5fd] flex items-start gap-2">
          <span className="text-sm">ℹ️</span>
          <span>
            {c.destination} {manualPath}
          </span>
        </div>

        {/* Explication iframe si nécessaire */}
        {isInIframe && (
          <div className="p-3 bg-[#0c4a6e]/40 border border-[#0284c7] rounded text-xs text-[#bae6fd] space-y-2">
            <button
              type="button"
              onClick={handleOpenNewTab}
              className="w-full py-2 px-3 bg-[#0284c7] hover:bg-[#0369a1] text-white font-bold rounded transition-colors text-xs flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
            >
              <span>🚀 Ouvrir dans un nouvel onglet autonome</span>
            </button>
          </div>
        )}

        {/* Option 1: Bouton Explorateur */}
        <div className="space-y-2">
          <label className="text-xs text-[#ccc] font-semibold block">
            {m.nativeFolder}
          </label>
          <button
            type="button"
            onClick={handlePickLocalFolder}
            className="w-full py-2.5 px-4 bg-[#333333] hover:bg-[#404040] text-white font-medium text-xs rounded transition-colors flex items-center justify-center gap-2 cursor-pointer border border-[#444444]"
          >
            <span>📁 {m.nativeFolder}</span>
          </button>
          {errorMsg && (
            <div className="text-xs text-[#f87171] p-2 bg-[#450a0a]/40 border border-[#7f1d1d] rounded">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Option 2: Saisie manuelle du chemin */}
        <form onSubmit={handleSaveManual} className="space-y-2 pt-2 border-t border-[#333333]">
          <label className="text-xs text-[#ccc] font-semibold block">
            {m.customManual}
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={manualPath}
              onChange={(e) => setManualPath(e.target.value)}
              placeholder="ex: /Users/stephan/Desktop/Staging"
              className="flex-1 text-xs bg-[#161616] border border-[#383838] focus:border-[#0ea5e9] rounded px-3 py-2 text-white focus:outline-hidden"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-[#0ea5e9] hover:bg-[#0284c7] text-white font-bold text-xs rounded transition-colors cursor-pointer"
            >
              {c.confirm}
            </button>
          </div>
          <div className="text-[11px] text-[#888]">
            {c.destination} <span className="text-[#38bdf8] font-mono">{currentPath}</span>
          </div>
        </form>

        {/* Footer */}
        <div className="pt-2 border-t border-[#333333] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 bg-[#333333] hover:bg-[#444444] text-white text-xs font-medium rounded transition-colors cursor-pointer"
          >
            {c.close}
          </button>
        </div>
      </div>
    </div>
  );
}
