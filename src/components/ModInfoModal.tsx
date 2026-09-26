import { FomodMetadata } from '../types/fomod';
import { useI18n } from '../locales';

interface ModInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  metadata: FomodMetadata;
}

export default function ModInfoModal({
  isOpen,
  onClose,
  metadata,
}: ModInfoModalProps) {
  const { strings } = useI18n();
  const m = strings.modals.modInfo;
  const c = strings.common;

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-[#1e1e1e] border border-[#333333] shadow-2xl rounded p-6 flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-3 border-b border-[#333333]">
          <h2 className="text-base font-bold text-white tracking-wide">
            ℹ️ {m.title}
          </h2>
          <button
            onClick={onClose}
            className="text-[#999] hover:text-white text-xl leading-none px-2 cursor-pointer transition-colors"
            title={c.close}
          >
            &times;
          </button>
        </div>

        <div className="py-4 space-y-3 overflow-y-auto pr-1">
          <div className="grid grid-cols-[100px_1fr] gap-2 items-baseline">
            <span className="text-sm font-bold text-white">{m.name}</span>
            <span className="text-sm text-[#ddd] bg-[#222222] px-3 py-1.5 rounded border border-[#2d2d2d]">
              {metadata.name || '—'}
            </span>
          </div>

          <div className="grid grid-cols-[100px_1fr] gap-2 items-baseline">
            <span className="text-sm font-bold text-white">{m.author}</span>
            <span className="text-sm text-[#ddd] bg-[#222222] px-3 py-1.5 rounded border border-[#2d2d2d]">
              {metadata.author || '—'}
            </span>
          </div>

          <div className="grid grid-cols-[100px_1fr] gap-2 items-baseline">
            <span className="text-sm font-bold text-white">{m.version}</span>
            <span className="text-sm text-[#ddd] bg-[#222222] px-3 py-1.5 rounded border border-[#2d2d2d]">
              {metadata.version || '—'}
            </span>
          </div>

          <div className="grid grid-cols-[100px_1fr] gap-2 items-baseline">
            <span className="text-sm font-bold text-white">{m.website}</span>
            <div className="text-sm bg-[#222222] px-3 py-1.5 rounded border border-[#2d2d2d] break-all">
              {metadata.website ? (
                <a
                  href={metadata.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#60a5fa] hover:underline"
                >
                  {metadata.website}
                </a>
              ) : (
                <span className="text-[#888]">—</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-[100px_1fr] gap-2 items-start pt-1">
            <span className="text-sm font-bold text-white pt-1">{m.description}</span>
            <div className="text-sm text-[#ddd] bg-[#222222] p-3 rounded border border-[#2d2d2d] max-h-56 overflow-y-auto whitespace-pre-wrap leading-relaxed font-sans">
              {metadata.description || <span className="italic text-[#888]">—</span>}
            </div>
          </div>
        </div>

        <div className="pt-3 border-t border-[#333333] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#333333] hover:bg-[#444444] text-white text-xs font-medium rounded transition-colors cursor-pointer"
          >
            {c.close}
          </button>
        </div>
      </div>
    </div>
  );
}
