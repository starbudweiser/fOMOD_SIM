import { useI18n } from '../locales';

interface StagingWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  onChooseFolder: () => void;
}

/** Avertissement affiché quand on génère le staging sans avoir choisi de dossier de destination. */
export default function StagingWarningModal({ isOpen, onClose, onChooseFolder }: StagingWarningModalProps) {
  const { strings } = useI18n();
  const w = strings.stagingWarning;
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        role="alertdialog"
        aria-labelledby="staging-warning-title"
        className="w-full max-w-md bg-[#1e1e1e] shadow-2xl rounded p-6 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="staging-warning-title" className="text-base font-bold text-white tracking-wide flex items-center gap-2">
          <span className="text-[#fbbf24]">⚠</span> {w.title}
        </h2>
        <p className="text-sm text-[#ddd] leading-relaxed whitespace-pre-line">{w.message}</p>
        <div className="flex justify-end gap-2.5 pt-1">
          <button
            onClick={onClose}
            className="py-2 px-4 bg-[#333333] hover:bg-[#404040] text-white text-xs font-bold rounded transition-colors cursor-pointer"
          >
            {w.cancel}
          </button>
          <button
            autoFocus
            onClick={onChooseFolder}
            className="py-2 px-4 bg-[#0ea5e9] hover:bg-[#0284c7] text-white text-xs font-bold rounded transition-colors cursor-pointer"
          >
            {w.choose}
          </button>
        </div>
      </div>
    </div>
  );
}
